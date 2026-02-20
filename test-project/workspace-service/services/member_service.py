from __future__ import annotations

import logging
import uuid
from typing import Any

import httpx
import redis.asyncio as aioredis
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from workspace_service.config.settings import settings
from workspace_service.models.member import Member, MemberRole

logger = logging.getLogger(__name__)

ROLE_HIERARCHY: dict[MemberRole, int] = {
    MemberRole.OWNER: 40,
    MemberRole.ADMIN: 30,
    MemberRole.MEMBER: 20,
    MemberRole.VIEWER: 10,
}


class MemberService:
    def __init__(self, db: AsyncSession, redis: aioredis.Redis) -> None:
        self._db = db
        self._redis = redis

    async def invite_member(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        role: MemberRole,
        invited_by: uuid.UUID,
    ) -> Member:
        await self._check_permission(workspace_id, invited_by, min_role=MemberRole.ADMIN)

        count_result = await self._db.execute(
            select(func.count()).select_from(Member).where(
                Member.workspace_id == workspace_id
            )
        )
        member_count = count_result.scalar_one()

        if member_count >= settings.max_members_per_workspace:
            raise ValueError(
                f"Workspace has reached the maximum of "
                f"{settings.max_members_per_workspace} members"
            )

        existing = await self._db.execute(
            select(Member).where(
                Member.workspace_id == workspace_id, Member.user_id == user_id
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ValueError(f"User {user_id} is already a member of this workspace")

        if role == MemberRole.OWNER:
            raise ValueError("Cannot invite a user as owner; use ownership transfer instead")

        member = Member(
            workspace_id=workspace_id,
            user_id=user_id,
            role=role,
            invited_by=invited_by,
        )
        self._db.add(member)
        await self._db.flush()

        await self._send_invite_notification(workspace_id, user_id, invited_by, role)

        logger.info(
            "Invited user %s to workspace %s with role %s",
            user_id, workspace_id, role.value,
        )
        return member

    async def remove_member(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        removed_by: uuid.UUID,
    ) -> bool:
        await self._check_permission(workspace_id, removed_by, min_role=MemberRole.ADMIN)

        target = await self._db.execute(
            select(Member).where(
                Member.workspace_id == workspace_id, Member.user_id == user_id
            )
        )
        target_member = target.scalar_one_or_none()
        if target_member is None:
            return False

        if target_member.role == MemberRole.OWNER:
            raise ValueError("Cannot remove the workspace owner")

        await self._db.execute(
            delete(Member).where(
                Member.workspace_id == workspace_id, Member.user_id == user_id
            )
        )
        logger.info("Removed user %s from workspace %s", user_id, workspace_id)
        return True

    async def update_role(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        new_role: MemberRole,
        updated_by: uuid.UUID,
    ) -> Member | None:
        await self._check_permission(workspace_id, updated_by, min_role=MemberRole.ADMIN)

        result = await self._db.execute(
            select(Member).where(
                Member.workspace_id == workspace_id, Member.user_id == user_id
            )
        )
        member = result.scalar_one_or_none()
        if member is None:
            return None

        if member.role == MemberRole.OWNER and new_role != MemberRole.OWNER:
            raise ValueError("Cannot demote workspace owner; transfer ownership first")

        if new_role == MemberRole.OWNER:
            raise ValueError("Use ownership transfer to assign owner role")

        member.role = new_role
        await self._db.flush()
        logger.info(
            "Updated role for user %s in workspace %s to %s",
            user_id, workspace_id, new_role.value,
        )
        return member

    async def list_members(
        self,
        workspace_id: uuid.UUID,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Member]:
        result = await self._db.execute(
            select(Member)
            .where(Member.workspace_id == workspace_id)
            .order_by(Member.joined_at.asc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def _check_permission(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        min_role: MemberRole,
    ) -> Member:
        result = await self._db.execute(
            select(Member).where(
                Member.workspace_id == workspace_id, Member.user_id == user_id
            )
        )
        member = result.scalar_one_or_none()
        if member is None:
            raise PermissionError(f"User {user_id} is not a member of workspace {workspace_id}")

        if ROLE_HIERARCHY[member.role] < ROLE_HIERARCHY[min_role]:
            raise PermissionError(
                f"User {user_id} has insufficient permissions "
                f"(required: {min_role.value}, has: {member.role.value})"
            )
        return member

    async def _send_invite_notification(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        invited_by: uuid.UUID,
        role: MemberRole,
    ) -> None:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{settings.notification_service_url}/api/v1/send",
                    json={
                        "user_id": str(user_id),
                        "channel": "email",
                        "subject": "You've been invited to a workspace",
                        "body": (
                            f"You have been invited to workspace {workspace_id} "
                            f"with role {role.value} by user {invited_by}."
                        ),
                        "event_type": "workspace.invite",
                        "metadata": {
                            "workspace_id": str(workspace_id),
                            "invited_by": str(invited_by),
                            "role": role.value,
                        },
                    },
                    headers={"X-Service": settings.service_name},
                )
        except httpx.RequestError as exc:
            logger.warning("Failed to send invite notification: %s", exc)
