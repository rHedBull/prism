from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from workspace_service.main import get_db_session, get_redis
from workspace_service.models.member import MemberRole
from workspace_service.services.member_service import MemberService

router = APIRouter(prefix="/workspaces/{workspace_id}/members", tags=["members"])


class InviteMemberRequest(BaseModel):
    user_id: uuid.UUID
    role: MemberRole = MemberRole.MEMBER


class UpdateRoleRequest(BaseModel):
    role: MemberRole


@router.post("/invite", status_code=201)
async def invite_member(
    workspace_id: uuid.UUID,
    body: InviteMemberRequest,
    x_user_id: str = Header(...),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    service = MemberService(db, get_redis())
    try:
        member = await service.invite_member(
            workspace_id=workspace_id,
            user_id=body.user_id,
            role=body.role,
            invited_by=uuid.UUID(x_user_id),
        )
        return member.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.delete("/{user_id}", status_code=204)
async def remove_member(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    x_user_id: str = Header(...),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    service = MemberService(db, get_redis())
    try:
        removed = await service.remove_member(
            workspace_id=workspace_id,
            user_id=user_id,
            removed_by=uuid.UUID(x_user_id),
        )
        if not removed:
            raise HTTPException(status_code=404, detail="Member not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.patch("/{user_id}/role")
async def update_member_role(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    body: UpdateRoleRequest,
    x_user_id: str = Header(...),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    service = MemberService(db, get_redis())
    try:
        member = await service.update_role(
            workspace_id=workspace_id,
            user_id=user_id,
            new_role=body.role,
            updated_by=uuid.UUID(x_user_id),
        )
        if member is None:
            raise HTTPException(status_code=404, detail="Member not found")
        return member.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.get("/")
async def list_members(
    workspace_id: uuid.UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    service = MemberService(db, get_redis())
    members = await service.list_members(
        workspace_id=workspace_id, offset=offset, limit=limit
    )
    return [m.to_dict() for m in members]
