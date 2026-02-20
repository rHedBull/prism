from __future__ import annotations

import uuid

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.models.role import Role, UserRole


class PermissionService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def check_permission(
        self, user_id: uuid.UUID, permission: str, tenant_id: uuid.UUID
    ) -> bool:
        result = await self._db.execute(
            select(Role)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(
                and_(
                    UserRole.user_id == user_id,
                    UserRole.tenant_id == tenant_id,
                )
            )
        )
        roles = result.scalars().all()
        for role in roles:
            permissions: dict = role.permissions or {}
            if permission in permissions.get("actions", []):
                return True
            if "*" in permissions.get("actions", []):
                return True
        return False

    async def get_user_roles(
        self, user_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> list[Role]:
        result = await self._db.execute(
            select(Role)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(
                and_(
                    UserRole.user_id == user_id,
                    UserRole.tenant_id == tenant_id,
                )
            )
        )
        return list(result.scalars().all())

    async def assign_role(
        self, user_id: uuid.UUID, role_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> UserRole:
        existing = await self._db.execute(
            select(UserRole).where(
                and_(
                    UserRole.user_id == user_id,
                    UserRole.role_id == role_id,
                    UserRole.tenant_id == tenant_id,
                )
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ValueError("Role already assigned to user for this tenant")

        user_role = UserRole(
            user_id=user_id,
            role_id=role_id,
            tenant_id=tenant_id,
        )
        self._db.add(user_role)
        await self._db.commit()
        await self._db.refresh(user_role)
        return user_role

    async def remove_role(
        self, user_id: uuid.UUID, role_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> None:
        await self._db.execute(
            delete(UserRole).where(
                and_(
                    UserRole.user_id == user_id,
                    UserRole.role_id == role_id,
                    UserRole.tenant_id == tenant_id,
                )
            )
        )
        await self._db.commit()
