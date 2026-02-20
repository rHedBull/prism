from __future__ import annotations

import asyncio
import json
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Any

from clickhouse_driver import Client as ClickHouseClient

from analytics_service.config.settings import settings
from analytics_service.models.event import AnalyticsEvent

logger = logging.getLogger(__name__)


class IngestionService:
    """Handles buffered ingestion of analytics events into ClickHouse."""

    def __init__(self, clickhouse: ClickHouseClient) -> None:
        self._ch = clickhouse
        self._buffer: deque[AnalyticsEvent] = deque()
        self._lock = asyncio.Lock()
        self._flush_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self._flush_task = asyncio.create_task(self._periodic_flush())
        logger.info("Ingestion service started with batch_size=%d", settings.batch_size)

    async def stop(self) -> None:
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        await self._flush_buffer()
        logger.info("Ingestion service stopped, final buffer flushed")

    async def ingest_event(self, event: AnalyticsEvent) -> None:
        async with self._lock:
            self._buffer.append(event)

        if len(self._buffer) >= settings.batch_size:
            await self._flush_buffer()

    async def batch_insert(self, events: list[AnalyticsEvent]) -> int:
        if not events:
            return 0

        rows = [e.to_clickhouse_row() for e in events]
        columns = AnalyticsEvent.clickhouse_columns()

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._ch.execute(
                    f"INSERT INTO analytics_events ({', '.join(columns)}) VALUES",
                    rows,
                ),
            )
            logger.info("Batch inserted %d events into ClickHouse", len(rows))
            return len(rows)
        except Exception as exc:
            logger.error("Failed to batch insert %d events: %s", len(rows), exc)
            raise

    async def _flush_buffer(self) -> None:
        async with self._lock:
            if not self._buffer:
                return
            events = list(self._buffer)
            self._buffer.clear()

        await self.batch_insert(events)

    async def _periodic_flush(self) -> None:
        while True:
            await asyncio.sleep(settings.batch_flush_interval_seconds)
            try:
                await self._flush_buffer()
            except Exception as exc:
                logger.error("Periodic flush failed: %s", exc)
