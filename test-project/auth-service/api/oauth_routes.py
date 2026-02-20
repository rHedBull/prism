from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.config.settings import settings
from auth_service.models.session import Session
from auth_service.services.oauth_service import OAuthService
from auth_service.services.token_service import TokenService

router = APIRouter(prefix="/oauth")


async def _get_db(request: Request) -> AsyncSession:
    async with request.app.state.db_pool() as session:
        yield session


@router.get("/google")
async def google_oauth_redirect(
    db: AsyncSession = Depends(_get_db),
) -> RedirectResponse:
    svc = OAuthService(db)
    url = svc.generate_oauth_url()
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)


@router.get("/google/callback")
async def google_oauth_callback(
    code: str,
    state: str | None = None,
    request: Request = None,
    db: AsyncSession = Depends(_get_db),
) -> dict[str, Any]:
    svc = OAuthService(db)

    try:
        userinfo = await svc.exchange_code(code)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to exchange OAuth code with Google",
        )

    user = await svc.get_or_create_oauth_user(userinfo)

    token_svc = TokenService(request.app.state.redis)
    roles = [ur.role.name for ur in user.roles]
    access_token = token_svc.create_access_token(user.id, user.email, roles)
    refresh_token = token_svc.create_refresh_token(user.id)

    device_info = request.headers.get("user-agent") if request else None
    ip_address = request.client.host if request and request.client else None

    session = Session(
        user_id=user.id,
        token_hash=TokenService.hash_token(access_token),
        refresh_token_hash=TokenService.hash_token(refresh_token),
        device_info=device_info,
        ip_address=ip_address,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=settings.refresh_ttl),
    )
    db.add(session)
    await db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.token_ttl,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "avatar_url": user.avatar_url,
        },
    }
