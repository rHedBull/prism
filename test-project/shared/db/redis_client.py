"""Redis connection manager with singleton pattern and pub/sub support.

Provides a single shared Redis connection pool, optional pub/sub channels,
and health-check utilities.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine

import redis.asyncio as aioredis
from redis.asyncio import Redis
from redis.asyncio.client import PubSub

logger = logging.getLogger(__name__)

_instance: Redis | None = None
_pubsub_handlers: dict[str, list[Callable[..., Coroutine]]] = {}
_pubsub_task: asyncio.Task | None = None
_pubsub: PubSub | None = None


async def get_redis(
    url: str = "redis://localhost:6379/0",
    *,
    max_connections: int = 50,
    decode_responses: bool = True,
    socket_timeout: float = 5.0,
    socket_connect_timeout: float = 5.0,
    retry_on_timeout: bool = True,
) -> Redis:
    """Return the singleton Redis client, creating it on first call.

    Args:
        url: Redis connection URL.
        max_connections: Maximum pool connections.
        decode_responses: Decode bytes to str automatically.
        socket_timeout: Timeout for socket operations.
        socket_connect_timeout: Timeout for initial connection.
        retry_on_timeout: Retry commands that time out.

    Returns:
        A connected :class:`Redis` client.
    """
    global _instance

    if _instance is not None:
        return _instance

    pool = aioredis.ConnectionPool.from_url(
        url,
        max_connections=max_connections,
        decode_responses=decode_responses,
        socket_timeout=socket_timeout,
        socket_connect_timeout=socket_connect_timeout,
        retry_on_timeout=retry_on_timeout,
    )
    _instance = aioredis.Redis(connection_pool=pool)

    # Verify connectivity
    await _instance.ping()
    logger.info("Redis connection established: %s (pool_size=%d)", url, max_connections)

    return _instance


async def subscribe(
    channel: str,
    handler: Callable[[str, str], Coroutine[Any, Any, None]],
) -> None:
    """Subscribe to a Redis pub/sub channel.

    Args:
        channel: Channel name or glob pattern (e.g. ``events.*``).
        handler: Async callback ``(channel, message) -> None``.
    """
    global _pubsub, _pubsub_task

    if _instance is None:
        raise RuntimeError("Redis not initialized. Call get_redis() first.")

    if channel not in _pubsub_handlers:
        _pubsub_handlers[channel] = []
    _pubsub_handlers[channel].append(handler)

    if _pubsub is None:
        _pubsub = _instance.pubsub()

    if "*" in channel:
        await _pubsub.psubscribe(channel)
    else:
        await _pubsub.subscribe(channel)

    # Start the listener loop if not already running
    if _pubsub_task is None or _pubsub_task.done():
        _pubsub_task = asyncio.create_task(_pubsub_listener())

    logger.info("Subscribed to Redis channel: %s", channel)


async def publish(channel: str, message: str) -> int:
    """Publish a message to a Redis pub/sub channel.

    Args:
        channel: Target channel name.
        message: Message payload (typically JSON-encoded).

    Returns:
        Number of subscribers that received the message.
    """
    if _instance is None:
        raise RuntimeError("Redis not initialized. Call get_redis() first.")

    count = await _instance.publish(channel, message)
    logger.debug("Published to '%s' (%d receivers)", channel, count)
    return count


async def _pubsub_listener() -> None:
    """Internal loop that reads pub/sub messages and dispatches to handlers."""
    if _pubsub is None:
        return

    try:
        async for raw_message in _pubsub.listen():
            msg_type = raw_message.get("type", "")
            if msg_type not in ("message", "pmessage"):
                continue

            channel = raw_message.get("channel", "")
            data = raw_message.get("data", "")
            pattern = raw_message.get("pattern")

            # Dispatch to matching handlers
            lookup_key = pattern if pattern else channel
            handlers = _pubsub_handlers.get(lookup_key, [])
            for handler in handlers:
                try:
                    await handler(channel, data)
                except Exception:
                    logger.exception(
                        "Error in pub/sub handler for channel '%s'", channel
                    )
    except asyncio.CancelledError:
        logger.info("Pub/sub listener cancelled.")
    except Exception:
        logger.exception("Pub/sub listener crashed.")


async def health_check() -> bool:
    """Return True if the Redis connection is healthy."""
    if _instance is None:
        return False
    try:
        return await _instance.ping()
    except Exception:
        return False


async def close_redis() -> None:
    """Close the Redis connection and clean up pub/sub resources."""
    global _instance, _pubsub, _pubsub_task

    if _pubsub_task is not None and not _pubsub_task.done():
        _pubsub_task.cancel()
        try:
            await _pubsub_task
        except asyncio.CancelledError:
            pass
        _pubsub_task = None

    if _pubsub is not None:
        await _pubsub.close()
        _pubsub = None

    _pubsub_handlers.clear()

    if _instance is not None:
        await _instance.close()
        _instance = None
        logger.info("Redis connection closed.")
