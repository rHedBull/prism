from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from aiokafka import AIOKafkaConsumer

from analytics_service.config.settings import settings
from analytics_service.models.event import AnalyticsEvent
from analytics_service.services.ingestion_service import IngestionService

logger = logging.getLogger(__name__)


class KafkaCollector:
    """Consumes platform events from Kafka and ingests them into ClickHouse."""

    def __init__(self, ingestion_service: IngestionService) -> None:
        self._ingestion = ingestion_service
        self._consumer: AIOKafkaConsumer | None = None
        self._running = False

    async def start(self) -> None:
        self._consumer = AIOKafkaConsumer(
            settings.kafka_events_topic,
            bootstrap_servers=settings.kafka_brokers,
            group_id=settings.kafka_consumer_group,
            auto_offset_reset="latest",
            enable_auto_commit=True,
            auto_commit_interval_ms=5000,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        )

        await self._consumer.start()
        self._running = True
        logger.info(
            "Kafka collector started, consuming from topic '%s'",
            settings.kafka_events_topic,
        )

        asyncio.create_task(self._consume_loop())

    async def stop(self) -> None:
        self._running = False
        if self._consumer:
            await self._consumer.stop()
        logger.info("Kafka collector stopped")

    async def _consume_loop(self) -> None:
        assert self._consumer is not None

        while self._running:
            try:
                async for message in self._consumer:
                    if not self._running:
                        break

                    try:
                        event = self._transform_message(message.value)
                        if event is not None:
                            await self._ingestion.ingest_event(event)
                    except Exception as exc:
                        logger.error(
                            "Failed to process message at offset %d: %s",
                            message.offset,
                            exc,
                        )
            except Exception as exc:
                logger.error("Kafka consumer loop error: %s", exc)
                if self._running:
                    await asyncio.sleep(5)

    def _transform_message(self, raw: dict[str, Any]) -> AnalyticsEvent | None:
        """Transform a raw Kafka message into an AnalyticsEvent."""
        required_fields = {"event_type", "tenant_id", "user_id"}
        if not required_fields.issubset(raw.keys()):
            logger.warning("Dropping message missing required fields: %s", raw.keys())
            return None

        timestamp_str = raw.get("timestamp")
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str)
            except ValueError:
                timestamp = datetime.now(timezone.utc)
        else:
            timestamp = datetime.now(timezone.utc)

        properties = raw.get("properties", {})
        if not isinstance(properties, dict):
            properties = {"raw_value": str(properties)}

        session_id_str = raw.get("session_id")
        session_id = uuid.UUID(session_id_str) if session_id_str else None

        return AnalyticsEvent(
            timestamp=timestamp,
            tenant_id=uuid.UUID(raw["tenant_id"]),
            user_id=uuid.UUID(raw["user_id"]),
            event_type=raw["event_type"],
            properties=properties,
            session_id=session_id,
        )
