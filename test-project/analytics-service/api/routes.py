from __future__ import annotations

from fastapi import APIRouter

from analytics_service.api.dashboard_routes import router as dashboard_router
from analytics_service.api.query_routes import router as query_router

router = APIRouter()
router.include_router(query_router)
router.include_router(dashboard_router)
