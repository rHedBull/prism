from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.models.user import User
from auth_service.services.permission_service import PermissionService
from auth_service.services.token_service import TokenService

router = APIRouter(prefix="/users")


class UpdateProfileRequest(BaseModel):
    name: str | None = None
    avatar_url: str | None = None


class AssignRoleRequest(BaseModel):
    role_id: str
    tenant_id: str


async def _get_db(request: Request) -> AsyncSession:
    async with request.app.state.db_pool() as session:
        yield session


async def _get_current_user(
    request: Request,
    db: AsyncSession = Depends(_get_db),
) -> User:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token"
        )
    token = auth_header.removeprefix("Bearer ")
    token_svc = TokenService(request.app.state.redis)
    try:
        payload = await token_svc.is_blacklisted(token)
        if payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked"
            )
        payload = token_svc.decode_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        )

    result = await db.execute(select(User).where(User.id == uuid.UUID(payload["sub"])))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    return user


@router.get("/me")
async def get_me(user: User = Depends(_get_current_user)) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "avatar_url": user.avatar_url,
        "created_at": user.created_at.isoformat(),
        "mfa_enabled": user.mfa_enabled,
        "roles": [
            {"role": ur.role.name, "tenant_id": str(ur.tenant_id)}
            for ur in user.roles
        ],
    }


@router.patch("/me")
async def update_me(
    body: UpdateProfileRequest,
    user: User = Depends(_get_current_user),
    db: AsyncSession = Depends(_get_db),
) -> dict[str, Any]:
    if body.name is not None:
        user.name = body.name
    if body.avatar_url is not None:
        user.avatar_url = body.avatar_url
    await db.commit()
    await db.refresh(user)
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "avatar_url": user.avatar_url,
    }


@router.get("")
async def list_users(
    request: Request,
    user: User = Depends(_get_current_user),
    db: AsyncSession = Depends(_get_db),
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    tenant_id = request.headers.get("x-tenant-id")
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant ID required")

    perm_svc = PermissionService(db)
    has_perm = await perm_svc.check_permission(
        user.id, "users:list", uuid.UUID(tenant_id)
    )
    if not has_perm:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    result = await db.execute(select(User).limit(limit).offset(offset))
    users = result.scalars().all()
    return {
        "users": [
            {"id": str(u.id), "email": u.email, "name": u.name, "is_active": u.is_active}
            for u in users
        ],
        "total": len(users),
    }


@router.put("/{user_id}/roles")
async def assign_user_role(
    user_id: str,
    body: AssignRoleRequest,
    user: User = Depends(_get_current_user),
    db: AsyncSession = Depends(_get_db),
) -> dict[str, Any]:
    perm_svc = PermissionService(db)
    tenant_id = uuid.UUID(body.tenant_id)

    has_perm = await perm_svc.check_permission(user.id, "roles:assign", tenant_id)
    if not has_perm:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    try:
        user_role = await perm_svc.assign_role(
            uuid.UUID(user_id), uuid.UUID(body.role_id), tenant_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    return {
        "user_id": user_id,
        "role_id": body.role_id,
        "tenant_id": body.tenant_id,
        "id": str(user_role.id),
    }
