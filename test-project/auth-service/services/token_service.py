from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from redis.asyncio import Redis

from auth_service.config.settings import settings


class TokenService:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    def create_access_token(
        self,
        user_id: uuid.UUID,
        email: str,
        roles: list[str],
        tenant_id: uuid.UUID | None = None,
    ) -> str:
        now = datetime.now(timezone.utc)
        payload: dict[str, Any] = {
            "sub": str(user_id),
            "email": email,
            "roles": roles,
            "iat": now,
            "exp": now + timedelta(seconds=settings.token_ttl),
            "jti": str(uuid.uuid4()),
            "type": "access",
        }
        if tenant_id:
            payload["tenant_id"] = str(tenant_id)
        return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    def create_refresh_token(self, user_id: uuid.UUID) -> str:
        now = datetime.now(timezone.utc)
        payload: dict[str, Any] = {
            "sub": str(user_id),
            "iat": now,
            "exp": now + timedelta(seconds=settings.refresh_ttl),
            "jti": str(uuid.uuid4()),
            "type": "refresh",
        }
        return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    def decode_token(self, token: str) -> dict[str, Any]:
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret,
                algorithms=[settings.jwt_algorithm],
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise ValueError("Token has expired")
        except jwt.InvalidTokenError as exc:
            raise ValueError(f"Invalid token: {exc}")

    async def blacklist_token(self, token: str) -> None:
        try:
            payload = self.decode_token(token)
        except ValueError:
            return
        jti = payload.get("jti")
        exp = payload.get("exp", 0)
        ttl = max(int(exp - datetime.now(timezone.utc).timestamp()), 1)
        await self._redis.setex(f"blacklist:{jti}", ttl, "1")

    async def is_blacklisted(self, token: str) -> bool:
        payload = self.decode_token(token)
        jti = payload.get("jti")
        return await self._redis.exists(f"blacklist:{jti}") > 0

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()
