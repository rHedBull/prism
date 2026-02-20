from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from clickhouse_driver import Client as ClickHouseClient

from analytics_service.models.metric import AggregatedMetric

logger = logging.getLogger(__name__)


class AggregationService:
    """Computes pre-aggregated metrics for dashboards and reporting."""

    def __init__(self, clickhouse: ClickHouseClient) -> None:
        self._ch = clickhouse

    async def compute_daily_rollups(self, target_date: date | None = None) -> int:
        if target_date is None:
            target_date = date.today() - timedelta(days=1)

        queries = [
            self._daily_event_counts(target_date),
            self._daily_active_users(target_date),
            self._daily_session_counts(target_date),
            self._daily_event_type_breakdown(target_date),
        ]

        total_metrics = 0
        for coro in queries:
            count = await coro
            total_metrics += count

        logger.info(
            "Computed %d daily rollup metrics for %s", total_metrics, target_date
        )
        return total_metrics

    async def compute_tenant_metrics(
        self, tenant_id: uuid.UUID, target_date: date | None = None
    ) -> list[AggregatedMetric]:
        if target_date is None:
            target_date = date.today() - timedelta(days=1)

        query = """
            SELECT
                event_type,
                count() as event_count,
                uniqExact(user_id) as unique_users,
                uniqExact(session_id) as unique_sessions
            FROM analytics_events
            WHERE tenant_id = %(tenant_id)s
                AND toDate(timestamp) = %(target_date)s
            GROUP BY event_type
        """
        params = {"tenant_id": str(tenant_id), "target_date": target_date}

        loop = asyncio.get_event_loop()
        rows = await loop.run_in_executor(
            None, lambda: self._ch.execute(query, params)
        )

        metrics: list[AggregatedMetric] = []
        now = datetime.now(timezone.utc)

        for event_type, event_count, unique_users, unique_sessions in rows:
            metrics.append(AggregatedMetric(
                tenant_id=tenant_id,
                metric_name=f"events.{event_type}.count",
                period=target_date,
                value=float(event_count),
                dimensions={"event_type": event_type},
                computed_at=now,
            ))
            metrics.append(AggregatedMetric(
                tenant_id=tenant_id,
                metric_name=f"events.{event_type}.unique_users",
                period=target_date,
                value=float(unique_users),
                dimensions={"event_type": event_type},
                computed_at=now,
            ))

        if metrics:
            await self._insert_metrics(metrics)

        return metrics

    async def _daily_event_counts(self, target_date: date) -> int:
        query = """
            SELECT
                tenant_id,
                count() as total_events
            FROM analytics_events
            WHERE toDate(timestamp) = %(target_date)s
            GROUP BY tenant_id
        """
        loop = asyncio.get_event_loop()
        rows = await loop.run_in_executor(
            None, lambda: self._ch.execute(query, {"target_date": target_date})
        )

        metrics = [
            AggregatedMetric(
                tenant_id=uuid.UUID(tid),
                metric_name="total_events",
                period=target_date,
                value=float(count),
                computed_at=datetime.now(timezone.utc),
            )
            for tid, count in rows
        ]

        if metrics:
            await self._insert_metrics(metrics)
        return len(metrics)

    async def _daily_active_users(self, target_date: date) -> int:
        query = """
            SELECT
                tenant_id,
                uniqExact(user_id) as dau
            FROM analytics_events
            WHERE toDate(timestamp) = %(target_date)s
            GROUP BY tenant_id
        """
        loop = asyncio.get_event_loop()
        rows = await loop.run_in_executor(
            None, lambda: self._ch.execute(query, {"target_date": target_date})
        )

        metrics = [
            AggregatedMetric(
                tenant_id=uuid.UUID(tid),
                metric_name="daily_active_users",
                period=target_date,
                value=float(dau),
                computed_at=datetime.now(timezone.utc),
            )
            for tid, dau in rows
        ]

        if metrics:
            await self._insert_metrics(metrics)
        return len(metrics)

    async def _daily_session_counts(self, target_date: date) -> int:
        query = """
            SELECT
                tenant_id,
                uniqExact(session_id) as sessions
            FROM analytics_events
            WHERE toDate(timestamp) = %(target_date)s
                AND session_id != ''
            GROUP BY tenant_id
        """
        loop = asyncio.get_event_loop()
        rows = await loop.run_in_executor(
            None, lambda: self._ch.execute(query, {"target_date": target_date})
        )

        metrics = [
            AggregatedMetric(
                tenant_id=uuid.UUID(tid),
                metric_name="daily_sessions",
                period=target_date,
                value=float(sessions),
                computed_at=datetime.now(timezone.utc),
            )
            for tid, sessions in rows
        ]

        if metrics:
            await self._insert_metrics(metrics)
        return len(metrics)

    async def _daily_event_type_breakdown(self, target_date: date) -> int:
        query = """
            SELECT
                tenant_id,
                event_type,
                count() as cnt
            FROM analytics_events
            WHERE toDate(timestamp) = %(target_date)s
            GROUP BY tenant_id, event_type
        """
        loop = asyncio.get_event_loop()
        rows = await loop.run_in_executor(
            None, lambda: self._ch.execute(query, {"target_date": target_date})
        )

        metrics = [
            AggregatedMetric(
                tenant_id=uuid.UUID(tid),
                metric_name="event_type_count",
                period=target_date,
                value=float(cnt),
                dimensions={"event_type": event_type},
                computed_at=datetime.now(timezone.utc),
            )
            for tid, event_type, cnt in rows
        ]

        if metrics:
            await self._insert_metrics(metrics)
        return len(metrics)

    async def _insert_metrics(self, metrics: list[AggregatedMetric]) -> None:
        rows = [m.to_clickhouse_row() for m in metrics]
        columns = AggregatedMetric.clickhouse_columns()

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._ch.execute(
                f"INSERT INTO aggregated_metrics ({', '.join(columns)}) VALUES",
                rows,
            ),
        )
