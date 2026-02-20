"""Kafka producer for cross-service event streaming.

Wraps ``aiokafka`` with serialization, partitioning, delivery guarantees,
and graceful shutdown.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from aiokafka import AIOKafkaProducer

from shared.events.event_bus import Event

logger = logging.getLogger(__name__)

_producer: AIOKafkaProducer | None = None


async def create_producer(
    bootstrap_servers: str | list[str] = "localhost:9092",
    *,
    client_id: str = "prism-producer",
    acks: str | int = "all",
    compression_type: str = "lz4",
    max_batch_size: int = 16_384,
    linger_ms: int = 10,
    max_request_size: int = 1_048_576,
    enable_idempotence: bool = True,
    retries: int = 5,
) -> AIOKafkaProducer:
    """Initialize and start the Kafka producer.

    Args:
        bootstrap_servers: Kafka broker address(es).
        client_id: Producer client identifier.
        acks: Acknowledgement level ('all', 0, 1).
        compression_type: Message compression (none, gzip, snappy, lz4, zstd).
        max_batch_size: Maximum batch size in bytes.
        linger_ms: Time to wait for batch accumulation.
        max_request_size: Maximum request size in bytes.
        enable_idempotence: Enable exactly-once semantics.
        retries: Number of send retries.

    Returns:
        A started :class:`AIOKafkaProducer`.
    """
    global _producer

    if _producer is not None:
        return _producer

    _producer = AIOKafkaProducer(
        bootstrap_servers=bootstrap_servers,
        client_id=client_id,
        acks=acks,
        compression_type=compression_type,
        max_batch_size=max_batch_size,
        linger_ms=linger_ms,
        max_request_size=max_request_size,
        enable_idempotence=enable_idempotence,
        retry_backoff_ms=200,
        value_serializer=_serialize_value,
        key_serializer=_serialize_key,
    )

    await _producer.start()
    logger.info(
        "Kafka producer started: %s (client_id=%s, acks=%s)",
        bootstrap_servers,
        client_id,
        acks,
    )
    return _producer


def _serialize_value(value: Any) -> bytes:
    """Serialize a value to JSON bytes."""
    return json.dumps(value, default=str).encode("utf-8")


def _serialize_key(key: Any) -> bytes | None:
    """Serialize a partition key to bytes."""
    if key is None:
        return None
    return str(key).encode("utf-8")


def _get_producer() -> AIOKafkaProducer:
    """Return the active producer or raise if not started."""
    if _producer is None:
        raise RuntimeError("Kafka producer not initialized. Call create_producer() first.")
    return _producer


async def send_event(
    topic: str,
    event: Event,
    *,
    key: str | None = None,
    partition: int | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Publish an event to a Kafka topic.

    Args:
        topic: Kafka topic name.
        event: Event to publish.
        key: Optional partition key (defaults to event source_service).
        partition: Explicit partition number (overrides key-based routing).
        headers: Additional Kafka headers as string key-value pairs.

    Returns:
        Dict with ``topic``, ``partition``, ``offset``, and ``timestamp``.
    """
    producer = _get_producer()

    kafka_key = key or event.source_service

    kafka_headers = [
        ("event_type", event.type.encode()),
        ("event_id", event.event_id.encode()),
        ("source_service", event.source_service.encode()),
        ("timestamp", event.timestamp.isoformat().encode()),
    ]
    if event.correlation_id:
        kafka_headers.append(("correlation_id", event.correlation_id.encode()))
    if headers:
        kafka_headers.extend(
            (k, v.encode()) for k, v in headers.items()
        )

    send_kwargs: dict[str, Any] = {
        "topic": topic,
        "value": event.to_dict(),
        "key": kafka_key,
        "headers": kafka_headers,
    }
    if partition is not None:
        send_kwargs["partition"] = partition

    record_metadata = await producer.send_and_wait(**send_kwargs)

    result = {
        "topic": record_metadata.topic,
        "partition": record_metadata.partition,
        "offset": record_metadata.offset,
        "timestamp": record_metadata.timestamp,
    }

    logger.debug(
        "Sent event '%s' (%s) to %s[%d]@%d",
        event.type,
        event.event_id,
        result["topic"],
        result["partition"],
        result["offset"],
    )
    return result


async def send_raw(
    topic: str,
    value: dict[str, Any],
    *,
    key: str | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Publish a raw dict payload without wrapping in an Event.

    Useful for legacy or third-party topic schemas.
    """
    producer = _get_producer()

    kafka_headers = []
    if headers:
        kafka_headers = [(k, v.encode()) for k, v in headers.items()]

    record_metadata = await producer.send_and_wait(
        topic=topic,
        value=value,
        key=key,
        headers=kafka_headers or None,
    )

    return {
        "topic": record_metadata.topic,
        "partition": record_metadata.partition,
        "offset": record_metadata.offset,
        "timestamp": record_metadata.timestamp,
    }


async def flush(timeout: float = 30.0) -> None:
    """Flush all buffered messages, blocking until delivery or timeout.

    Args:
        timeout: Maximum seconds to wait for delivery.
    """
    producer = _get_producer()
    await producer.flush(timeout=timeout)
    logger.debug("Kafka producer flushed.")


async def close() -> None:
    """Stop the Kafka producer and release resources."""
    global _producer

    if _producer is not None:
        await _producer.flush(timeout=10.0)
        await _producer.stop()
        _producer = None
        logger.info("Kafka producer stopped.")
