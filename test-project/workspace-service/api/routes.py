from __future__ import annotations

from fastapi import APIRouter

from workspace_service.api.member_routes import router as member_router
from workspace_service.api.project_routes import router as project_router
from workspace_service.api.workspace_routes import router as workspace_router

router = APIRouter()
router.include_router(workspace_router)
router.include_router(project_router)
router.include_router(member_router)
