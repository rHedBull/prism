from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from billing_service.models.usage_record import UsageRecord


class UsageService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def record_usage(
        self,
        tenant_id: uuid.UUID,
        metric: str,
        quantity: float,
        recorded_at: datetime | None = None,
    ) -> UsageRecord:
        record = UsageRecord(
            tenant_id=tenant_id,
            metric=metric,
            quantity=quantity,
            recorded_at=recorded_at or datetime.now(timezone.utc),
        )
        self._db.add(record)
        await self._db.commit()
        await self._db.refresh(record)
        return record

    async def get_usage_summary(
        self,
        tenant_id: uuid.UUID,
        since: datetime | None = None,
    ) -> dict[str, Any]:
        if since is None:
            since = datetime.now(timezone.utc) - timedelta(days=30)

        result = await self._db.execute(
            select(
                UsageRecord.metric,
                func.sum(UsageRecord.quantity).label("total"),
                func.count(UsageRecord.id).label("count"),
                func.max(UsageRecord.recorded_at).label("last_recorded"),
            )
            .where(
                UsageRecord.tenant_id == tenant_id,
                UsageRecord.recorded_at >= since,
            )
            .group_by(UsageRecord.metric)
        )

        summary: dict[str, Any] = {}
        for row in result.all():
            summary[row.metric] = {
                "total": float(row.total),
                "count": row.count,
                "last_recorded": row.last_recorded.isoformat() if row.last_recorded else None,
            }
        return summary

    async def check_quota(
        self,
        tenant_id: uuid.UUID,
        metric: str,
        quota: int,
    ) -> dict[str, Any]:
        if quota == -1:
            return {"within_quota": True, "used": 0, "quota": -1, "metric": metric}

        since = datetime.now(timezone.utc) - timedelta(days=30)
        result = await self._db.execute(
            select(func.coalesce(func.sum(UsageRecord.quantity), 0.0))
            .where(
                UsageRecord.tenant_id == tenant_id,
                UsageRecord.metric == metric,
                UsageRecord.recorded_at >= since,
            )
        )
        used = float(result.scalar_one())

        return {
            "within_quota": used < quota,
            "used": used,
            "quota": quota,
            "metric": metric,
            "remaining": max(0, quota - used),
        }
