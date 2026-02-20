from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import date, datetime
from typing import Any

from clickhouse_driver import Client as ClickHouseClient

logger = logging.getLogger(__name__)


class QueryService:
    """Executes analytics queries against ClickHouse."""

    def __init__(self, clickhouse: ClickHouseClient) -> None:
        self._ch = clickhouse

    async def run_query(
        self,
        tenant_id: uuid.UUID,
        event_types: list[str] | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        group_by: list[str] | None = None,
        filters: dict[str, Any] | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        conditions = ["tenant_id = %(tenant_id)s"]
        params: dict[str, Any] = {"tenant_id": str(tenant_id)}

        if event_types:
            conditions.append("event_type IN %(event_types)s")
            params["event_types"] = event_types

        if start_date:
            conditions.append("timestamp >= %(start_date)s")
            params["start_date"] = start_date

        if end_date:
            conditions.append("timestamp <= %(end_date)s")
            params["end_date"] = end_date

        if filters:
            for key, value in filters.items():
                safe_key = key.replace(".", "_")
                conditions.append(
                    f"JSONExtractString(properties, %(filter_key_{safe_key})s) = %(filter_val_{safe_key})s"
                )
                params[f"filter_key_{safe_key}"] = key
                params[f"filter_val_{safe_key}"] = str(value)

        where_clause = " AND ".join(conditions)

        if group_by:
            select_cols = ", ".join(group_by) + ", count() as count"
            group_clause = f"GROUP BY {', '.join(group_by)}"
            order_clause = "ORDER BY count DESC"
        else:
            select_cols = "timestamp, user_id, event_type, properties, session_id"
            group_clause = ""
            order_clause = "ORDER BY timestamp DESC"

        query = f"""
            SELECT {select_cols}
            FROM analytics_events
            WHERE {where_clause}
            {group_clause}
            {order_clause}
            LIMIT %(limit)s
        """
        params["limit"] = limit

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self._ch.execute(query, params, with_column_types=True),
        )

        rows, columns = result
        col_names = [c[0] for c in columns]
        return [dict(zip(col_names, row)) for row in rows]

    async def get_timeseries(
        self,
        tenant_id: uuid.UUID,
        event_type: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "day",
    ) -> list[dict[str, Any]]:
        interval_func = {
            "hour": "toStartOfHour",
            "day": "toDate",
            "week": "toMonday",
            "month": "toStartOfMonth",
        }.get(interval, "toDate")

        query = f"""
            SELECT
                {interval_func}(timestamp) as period,
                count() as event_count,
                uniqExact(user_id) as unique_users
            FROM analytics_events
            WHERE tenant_id = %(tenant_id)s
                AND event_type = %(event_type)s
                AND timestamp >= %(start_date)s
                AND timestamp <= %(end_date)s
            GROUP BY period
            ORDER BY period ASC
        """
        params = {
            "tenant_id": str(tenant_id),
            "event_type": event_type,
            "start_date": start_date,
            "end_date": end_date,
        }

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self._ch.execute(query, params, with_column_types=True),
        )

        rows, columns = result
        col_names = [c[0] for c in columns]
        return [dict(zip(col_names, row)) for row in rows]

    async def get_funnel(
        self,
        tenant_id: uuid.UUID,
        steps: list[str],
        start_date: datetime,
        end_date: datetime,
        window_seconds: int = 86400,
    ) -> list[dict[str, Any]]:
        if len(steps) < 2:
            raise ValueError("Funnel requires at least 2 steps")

        step_conditions = []
        for i, step in enumerate(steps):
            step_conditions.append(
                f"countIf(event_type = %(step_{i})s) > 0 as has_step_{i}"
            )

        query = f"""
            SELECT
                session_id,
                {', '.join(step_conditions)}
            FROM analytics_events
            WHERE tenant_id = %(tenant_id)s
                AND timestamp >= %(start_date)s
                AND timestamp <= %(end_date)s
                AND event_type IN %(step_list)s
            GROUP BY session_id
        """
        params: dict[str, Any] = {
            "tenant_id": str(tenant_id),
            "start_date": start_date,
            "end_date": end_date,
            "step_list": steps,
        }
        for i, step in enumerate(steps):
            params[f"step_{i}"] = step

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self._ch.execute(query, params, with_column_types=True),
        )

        rows, _ = result
        funnel_results = []
        for i, step in enumerate(steps):
            count = sum(1 for row in rows if row[i + 1])  # +1 to skip session_id
            conversion = (count / len(rows) * 100) if rows else 0
            funnel_results.append({
                "step": step,
                "step_index": i,
                "count": count,
                "conversion_rate": round(conversion, 2),
            })

        return funnel_results
