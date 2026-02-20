from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from workspace_service.models.project import Project, ProjectStatus

logger = logging.getLogger(__name__)


class ProjectService:
    def __init__(self, db: AsyncSession, redis: aioredis.Redis) -> None:
        self._db = db
        self._redis = redis

    async def create_project(
        self,
        workspace_id: uuid.UUID,
        name: str,
        description: str | None,
        created_by: uuid.UUID,
    ) -> Project:
        project = Project(
            workspace_id=workspace_id,
            name=name,
            description=description,
            created_by=created_by,
        )
        self._db.add(project)
        await self._db.flush()

        await self._publish_event(
            "project.created",
            {
                "project_id": str(project.id),
                "workspace_id": str(workspace_id),
                "name": name,
                "created_by": str(created_by),
            },
        )

        logger.info("Created project %s in workspace %s", project.id, workspace_id)
        return project

    async def get_project(self, project_id: uuid.UUID) -> Project | None:
        result = await self._db.execute(
            select(Project).where(Project.id == project_id)
        )
        return result.scalar_one_or_none()

    async def list_projects(
        self,
        workspace_id: uuid.UUID,
        status: ProjectStatus | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Project]:
        query = select(Project).where(Project.workspace_id == workspace_id)
        if status is not None:
            query = query.where(Project.status == status)

        query = query.order_by(Project.created_at.desc()).offset(offset).limit(limit)
        result = await self._db.execute(query)
        return list(result.scalars().all())

    async def update_project(
        self,
        project_id: uuid.UUID,
        name: str | None = None,
        description: str | None = None,
    ) -> Project | None:
        project = await self.get_project(project_id)
        if project is None:
            return None

        if name is not None:
            project.name = name
        if description is not None:
            project.description = description

        await self._db.flush()

        await self._publish_event(
            "project.updated",
            {"project_id": str(project_id), "workspace_id": str(project.workspace_id)},
        )
        return project

    async def archive_project(self, project_id: uuid.UUID) -> Project | None:
        project = await self.get_project(project_id)
        if project is None:
            return None

        project.status = ProjectStatus.ARCHIVED
        await self._db.flush()

        await self._publish_event(
            "project.archived",
            {"project_id": str(project_id), "workspace_id": str(project.workspace_id)},
        )
        logger.info("Archived project %s", project_id)
        return project

    async def restore_project(self, project_id: uuid.UUID) -> Project | None:
        project = await self.get_project(project_id)
        if project is None:
            return None

        project.status = ProjectStatus.ACTIVE
        await self._db.flush()

        await self._publish_event(
            "project.restored",
            {"project_id": str(project_id), "workspace_id": str(project.workspace_id)},
        )
        logger.info("Restored project %s", project_id)
        return project

    async def _publish_event(self, event_type: str, payload: dict[str, Any]) -> None:
        """Publish event to Redis pub/sub for the event bus to pick up."""
        event = {
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        try:
            await self._redis.publish("workspace_events", json.dumps(event))
        except Exception as exc:
            logger.error("Failed to publish event %s: %s", event_type, exc)
