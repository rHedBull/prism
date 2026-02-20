from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.config.settings import settings
from auth_service.models.session import Session
from auth_service.models.user import User
from auth_service.services.token_service import TokenService


class AuthService:
    def __init__(self, db: AsyncSession, token_service: TokenService) -> None:
        self._db = db
        self._tokens = token_service

    async def authenticate(
        self, email: str, password: str, device_info: str | None = None, ip_address: str | None = None
    ) -> dict[str, Any]:
        result = await self._db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is None:
            raise ValueError("Invalid email or password")

        if not user.is_active:
            raise PermissionError("Account is deactivated")

        if user.hashed_password is None:
            raise ValueError("Account uses OAuth login — password authentication disabled")

        if not bcrypt.checkpw(password.encode(), user.hashed_password.encode()):
            raise ValueError("Invalid email or password")

        roles = [ur.role.name for ur in user.roles]
        access_token = self._tokens.create_access_token(user.id, user.email, roles)
        refresh_token = self._tokens.create_refresh_token(user.id)

        session = Session(
            user_id=user.id,
            token_hash=TokenService.hash_token(access_token),
            refresh_token_hash=TokenService.hash_token(refresh_token),
            device_info=device_info,
            ip_address=ip_address,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=settings.refresh_ttl),
        )
        self._db.add(session)

        user.last_login = datetime.now(timezone.utc)
        await self._db.commit()

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.token_ttl,
            "user": {
                "id": str(user.id),
                "email": user.email,
                "name": user.name,
                "mfa_enabled": user.mfa_enabled,
            },
        }

    async def register_user(
        self, email: str, password: str, name: str
    ) -> User:
        existing = await self._db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none() is not None:
            raise ValueError("Email already registered")

        if len(password) < settings.password_min_length:
            raise ValueError(
                f"Password must be at least {settings.password_min_length} characters"
            )

        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user = User(email=email, hashed_password=hashed, name=name)
        self._db.add(user)
        await self._db.commit()
        await self._db.refresh(user)
        return user

    async def refresh_tokens(
        self, refresh_token: str
    ) -> dict[str, Any]:
        payload = self._tokens.decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("Invalid token type — expected refresh token")

        if await self._tokens.is_blacklisted(refresh_token):
            raise ValueError("Refresh token has been revoked")

        user_id = uuid.UUID(payload["sub"])
        result = await self._db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            raise ValueError("User not found or deactivated")

        refresh_hash = TokenService.hash_token(refresh_token)
        session_result = await self._db.execute(
            select(Session).where(Session.refresh_token_hash == refresh_hash)
        )
        session = session_result.scalar_one_or_none()
        if session is None:
            raise ValueError("Session not found")

        await self._tokens.blacklist_token(refresh_token)

        roles = [ur.role.name for ur in user.roles]
        new_access = self._tokens.create_access_token(user.id, user.email, roles)
        new_refresh = self._tokens.create_refresh_token(user.id)

        session.token_hash = TokenService.hash_token(new_access)
        session.refresh_token_hash = TokenService.hash_token(new_refresh)
        session.expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.refresh_ttl)
        await self._db.commit()

        return {
            "access_token": new_access,
            "refresh_token": new_refresh,
            "token_type": "bearer",
            "expires_in": settings.token_ttl,
        }

    async def revoke_session(self, access_token: str) -> None:
        await self._tokens.blacklist_token(access_token)
        token_hash = TokenService.hash_token(access_token)
        result = await self._db.execute(
            select(Session).where(Session.token_hash == token_hash)
        )
        session = result.scalar_one_or_none()
        if session:
            await self._db.delete(session)
            await self._db.commit()

    async def validate_token(self, token: str) -> dict[str, Any]:
        if await self._tokens.is_blacklisted(token):
            raise ValueError("Token has been revoked")
        payload = self._tokens.decode_token(token)
        if payload.get("type") != "access":
            raise ValueError("Invalid token type — expected access token")
        return payload
