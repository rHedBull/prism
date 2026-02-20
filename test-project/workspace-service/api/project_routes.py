from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from workspace_service.main import get_db_session, get_redis
from workspace_service.models.project import ProjectStatus
from workspace_service.services.project_service import ProjectService

router = APIRouter(prefix="/workspaces/{workspace_id}/projects", tags=["projects"])


class CreateProjectRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


class UpdateProjectRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None


@router.post("/", status_code=201)
async def create_project(
    workspace_id: uuid.UUID,
    body: CreateProjectRequest,
    x_user_id: str = Header(...),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    service = ProjectService(db, get_redis())
    project = await service.create_project(
        workspace_id=workspace_id,
        name=body.name,
        description=body.description,
        created_by=uuid.UUID(x_user_id),
    )
    return project.to_dict()


@router.get("/")
async def list_projects(
    workspace_id: uuid.UUID,
    status: ProjectStatus | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    service = ProjectService(db, get_redis())
    projects = await service.list_projects(
        workspace_id=workspace_id, status=status, offset=offset, limit=limit
    )
    return [p.to_dict() for p in projects]


@router.get("/{project_id}")
async def get_project(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    service = ProjectService(db, get_redis())
    project = await service.get_project(project_id)
    if project is None or project.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Project not found")
    return project.to_dict()


@router.patch("/{project_id}")
async def update_project(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    body: UpdateProjectRequest,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    service = ProjectService(db, get_redis())
    project = await service.update_project(
        project_id, name=body.name, description=body.description
    )
    if project is None or project.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Project not found")
    return project.to_dict()


@router.post("/{project_id}/archive", status_code=200)
async def archive_project(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    service = ProjectService(db, get_redis())
    project = await service.archive_project(project_id)
    if project is None or project.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Project not found")
    return project.to_dict()


@router.post("/{project_id}/restore", status_code=200)
async def restore_project(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    service = ProjectService(db, get_redis())
    project = await service.restore_project(project_id)
    if project is None or project.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Project not found")
    return project.to_dict()
