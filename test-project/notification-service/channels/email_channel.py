from __future__ import annotations

import asyncio
import logging
import smtplib
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import httpx

from notification_service.config.settings import settings

logger = logging.getLogger(__name__)


class EmailChannel:
    """Sends email notifications via SMTP or SendGrid API."""

    async def send(
        self,
        user_id: uuid.UUID,
        subject: str,
        body: str,
        metadata: dict[str, Any] | None = None,
        to_email: str | None = None,
    ) -> None:
        # In production, resolve user_id to email via user service
        recipient = to_email or (metadata or {}).get("email")
        if not recipient:
            recipient = await self._resolve_user_email(user_id)

        if settings.use_sendgrid_api and settings.sendgrid_api_key:
            await self._send_via_sendgrid(recipient, subject, body)
        else:
            await self._send_via_smtp(recipient, subject, body)

        logger.info("Email sent to %s (user %s): %s", recipient, user_id, subject)

    async def _send_via_smtp(
        self, to_email: str, subject: str, body: str
    ) -> None:
        message = MIMEMultipart("alternative")
        message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
        message["To"] = to_email
        message["Subject"] = subject

        text_part = MIMEText(body, "plain", "utf-8")
        html_part = MIMEText(
            f"<html><body><pre>{body}</pre></body></html>", "html", "utf-8"
        )
        message.attach(text_part)
        message.attach(html_part)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._smtp_send_sync, to_email, message)

    def _smtp_send_sync(self, to_email: str, message: MIMEMultipart) -> None:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.ehlo()
            if settings.smtp_port == 587:
                server.starttls()
                server.ehlo()
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_from_email, to_email, message.as_string())

    async def _send_via_sendgrid(
        self, to_email: str, subject: str, body: str
    ) -> None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={
                    "Authorization": f"Bearer {settings.sendgrid_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "personalizations": [{"to": [{"email": to_email}]}],
                    "from": {
                        "email": settings.smtp_from_email,
                        "name": settings.smtp_from_name,
                    },
                    "subject": subject,
                    "content": [
                        {"type": "text/plain", "value": body},
                        {
                            "type": "text/html",
                            "value": f"<html><body><pre>{body}</pre></body></html>",
                        },
                    ],
                },
            )

            if response.status_code not in (200, 202):
                raise RuntimeError(
                    f"SendGrid API error: {response.status_code} - {response.text}"
                )

    async def _resolve_user_email(self, user_id: uuid.UUID) -> str:
        """Resolve user_id to email address via the user service."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"http://user-service:8000/api/v1/users/{user_id}",
                    headers={"X-Service": settings.service_name},
                )
                if resp.status_code == 200:
                    return resp.json()["email"]
        except httpx.RequestError as exc:
            logger.warning("Failed to resolve email for user %s: %s", user_id, exc)

        raise ValueError(f"Cannot resolve email for user {user_id}")
