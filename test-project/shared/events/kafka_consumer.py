"""Kafka consumer with consumer group support and batch processing.

Wraps ``aiokafka`` with deserialization, error handling, offset management,
and graceful shutdown for reliable event consumption.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Coroutine, Sequence

from aiokafka import AIOKafkaConsumer, TopicPartition
from aiokafka.errors import KafkaError

from shared.events.event_bus import Event

logger = logging.getLogger(__name__)

# Type alias for message handler callbacks
MessageHandler = Callable[[Event], Coroutine[Any, Any, None]]
BatchHandler = Callable[[list[Event]], Coroutine[Any, Any, None]]


class KafkaEventConsumer:
    """Kafka consumer with consumer group, batch processing, and error handling.

    Supports both single-message and batch processing modes with
    configurable retry and dead-letter routing.
    """

    def __init__(
        self,
        topics: list[str],
        group_id: str,
        bootstrap_servers: str | list[str] = "localhost:9092",
        *,
        client_id: str = "prism-consumer",
        auto_offset_reset: str = "earliest",
        enable_auto_commit: bool = False,
        max_poll_records: int = 500,
        max_poll_interval_ms: int = 300_000,
        session_timeout_ms: int = 30_000,
        heartbeat_interval_ms: int = 10_000,
    ) -> None:
        self._topics = topics
        self._group_id = group_id
        self._consumer: AIOKafkaConsumer | None = None
        self._running = False
        self._processed_count = 0
        self._error_count = 0

        self._consumer_kwargs = {
            "bootstrap_servers": bootstrap_servers,
            "client_id": client_id,
            "group_id": group_id,
            "auto_offset_reset": auto_offset_reset,
            "enable_auto_commit": enable_auto_commit,
            "max_poll_records": max_poll_records,
            "max_poll_interval_ms": max_poll_interval_ms,
            "session_timeout_ms": session_timeout_ms,
            "heartbeat_interval_ms": heartbeat_interval_ms,
            "value_deserializer": self._deserialize_value,
            "key_deserializer": self._deserialize_key,
        }

    @staticmethod
    def _deserialize_value(raw: bytes) -> dict[str, Any]:
        """Deserialize a JSON-encoded message value."""
        return json.loads(raw.decode("utf-8"))

    @staticmethod
    def _deserialize_key(raw: bytes | None) -> str | None:
        """Deserialize a message key."""
        if raw is None:
            return None
        return raw.decode("utf-8")

    async def start(self) -> None:
        """Start the consumer and subscribe to topics."""
        self._consumer = AIOKafkaConsumer(*self._topics, **self._consumer_kwargs)
        await self._consumer.start()
        self._running = True
        logger.info(
            "Kafka consumer started: group=%s, topics=%s",
            self._group_id,
            self._topics,
        )

    async def consume(
        self,
        handler: MessageHandler,
        *,
        dead_letter_topic: str | None = None,
        max_retries: int = 3,
    ) -> None:
        """Consume messages one at a time, invoking *handler* for each.

        Runs until :meth:`stop` is called. On handler failure, retries
        up to *max_retries* times before routing to the dead-letter topic.

        Args:
            handler: Async callback receiving a deserialized :class:`Event`.
            dead_letter_topic: Topic name for messages that fail processing.
            max_retries: Number of retry attempts per message.
        """
        if self._consumer is None:
            raise RuntimeError("Consumer not started. Call start() first.")

        logger.info("Starting consume loop (group=%s)...", self._group_id)

        try:
            async for message in self._consumer:
                if not self._running:
                    break

                event = self._to_event(message.value)
                success = False

                for attempt in range(1, max_retries + 1):
                    try:
                        await handler(event)
                        success = True
                        self._processed_count += 1
                        break
                    except Exception:
                        logger.warning(
                            "Handler failed for event %s (attempt %d/%d)",
                            event.event_id,
                            attempt,
                            max_retries,
                            exc_info=True,
                        )
                        if attempt < max_retries:
                            await asyncio.sleep(0.5 * attempt)

                if not success:
                    self._error_count += 1
                    logger.error(
                        "Event %s exhausted retries, routing to dead-letter",
                        event.event_id,
                    )
                    if dead_letter_topic:
                        await self._send_to_dead_letter(dead_letter_topic, message)

                # Manual commit after successful processing
                await self._consumer.commit()

        except asyncio.CancelledError:
            logger.info("Consume loop cancelled.")
        except KafkaError:
            logger.exception("Kafka error in consume loop.")

    async def process_batch(
        self,
        handler: BatchHandler,
        *,
        batch_size: int = 100,
        batch_timeout_ms: int = 5000,
        dead_letter_topic: str | None = None,
    ) -> None:
        """Consume messages in batches for higher throughput.

        Collects up to *batch_size* messages or waits *batch_timeout_ms*
        before dispatching a batch to the handler.

        Args:
            handler: Async callback receiving a list of :class:`Event` objects.
            batch_size: Maximum events per batch.
            batch_timeout_ms: Maximum wait time for batch accumulation.
            dead_letter_topic: Topic for unprocessable batches.
        """
        if self._consumer is None:
            raise RuntimeError("Consumer not started. Call start() first.")

        logger.info(
            "Starting batch consume loop (group=%s, batch_size=%d)",
            self._group_id,
            batch_size,
        )

        try:
            while self._running:
                raw_messages = await self._consumer.getmany(
                    timeout_ms=batch_timeout_ms,
                    max_records=batch_size,
                )

                if not raw_messages:
                    continue

                events: list[Event] = []
                for tp, messages in raw_messages.items():
                    for message in messages:
                        events.append(self._to_event(message.value))

                if not events:
                    continue

                try:
                    await handler(events)
                    self._processed_count += len(events)
                    await self._consumer.commit()
                except Exception:
                    self._error_count += len(events)
                    logger.exception(
                        "Batch handler failed for %d events", len(events)
                    )

        except asyncio.CancelledError:
            logger.info("Batch consume loop cancelled.")

    async def commit(self) -> None:
        """Manually commit current offsets."""
        if self._consumer is None:
            raise RuntimeError("Consumer not started.")
        await self._consumer.commit()
        logger.debug("Offsets committed for group '%s'.", self._group_id)

    async def seek_to_beginning(self, topic: str, partition: int) -> None:
        """Seek a specific partition to the beginning."""
        if self._consumer is None:
            raise RuntimeError("Consumer not started.")
        tp = TopicPartition(topic, partition)
        await self._consumer.seek_to_beginning(tp)
        logger.info("Seeked %s[%d] to beginning.", topic, partition)

    async def stop(self) -> None:
        """Stop the consumer and release resources."""
        self._running = False
        if self._consumer is not None:
            await self._consumer.stop()
            self._consumer = None
            logger.info("Kafka consumer stopped (group=%s).", self._group_id)

    @staticmethod
    def _to_event(data: dict[str, Any]) -> Event:
        """Convert a raw message dict to an Event, with fallback."""
        try:
            return Event.from_dict(data)
        except (KeyError, TypeError):
            # Handle non-standard message formats
            return Event(
                type=data.get("type", "unknown"),
                payload=data,
                source_service=data.get("source_service", "external"),
            )

    async def _send_to_dead_letter(self, topic: str, message: Any) -> None:
        """Route a failed message to the dead-letter topic."""
        try:
            from shared.events.kafka_producer import send_raw

            await send_raw(
                topic=topic,
                value={
                    "original_topic": message.topic,
                    "original_partition": message.partition,
                    "original_offset": message.offset,
                    "original_key": message.key,
                    "payload": message.value,
                    "error": "exhausted_retries",
                },
                key=message.key,
            )
        except Exception:
            logger.exception("Failed to route message to dead-letter topic '%s'", topic)

    @property
    def stats(self) -> dict[str, Any]:
        """Return consumer statistics."""
        return {
            "group_id": self._group_id,
            "topics": self._topics,
            "running": self._running,
            "processed_count": self._processed_count,
            "error_count": self._error_count,
        }
