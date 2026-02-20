from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query

logger_name = __name__

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_query_service = None
_aggregation_service = None


def set_services(query_service: Any, aggregation_service: Any) -> None:
    global _query_service, _aggregation_service
    _query_service = query_service
    _aggregation_service = aggregation_service


@router.get("/overview")
async def dashboard_overview(
    x_tenant_id: str = Header(...),
    days: int = Query(30, ge=1, le=365),
) -> dict[str, Any]:
    if _query_service is None:
        raise HTTPException(status_code=503, detail="Services not initialized")

    tenant_id = uuid.UUID(x_tenant_id)
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    total_events_task = _query_service.run_query(
        tenant_id=tenant_id,
        start_date=start,
        end_date=end,
        group_by=["event_type"],
        limit=100,
    )
    active_users_task = _query_service.get_timeseries(
        tenant_id=tenant_id,
        event_type="page_view",
        start_date=start,
        end_date=end,
        interval="day",
    )

    event_breakdown, user_activity = await asyncio.gather(
        total_events_task, active_users_task
    )

    return {
        "period": {"start": start.isoformat(), "end": end.isoformat(), "days": days},
        "event_breakdown": event_breakdown,
        "user_activity": user_activity,
    }


@router.get("/usage")
async def dashboard_usage(
    x_tenant_id: str = Header(...),
    days: int = Query(30, ge=1, le=365),
) -> dict[str, Any]:
    if _query_service is None:
        raise HTTPException(status_code=503, detail="Services not initialized")

    tenant_id = uuid.UUID(x_tenant_id)
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    api_usage = await _query_service.get_timeseries(
        tenant_id=tenant_id,
        event_type="api_call",
        start_date=start,
        end_date=end,
        interval="day",
    )

    feature_usage = await _query_service.run_query(
        tenant_id=tenant_id,
        event_types=["feature_used"],
        start_date=start,
        end_date=end,
        group_by=["event_type"],
        filters=None,
        limit=50,
    )

    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "api_usage": api_usage,
        "feature_usage": feature_usage,
    }


@router.get("/activity")
async def dashboard_activity(
    x_tenant_id: str = Header(...),
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    if _query_service is None:
        raise HTTPException(status_code=503, detail="Services not initialized")

    tenant_id = uuid.UUID(x_tenant_id)
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    recent_events = await _query_service.run_query(
        tenant_id=tenant_id,
        start_date=start,
        end_date=end,
        limit=limit,
    )

    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "recent_events": recent_events,
        "count": len(recent_events),
    }
