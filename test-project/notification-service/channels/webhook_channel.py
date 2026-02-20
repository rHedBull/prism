from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
from typing import Any

import httpx

from notification_service.config.settings import settings

logger = logging.getLogger(__name__)


class WebhookChannel:
    """Sends notifications to configured webhook URLs with retry logic."""

    def __init__(self, signing_secret: str | None = None) -> None:
        self._signing_secret = signing_secret

    async def send(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> None:
        request_headers = {
            "Content-Type": "application/json",
            "User-Agent": f"Prism-Webhook/{settings.service_name}",
            **(headers or {}),
        }

        body = json.dumps(payload, default=str)

        # Add HMAC signature if signing secret is configured
        if self._signing_secret:
            timestamp = str(int(time.time()))
            signature_payload = f"{timestamp}.{body}"
            signature = hmac.new(
                self._signing_secret.encode("utf-8"),
                signature_payload.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            request_headers["X-Webhook-Timestamp"] = timestamp
            request_headers["X-Webhook-Signature"] = f"sha256={signature}"

        last_error: Exception | None = None

        for attempt in range(1, settings.webhook_max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=settings.webhook_timeout
                ) as client:
                    response = await client.post(
                        url,
                        content=body,
                        headers=request_headers,
                    )

                    if response.status_code < 300:
                        logger.info(
                            "Webhook delivered to %s (attempt %d, status %d)",
                            url, attempt, response.status_code,
                        )
                        return

                    if response.status_code >= 400 and response.status_code < 500:
                        # Client error, don't retry
                        raise RuntimeError(
                            f"Webhook rejected by {url}: "
                            f"{response.status_code} - {response.text[:200]}"
                        )

                    # Server error, retry
                    last_error = RuntimeError(
                        f"Webhook server error from {url}: {response.status_code}"
                    )
                    logger.warning(
                        "Webhook attempt %d/%d failed for %s: status %d",
                        attempt, settings.webhook_max_retries, url, response.status_code,
                    )

            except httpx.RequestError as exc:
                last_error = exc
                logger.warning(
                    "Webhook attempt %d/%d failed for %s: %s",
                    attempt, settings.webhook_max_retries, url, exc,
                )

            if attempt < settings.webhook_max_retries:
                delay = settings.webhook_retry_delay * (2 ** (attempt - 1))
                await asyncio.sleep(delay)

        raise RuntimeError(
            f"Webhook delivery to {url} failed after {settings.webhook_max_retries} "
            f"attempts: {last_error}"
        )
