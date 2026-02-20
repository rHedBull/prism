from __future__ import annotations

from fastapi import APIRouter

from file_service.api.file_routes import router as file_router

router = APIRouter()
router.include_router(file_router)
