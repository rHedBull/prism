from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from notification_service.channels.email_channel import EmailChannel
from notification_service.channels.in_app_channel import InAppChannel
from notification_service.channels.webhook_channel import WebhookChannel
from notification_service.models.notification import (
    Notification,
    NotificationChannel,
    NotificationStatus,
)
from notification_service.models.preference import NotificationPreference
from notification_service.services.template_service import TemplateService

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    """Routes notifications to the appropriate channel based on user preferences."""

    def __init__(
        self,
        db: AsyncSession,
        email_channel: EmailChannel,
        in_app_channel: InAppChannel,
        webhook_channel: WebhookChannel,
        template_service: TemplateService,
    ) -> None:
        self._db = db
        self._email = email_channel
        self._in_app = in_app_channel
        self._webhook = webhook_channel
        self._templates = template_service

    async def dispatch_notification(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        channel: NotificationChannel,
        subject: str,
        body: str,
        event_type: str = "general",
        metadata: dict[str, Any] | None = None,
        template_name: str | None = None,
        template_context: dict[str, Any] | None = None,
    ) -> Notification:
        # Check user preferences
        if not await self._is_channel_enabled(user_id, channel.value, event_type):
            logger.info(
                "Notification suppressed for user %s: channel=%s event=%s",
                user_id, channel.value, event_type,
            )
            notification = Notification(
                tenant_id=tenant_id,
                user_id=user_id,
                channel=channel,
                subject=subject,
                body=body,
                status=NotificationStatus.SENT,
                metadata={**(metadata or {}), "suppressed": True, "event_type": event_type},
            )
            self._db.add(notification)
            await self._db.flush()
            return notification

        # Render template if provided
        if template_name and template_context:
            rendered = await self._templates.render_template(
                template_name, template_context
            )
            subject = rendered.get("subject", subject)
            body = rendered.get("body", body)

        # Create notification record
        notification = Notification(
            tenant_id=tenant_id,
            user_id=user_id,
            channel=channel,
            subject=subject,
            body=body,
            status=NotificationStatus.PENDING,
            metadata={**(metadata or {}), "event_type": event_type},
        )
        self._db.add(notification)
        await self._db.flush()

        # Dispatch to the appropriate channel
        try:
            if channel == NotificationChannel.EMAIL:
                await self._email.send(
                    user_id=user_id,
                    subject=subject,
                    body=body,
                    metadata=metadata,
                )
            elif channel == NotificationChannel.IN_APP:
                await self._in_app.send(
                    user_id=user_id,
                    notification_id=notification.id,
                    subject=subject,
                    body=body,
                )
            elif channel == NotificationChannel.WEBHOOK:
                webhook_url = (metadata or {}).get("webhook_url")
                if webhook_url:
                    await self._webhook.send(
                        url=webhook_url,
                        payload={
                            "notification_id": str(notification.id),
                            "event_type": event_type,
                            "subject": subject,
                            "body": body,
                            "tenant_id": str(tenant_id),
                            "user_id": str(user_id),
                        },
                    )
                else:
                    raise ValueError("webhook_url required in metadata for webhook channel")

            notification.status = NotificationStatus.SENT
            notification.sent_at = datetime.now(timezone.utc)
            logger.info(
                "Notification %s sent via %s to user %s",
                notification.id, channel.value, user_id,
            )

        except Exception as exc:
            notification.status = NotificationStatus.FAILED
            notification.error = str(exc)
            logger.error(
                "Failed to send notification %s via %s: %s",
                notification.id, channel.value, exc,
            )

        await self._db.flush()
        return notification

    async def _is_channel_enabled(
        self, user_id: uuid.UUID, channel: str, event_type: str
    ) -> bool:
        result = await self._db.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id,
                NotificationPreference.channel == channel,
                NotificationPreference.event_type == event_type,
            )
        )
        preference = result.scalar_one_or_none()

        # Default to enabled if no preference is set
        if preference is None:
            return True

        return preference.enabled
