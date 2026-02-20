from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from notification_service.models.notification import (
    Notification,
    NotificationChannel,
    NotificationStatus,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])

# These will be wired during startup
_get_db = None
_dispatcher = None


def set_dependencies(get_db: Any, dispatcher: Any) -> None:
    global _get_db, _dispatcher
    _get_db = get_db
    _dispatcher = dispatcher


class SendNotificationRequest(BaseModel):
    user_id: uuid.UUID
    channel: NotificationChannel = NotificationChannel.EMAIL
    subject: str = Field(..., min_length=1, max_length=500)
    body: str = Field(..., min_length=1)
    event_type: str = "general"
    metadata: dict[str, Any] = Field(default_factory=dict)
    template_name: str | None = None
    template_context: dict[str, Any] | None = None


@router.post("/send", status_code=202)
async def send_notification(
    body: SendNotificationRequest,
    x_tenant_id: str = Header(...),
    db: AsyncSession = Depends(lambda: _get_db()),
) -> dict[str, Any]:
    if _dispatcher is None:
        raise HTTPException(status_code=503, detail="Dispatcher not initialized")

    notification = await _dispatcher.dispatch_notification(
        tenant_id=uuid.UUID(x_tenant_id),
        user_id=body.user_id,
        channel=body.channel,
        subject=body.subject,
        body=body.body,
        event_type=body.event_type,
        metadata=body.metadata,
        template_name=body.template_name,
        template_context=body.template_context,
    )
    return notification.to_dict()


@router.get("/")
async def list_notifications(
    x_tenant_id: str = Header(...),
    x_user_id: str = Header(...),
    status: NotificationStatus | None = Query(None),
    channel: NotificationChannel | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(lambda: _get_db()),
) -> list[dict[str, Any]]:
    query = select(Notification).where(
        Notification.user_id == uuid.UUID(x_user_id),
        Notification.tenant_id == uuid.UUID(x_tenant_id),
    )

    if status is not None:
        query = query.where(Notification.status == status)
    if channel is not None:
        query = query.where(Notification.channel == channel)

    query = query.order_by(Notification.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    notifications = result.scalars().all()
    return [n.to_dict() for n in notifications]


@router.patch("/{notification_id}/read")
async def mark_notification_read(
    notification_id: uuid.UUID,
    x_user_id: str = Header(...),
    db: AsyncSession = Depends(lambda: _get_db()),
) -> dict[str, Any]:
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == uuid.UUID(x_user_id),
        )
    )
    notification = result.scalar_one_or_none()
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.read_at = datetime.now(timezone.utc)
    await db.flush()
    return notification.to_dict()
