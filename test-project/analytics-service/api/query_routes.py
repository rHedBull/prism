from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

logger_name = __name__

router = APIRouter(prefix="/analytics", tags=["analytics-queries"])

# Set during startup
_query_service = None


def set_query_service(service: Any) -> None:
    global _query_service
    _query_service = service


class AnalyticsQueryRequest(BaseModel):
    event_types: list[str] | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    group_by: list[str] | None = None
    filters: dict[str, Any] | None = None
    limit: int = Field(1000, ge=1, le=10000)


class TimeseriesRequest(BaseModel):
    event_type: str
    start_date: datetime
    end_date: datetime
    interval: str = Field("day", pattern="^(hour|day|week|month)$")


class FunnelRequest(BaseModel):
    steps: list[str] = Field(..., min_length=2, max_length=20)
    start_date: datetime
    end_date: datetime
    window_seconds: int = Field(86400, ge=60, le=604800)


@router.post("/query")
async def run_analytics_query(
    body: AnalyticsQueryRequest,
    x_tenant_id: str = Header(...),
) -> dict[str, Any]:
    if _query_service is None:
        raise HTTPException(status_code=503, detail="Query service not initialized")

    results = await _query_service.run_query(
        tenant_id=uuid.UUID(x_tenant_id),
        event_types=body.event_types,
        start_date=body.start_date,
        end_date=body.end_date,
        group_by=body.group_by,
        filters=body.filters,
        limit=body.limit,
    )
    return {"results": results, "count": len(results)}


@router.post("/timeseries")
async def get_timeseries(
    body: TimeseriesRequest,
    x_tenant_id: str = Header(...),
) -> dict[str, Any]:
    if _query_service is None:
        raise HTTPException(status_code=503, detail="Query service not initialized")

    data = await _query_service.get_timeseries(
        tenant_id=uuid.UUID(x_tenant_id),
        event_type=body.event_type,
        start_date=body.start_date,
        end_date=body.end_date,
        interval=body.interval,
    )
    return {"data": data, "interval": body.interval}


@router.post("/funnel")
async def get_funnel(
    body: FunnelRequest,
    x_tenant_id: str = Header(...),
) -> dict[str, Any]:
    if _query_service is None:
        raise HTTPException(status_code=503, detail="Query service not initialized")

    try:
        results = await _query_service.get_funnel(
            tenant_id=uuid.UUID(x_tenant_id),
            steps=body.steps,
            start_date=body.start_date,
            end_date=body.end_date,
            window_seconds=body.window_seconds,
        )
        return {"funnel": results, "steps": len(body.steps)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/events")
async def get_events(
    x_tenant_id: str = Header(...),
    event_type: str | None = Query(None),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> dict[str, Any]:
    if _query_service is None:
        raise HTTPException(status_code=503, detail="Query service not initialized")

    event_types = [event_type] if event_type else None
    results = await _query_service.run_query(
        tenant_id=uuid.UUID(x_tenant_id),
        event_types=event_types,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )
    return {"events": results, "count": len(results), "offset": offset}
