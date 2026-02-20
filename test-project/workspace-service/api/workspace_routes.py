from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from workspace_service.main import get_db_session, get_redis
from workspace_service.services.workspace_service import WorkspaceService

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    settings: dict[str, Any] = Field(default_factory=dict)


class UpdateWorkspaceRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    settings: dict[str, Any] | None = None


@router.post("/", status_code=201)
async def create_workspace(
    body: CreateWorkspaceRequest,
    x_tenant_id: str = Header(...),
    x_user_id: str = Header(...),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    service = WorkspaceService(db, get_redis())
    try:
        workspace = await service.create_workspace(
            tenant_id=uuid.UUID(x_tenant_id),
            name=body.name,
            created_by=uuid.UUID(x_user_id),
            workspace_settings=body.settings,
        )
        return workspace.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/")
async def list_workspaces(
    x_tenant_id: str = Header(...),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    service = WorkspaceService(db, get_redis())
    workspaces = await service.list_workspaces(
        tenant_id=uuid.UUID(x_tenant_id), offset=offset, limit=limit
    )
    return [w.to_dict() for w in workspaces]


@router.get("/{workspace_id}")
async def get_workspace(
    workspace_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    service = WorkspaceService(db, get_redis())
    workspace = await service.get_workspace(workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace.to_dict()


@router.patch("/{workspace_id}")
async def update_workspace(
    workspace_id: uuid.UUID,
    body: UpdateWorkspaceRequest,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    service = WorkspaceService(db, get_redis())
    workspace = await service.update_workspace(
        workspace_id, name=body.name, workspace_settings=body.settings
    )
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace.to_dict()


@router.delete("/{workspace_id}", status_code=204)
async def delete_workspace(
    workspace_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    service = WorkspaceService(db, get_redis())
    deleted = await service.delete_workspace(workspace_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Workspace not found")
