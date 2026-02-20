from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis

from notification_service.config.settings import settings

logger = logging.getLogger(__name__)


class InAppChannel:
    """Stores in-app notifications in the database and pushes real-time
    updates via Redis pub/sub."""

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    async def send(
        self,
        user_id: uuid.UUID,
        notification_id: uuid.UUID,
        subject: str,
        body: str,
    ) -> None:
        # Push real-time notification via Redis pub/sub
        channel_name = f"notifications:user:{user_id}"
        payload = json.dumps({
            "notification_id": str(notification_id),
            "subject": subject,
            "body": body,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        subscribers = await self._redis.publish(channel_name, payload)
        logger.info(
            "In-app notification %s pushed to %d subscribers for user %s",
            notification_id, subscribers, user_id,
        )

        # Also add to the user's unread notification counter
        counter_key = f"notifications:unread:{user_id}"
        await self._redis.incr(counter_key)
        await self._redis.expire(counter_key, 86400 * 30)  # 30-day TTL

    async def get_unread_count(self, user_id: uuid.UUID) -> int:
        counter_key = f"notifications:unread:{user_id}"
        count = await self._redis.get(counter_key)
        return int(count) if count else 0

    async def mark_read(self, user_id: uuid.UUID) -> None:
        counter_key = f"notifications:unread:{user_id}"
        await self._redis.set(counter_key, 0)
