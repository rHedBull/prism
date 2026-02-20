from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# ClickHouse DDL for reference:
# CREATE TABLE analytics_events (
#     timestamp DateTime64(3, 'UTC'),
#     tenant_id UUID,
#     user_id UUID,
#     event_type LowCardinality(String),
#     properties String,  -- JSON encoded
#     session_id UUID,
#     _partition_key Date DEFAULT toDate(timestamp)
# ) ENGINE = MergeTree()
# PARTITION BY _partition_key
# ORDER BY (tenant_id, event_type, timestamp)
# TTL timestamp + INTERVAL 90 DAY


class AnalyticsEvent(BaseModel):
    """Represents a single analytics event tracked by the platform."""

    timestamp: datetime
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    event_type: str
    properties: dict[str, Any] = Field(default_factory=dict)
    session_id: uuid.UUID | None = None

    def to_clickhouse_row(self) -> tuple[Any, ...]:
        import json

        return (
            self.timestamp,
            str(self.tenant_id),
            str(self.user_id),
            self.event_type,
            json.dumps(self.properties),
            str(self.session_id) if self.session_id else "",
        )

    @classmethod
    def clickhouse_columns(cls) -> list[str]:
        return [
            "timestamp",
            "tenant_id",
            "user_id",
            "event_type",
            "properties",
            "session_id",
        ]
