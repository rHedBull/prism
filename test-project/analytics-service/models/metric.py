from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

# ClickHouse DDL for reference:
# CREATE TABLE aggregated_metrics (
#     tenant_id UUID,
#     metric_name LowCardinality(String),
#     period Date,
#     value Float64,
#     dimensions String,  -- JSON encoded
#     computed_at DateTime64(3, 'UTC')
# ) ENGINE = ReplacingMergeTree(computed_at)
# PARTITION BY toYYYYMM(period)
# ORDER BY (tenant_id, metric_name, period, dimensions)


class AggregatedMetric(BaseModel):
    """Pre-computed metric rollup for dashboards and reporting."""

    tenant_id: uuid.UUID
    metric_name: str
    period: date
    value: float
    dimensions: dict[str, Any] = Field(default_factory=dict)
    computed_at: datetime | None = None

    def to_clickhouse_row(self) -> tuple[Any, ...]:
        import json
        from datetime import datetime, timezone

        return (
            str(self.tenant_id),
            self.metric_name,
            self.period,
            self.value,
            json.dumps(self.dimensions),
            self.computed_at or datetime.now(timezone.utc),
        )

    @classmethod
    def clickhouse_columns(cls) -> list[str]:
        return [
            "tenant_id",
            "metric_name",
            "period",
            "value",
            "dimensions",
            "computed_at",
        ]
