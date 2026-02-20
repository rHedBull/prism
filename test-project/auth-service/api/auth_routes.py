from __future__ import annotations

from typing import Any

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.models.user import User
from auth_service.services.auth_service import AuthService
from auth_service.services.token_service import TokenService

router = APIRouter(prefix="/auth")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str


class RefreshRequest(BaseModel):
    refresh_token: str


class MFAVerifyRequest(BaseModel):
    user_id: str
    code: str


async def _get_db(request: Request) -> AsyncSession:
    async with request.app.state.db_pool() as session:
        yield session


async def _get_token_service(request: Request) -> TokenService:
    return TokenService(request.app.state.redis)


async def _get_auth_service(
    db: AsyncSession = Depends(_get_db),
    token_service: TokenService = Depends(_get_token_service),
) -> AuthService:
    return AuthService(db, token_service)


@router.post("/login")
async def login(
    body: LoginRequest,
    request: Request,
    auth_svc: AuthService = Depends(_get_auth_service),
) -> dict[str, Any]:
    device_info = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None
    try:
        result = await auth_svc.authenticate(
            body.email, body.password, device_info=device_info, ip_address=ip_address
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))

    if result["user"]["mfa_enabled"]:
        return {
            "mfa_required": True,
            "user_id": result["user"]["id"],
            "message": "MFA verification required",
        }
    return result


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    auth_svc: AuthService = Depends(_get_auth_service),
) -> dict[str, Any]:
    try:
        user = await auth_svc.register_user(body.email, body.password, body.name)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        )
    return {"id": str(user.id), "email": user.email, "name": user.name}


@router.post("/refresh")
async def refresh(
    body: RefreshRequest,
    auth_svc: AuthService = Depends(_get_auth_service),
) -> dict[str, Any]:
    try:
        return await auth_svc.refresh_tokens(body.refresh_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    auth_svc: AuthService = Depends(_get_auth_service),
) -> None:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token"
        )
    token = auth_header.removeprefix("Bearer ")
    await auth_svc.revoke_session(token)


@router.post("/mfa/verify")
async def mfa_verify(
    body: MFAVerifyRequest,
    db: AsyncSession = Depends(_get_db),
    token_svc: TokenService = Depends(_get_token_service),
) -> dict[str, Any]:
    result = await db.execute(select(User).where(User.id == body.user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.mfa_enabled or user.mfa_secret is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="MFA not configured"
        )

    totp = pyotp.TOTP(user.mfa_secret)
    if not totp.verify(body.code, valid_window=1):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA code"
        )

    roles = [ur.role.name for ur in user.roles]
    access_token = token_svc.create_access_token(user.id, user.email, roles)
    refresh_token = token_svc.create_refresh_token(user.id)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }
