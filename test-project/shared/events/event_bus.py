"""Internal in-process event bus for intra-service communication.

Provides publish/subscribe with typed events, async handlers,
and optional dead-letter capture for failed deliveries.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Event:
    """Immutable event object passed through the bus.

    Attributes:
        type: Dot-separated event type (e.g. ``user.created``, ``order.paid``).
        payload: Arbitrary event data.
        timestamp: UTC timestamp of event creation.
        source_service: Name of the originating service.
        event_id: Unique identifier for this event instance.
        correlation_id: Optional ID for tracing across service boundaries.
        metadata: Optional extra metadata (headers, tenant info, etc.).
    """

    type: str
    payload: dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source_service: str = "unknown"
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the event to a plain dict for transport."""
        return {
            "event_id": self.event_id,
            "type": self.type,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "source_service": self.source_service,
            "correlation_id": self.correlation_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Event:
        """Deserialize an event from a plain dict."""
        return cls(
            event_id=data["event_id"],
            type=data["type"],
            payload=data["payload"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            source_service=data.get("source_service", "unknown"),
            correlation_id=data.get("correlation_id"),
            metadata=data.get("metadata", {}),
        )


# Type alias for event handler callbacks
EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """Async in-process event bus with wildcard subscription support.

    Supports exact matches (``user.created``) and prefix wildcards
    (``user.*``) for flexible event routing.
    """

    def __init__(self, *, max_dead_letters: int = 1000) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._dead_letters: list[tuple[Event, str, Exception]] = []
        self._max_dead_letters = max_dead_letters
        self._event_count = 0

    def subscribe(
        self,
        event_type: str,
        handler: EventHandler,
    ) -> Callable[[], None]:
        """Register a handler for an event type.

        Args:
            event_type: Event type to listen for. Use ``*`` suffix for
                prefix matching (e.g. ``order.*`` matches ``order.created``
                and ``order.cancelled``).
            handler: Async callable that receives an :class:`Event`.

        Returns:
            An unsubscribe callable that removes this specific handler.
        """
        self._handlers[event_type].append(handler)
        logger.debug("Subscribed handler %s to '%s'", handler.__name__, event_type)

        def _unsubscribe() -> None:
            self._handlers[event_type].remove(handler)

        return _unsubscribe

    async def publish(self, event: Event) -> int:
        """Publish an event to all matching subscribers.

        Handlers are invoked concurrently. Failures in individual handlers
        do not prevent other handlers from executing; failed deliveries
        are captured in the dead-letter queue.

        Args:
            event: The event to publish.

        Returns:
            Number of handlers that were invoked.
        """
        self._event_count += 1
        matching_handlers = self._resolve_handlers(event.type)

        if not matching_handlers:
            logger.debug("No handlers for event type '%s'", event.type)
            return 0

        results = await asyncio.gather(
            *[self._safe_invoke(handler, event) for handler in matching_handlers],
            return_exceptions=False,
        )

        invoked = len(matching_handlers)
        logger.debug(
            "Published event '%s' (%s) to %d handlers",
            event.type,
            event.event_id,
            invoked,
        )
        return invoked

    def _resolve_handlers(self, event_type: str) -> list[EventHandler]:
        """Resolve all handlers matching an event type, including wildcards."""
        handlers: list[EventHandler] = []

        # Exact match
        handlers.extend(self._handlers.get(event_type, []))

        # Wildcard matches: e.g. "user.*" matches "user.created"
        parts = event_type.split(".")
        for i in range(len(parts)):
            prefix = ".".join(parts[: i + 1]) + ".*"
            handlers.extend(self._handlers.get(prefix, []))

        # Global wildcard
        handlers.extend(self._handlers.get("*", []))

        return handlers

    async def _safe_invoke(self, handler: EventHandler, event: Event) -> None:
        """Invoke a handler and capture failures to the dead-letter queue."""
        try:
            await handler(event)
        except Exception as exc:
            logger.exception(
                "Handler %s failed for event '%s' (%s)",
                handler.__name__,
                event.type,
                event.event_id,
            )
            self._dead_letters.append((event, handler.__name__, exc))
            if len(self._dead_letters) > self._max_dead_letters:
                self._dead_letters = self._dead_letters[-self._max_dead_letters :]

    @property
    def dead_letters(self) -> list[tuple[Event, str, Exception]]:
        """Return the dead-letter queue contents."""
        return list(self._dead_letters)

    @property
    def stats(self) -> dict[str, Any]:
        """Return bus statistics."""
        return {
            "total_events_published": self._event_count,
            "registered_event_types": len(self._handlers),
            "total_handlers": sum(len(h) for h in self._handlers.values()),
            "dead_letter_count": len(self._dead_letters),
        }

    def clear(self) -> None:
        """Remove all handlers and clear the dead-letter queue."""
        self._handlers.clear()
        self._dead_letters.clear()
        self._event_count = 0


# Module-level singleton for convenience
_default_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Return the default module-level event bus singleton."""
    global _default_bus
    if _default_bus is None:
        _default_bus = EventBus()
    return _default_bus
