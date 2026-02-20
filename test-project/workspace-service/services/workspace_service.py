from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

import httpx
import redis.asyncio as aioredis
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from workspace_service.config.settings import settings
from workspace_service.models.workspace import Workspace

logger = logging.getLogger(__name__)

WORKSPACE_CACHE_TTL = 300  # 5 minutes


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return re.sub(r"-+", "-", slug).strip("-")


class WorkspaceService:
    def __init__(self, db: AsyncSession, redis: aioredis.Redis) -> None:
        self._db = db
        self._redis = redis

    async def create_workspace(
        self,
        tenant_id: uuid.UUID,
        name: str,
        created_by: uuid.UUID,
        workspace_settings: dict[str, Any] | None = None,
    ) -> Workspace:
        await self._check_billing_quota(tenant_id)

        count_result = await self._db.execute(
            select(func.count()).where(Workspace.tenant_id == tenant_id)
        )
        current_count = count_result.scalar_one()

        if current_count >= settings.max_workspaces_per_tenant:
            raise ValueError(
                f"Tenant {tenant_id} has reached the maximum of "
                f"{settings.max_workspaces_per_tenant} workspaces"
            )

        slug = _slugify(name)
        existing = await self._db.execute(
            select(Workspace).where(
                Workspace.tenant_id == tenant_id, Workspace.slug == slug
            )
        )
        if existing.scalar_one_or_none() is not None:
            slug = f"{slug}-{uuid.uuid4().hex[:6]}"

        workspace = Workspace(
            tenant_id=tenant_id,
            name=name,
            slug=slug,
            settings=workspace_settings or {},
        )
        self._db.add(workspace)
        await self._db.flush()

        await self._invalidate_cache(tenant_id)
        logger.info("Created workspace %s for tenant %s", workspace.id, tenant_id)
        return workspace

    async def get_workspace(self, workspace_id: uuid.UUID) -> Workspace | None:
        cache_key = f"workspace:{workspace_id}"
        cached = await self._redis.get(cache_key)
        if cached:
            logger.debug("Cache hit for workspace %s", workspace_id)
            # Return from DB anyway for full ORM object, but cache validates existence
            pass

        result = await self._db.execute(
            select(Workspace).where(Workspace.id == workspace_id)
        )
        workspace = result.scalar_one_or_none()

        if workspace:
            await self._redis.setex(
                cache_key, WORKSPACE_CACHE_TTL, json.dumps(workspace.to_dict())
            )

        return workspace

    async def list_workspaces(
        self,
        tenant_id: uuid.UUID,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Workspace]:
        result = await self._db.execute(
            select(Workspace)
            .where(Workspace.tenant_id == tenant_id)
            .order_by(Workspace.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_workspace(
        self,
        workspace_id: uuid.UUID,
        name: str | None = None,
        workspace_settings: dict[str, Any] | None = None,
    ) -> Workspace | None:
        workspace = await self.get_workspace(workspace_id)
        if workspace is None:
            return None

        if name is not None:
            workspace.name = name
            workspace.slug = _slugify(name)
        if workspace_settings is not None:
            workspace.settings = {**workspace.settings, **workspace_settings}

        await self._db.flush()
        await self._invalidate_cache(workspace.tenant_id)
        await self._redis.delete(f"workspace:{workspace_id}")
        return workspace

    async def delete_workspace(self, workspace_id: uuid.UUID) -> bool:
        workspace = await self.get_workspace(workspace_id)
        if workspace is None:
            return False

        tenant_id = workspace.tenant_id
        await self._db.execute(
            delete(Workspace).where(Workspace.id == workspace_id)
        )
        await self._invalidate_cache(tenant_id)
        await self._redis.delete(f"workspace:{workspace_id}")
        logger.info("Deleted workspace %s", workspace_id)
        return True

    async def _check_billing_quota(self, tenant_id: uuid.UUID) -> None:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{settings.billing_service_url}/api/v1/quotas/{tenant_id}",
                    headers={"X-Service": settings.service_name},
                )
                if resp.status_code == 200:
                    quota = resp.json()
                    if not quota.get("workspaces_allowed", True):
                        raise ValueError("Billing quota exceeded for workspaces")
        except httpx.RequestError as exc:
            logger.warning("Billing service unavailable, allowing by default: %s", exc)

    async def _invalidate_cache(self, tenant_id: uuid.UUID) -> None:
        cache_key = f"workspaces:tenant:{tenant_id}"
        await self._redis.delete(cache_key)
