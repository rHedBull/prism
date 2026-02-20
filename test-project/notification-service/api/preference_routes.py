from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from notification_service.models.preference import NotificationPreference

router = APIRouter(prefix="/preferences", tags=["preferences"])

_get_db = None


def set_dependencies(get_db: Any) -> None:
    global _get_db
    _get_db = get_db


class PreferenceUpdate(BaseModel):
    channel: str
    event_type: str
    enabled: bool


class BulkPreferenceUpdate(BaseModel):
    preferences: list[PreferenceUpdate] = Field(..., min_length=1, max_length=100)


@router.get("/")
async def get_preferences(
    x_user_id: str = Header(...),
    db: AsyncSession = Depends(lambda: _get_db()),
) -> list[dict[str, Any]]:
    result = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == uuid.UUID(x_user_id)
        )
    )
    preferences = result.scalars().all()
    return [p.to_dict() for p in preferences]


@router.put("/")
async def update_preferences(
    body: BulkPreferenceUpdate,
    x_user_id: str = Header(...),
    db: AsyncSession = Depends(lambda: _get_db()),
) -> list[dict[str, Any]]:
    user_id = uuid.UUID(x_user_id)
    updated: list[dict[str, Any]] = []

    for pref_update in body.preferences:
        result = await db.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id,
                NotificationPreference.channel == pref_update.channel,
                NotificationPreference.event_type == pref_update.event_type,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.enabled = pref_update.enabled
        else:
            existing = NotificationPreference(
                user_id=user_id,
                channel=pref_update.channel,
                event_type=pref_update.event_type,
                enabled=pref_update.enabled,
            )
            db.add(existing)

        await db.flush()
        updated.append(existing.to_dict())

    return updated
