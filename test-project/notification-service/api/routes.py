from __future__ import annotations

from fastapi import APIRouter

from notification_service.api.notification_routes import router as notification_router
from notification_service.api.preference_routes import router as preference_router

router = APIRouter()
router.include_router(notification_router)
router.include_router(preference_router)
