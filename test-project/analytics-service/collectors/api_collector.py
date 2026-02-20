from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from analytics_service.models.event import AnalyticsEvent
from analytics_service.services.ingestion_service import IngestionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/collect", tags=["collection"])

# This will be set during app startup
_ingestion_service: IngestionService | None = None


def set_ingestion_service(service: IngestionService) -> None:
    global _ingestion_service
    _ingestion_service = service


class IngestEventRequest(BaseModel):
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    event_type: str = Field(..., min_length=1, max_length=255)
    properties: dict[str, Any] = Field(default_factory=dict)
    session_id: uuid.UUID | None = None
    timestamp: datetime | None = None


class BatchIngestRequest(BaseModel):
    events: list[IngestEventRequest] = Field(..., min_length=1, max_length=500)


@router.post("/event", status_code=202)
async def collect_event(body: IngestEventRequest) -> dict[str, str]:
    if _ingestion_service is None:
        raise HTTPException(status_code=503, detail="Ingestion service not initialized")

    event = AnalyticsEvent(
        timestamp=body.timestamp or datetime.now(timezone.utc),
        tenant_id=body.tenant_id,
        user_id=body.user_id,
        event_type=body.event_type,
        properties=body.properties,
        session_id=body.session_id,
    )

    await _ingestion_service.ingest_event(event)
    return {"status": "accepted"}


@router.post("/batch", status_code=202)
async def collect_batch(body: BatchIngestRequest) -> dict[str, Any]:
    if _ingestion_service is None:
        raise HTTPException(status_code=503, detail="Ingestion service not initialized")

    events = [
        AnalyticsEvent(
            timestamp=e.timestamp or datetime.now(timezone.utc),
            tenant_id=e.tenant_id,
            user_id=e.user_id,
            event_type=e.event_type,
            properties=e.properties,
            session_id=e.session_id,
        )
        for e in body.events
    ]

    count = await _ingestion_service.batch_insert(events)
    return {"status": "accepted", "count": count}
