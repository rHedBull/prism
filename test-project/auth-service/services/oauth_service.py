from __future__ import annotations

import uuid
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.config.settings import settings
from auth_service.models.user import User

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


class OAuthService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    def generate_oauth_url(self, state: str | None = None) -> str:
        if not state:
            state = uuid.uuid4().hex
        params = {
            "client_id": settings.google_oauth_client_id,
            "redirect_uri": settings.google_oauth_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            token_response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": settings.google_oauth_client_id,
                    "client_secret": settings.google_oauth_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": settings.google_oauth_redirect_uri,
                },
            )
            token_response.raise_for_status()
            tokens = token_response.json()

            userinfo_response = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            userinfo_response.raise_for_status()
            return userinfo_response.json()

    async def get_or_create_oauth_user(self, userinfo: dict[str, Any]) -> User:
        google_id = userinfo["id"]
        email = userinfo["email"]

        result = await self._db.execute(
            select(User).where(
                User.oauth_provider == "google",
                User.oauth_provider_id == google_id,
            )
        )
        user = result.scalar_one_or_none()

        if user is not None:
            user.name = userinfo.get("name", user.name)
            user.avatar_url = userinfo.get("picture", user.avatar_url)
            await self._db.commit()
            return user

        result = await self._db.execute(select(User).where(User.email == email))
        existing_user = result.scalar_one_or_none()
        if existing_user is not None:
            existing_user.oauth_provider = "google"
            existing_user.oauth_provider_id = google_id
            existing_user.avatar_url = userinfo.get("picture", existing_user.avatar_url)
            await self._db.commit()
            return existing_user

        new_user = User(
            email=email,
            name=userinfo.get("name", email.split("@")[0]),
            avatar_url=userinfo.get("picture"),
            oauth_provider="google",
            oauth_provider_id=google_id,
            hashed_password=None,
        )
        self._db.add(new_user)
        await self._db.commit()
        await self._db.refresh(new_user)
        return new_user
