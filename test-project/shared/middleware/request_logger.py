"""Structured request/response logging middleware.

Logs every HTTP request and response to structured JSON, captures timing
metrics, and optionally forwards metrics to the analytics service.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger("request_logger")

# Fields to redact from logged headers
_SENSITIVE_HEADERS: set[str] = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "x-csrf-token",
}


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    """Structured JSON request/response logger with analytics integration.

    Logs:
    - Request method, path, query, headers (redacted), client IP.
    - Response status code, size, timing.
    - Tenant and user context if available in request state.

    Optionally publishes timing metrics to the internal event bus for
    the analytics pipeline.
    """

    def __init__(
        self,
        app: Any,
        *,
        service_name: str = "unknown",
        log_request_body: bool = False,
        log_response_body: bool = False,
        max_body_log_size: int = 4096,
        exclude_paths: set[str] | None = None,
        publish_metrics: bool = True,
        slow_request_threshold_ms: float = 1000.0,
    ) -> None:
        super().__init__(app)
        self.service_name = service_name
        self.log_request_body = log_request_body
        self.log_response_body = log_response_body
        self.max_body_log_size = max_body_log_size
        self.exclude_paths = exclude_paths or {"/health", "/healthz", "/metrics"}
        self.publish_metrics = publish_metrics
        self.slow_request_threshold_ms = slow_request_threshold_ms

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Log the request, call the handler, then log the response."""

        if request.url.path in self.exclude_paths:
            return await call_next(request)

        # Generate or propagate request ID
        request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
        correlation_id = request.headers.get("X-Correlation-Id", request_id)

        # Inject into request state for downstream use
        request.state.request_id = request_id
        request.state.correlation_id = correlation_id

        # Capture timing
        start_time = time.perf_counter()

        # Capture request body if configured
        request_body: str | None = None
        if self.log_request_body:
            body_bytes = await request.body()
            if len(body_bytes) <= self.max_body_log_size:
                request_body = body_bytes.decode("utf-8", errors="replace")

        # Process the request
        response: Response | None = None
        error: Exception | None = None

        try:
            response = await call_next(request)
        except Exception as exc:
            error = exc
            raise
        finally:
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            log_entry = self._build_log_entry(
                request=request,
                response=response,
                request_id=request_id,
                correlation_id=correlation_id,
                elapsed_ms=elapsed_ms,
                request_body=request_body,
                error=error,
            )

            # Choose log level based on status code and timing
            if error or (response and response.status_code >= 500):
                logger.error(json.dumps(log_entry, default=str))
            elif response and response.status_code >= 400:
                logger.warning(json.dumps(log_entry, default=str))
            elif elapsed_ms > self.slow_request_threshold_ms:
                logger.warning(json.dumps(log_entry, default=str))
            else:
                logger.info(json.dumps(log_entry, default=str))

            # Publish metrics to the event bus
            if self.publish_metrics:
                await self._publish_metrics(log_entry)

        # Attach tracing headers to the response
        if response is not None:
            response.headers["X-Request-Id"] = request_id
            response.headers["X-Correlation-Id"] = correlation_id
            response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.1f}"

        return response

    def _build_log_entry(
        self,
        *,
        request: Request,
        response: Response | None,
        request_id: str,
        correlation_id: str,
        elapsed_ms: float,
        request_body: str | None,
        error: Exception | None,
    ) -> dict[str, Any]:
        """Construct a structured log dict."""
        client_ip = request.client.host if request.client else "unknown"

        entry: dict[str, Any] = {
            "timestamp": time.time(),
            "service": self.service_name,
            "request_id": request_id,
            "correlation_id": correlation_id,
            "method": request.method,
            "path": request.url.path,
            "query": str(request.url.query) or None,
            "client_ip": client_ip,
            "user_agent": request.headers.get("user-agent"),
            "headers": self._redact_headers(dict(request.headers)),
            "status_code": response.status_code if response else 500,
            "elapsed_ms": round(elapsed_ms, 2),
            "is_slow": elapsed_ms > self.slow_request_threshold_ms,
        }

        # Tenant/user context from auth middleware
        tenant_id = getattr(request.state, "tenant_id", None)
        user_id = getattr(request.state, "user_id", None)
        if tenant_id:
            entry["tenant_id"] = tenant_id
        if user_id:
            entry["user_id"] = user_id

        if request_body:
            entry["request_body"] = request_body

        if error:
            entry["error"] = {
                "type": type(error).__name__,
                "message": str(error),
            }

        return entry

    @staticmethod
    def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
        """Redact sensitive header values."""
        redacted = {}
        for key, value in headers.items():
            if key.lower() in _SENSITIVE_HEADERS:
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = value
        return redacted

    async def _publish_metrics(self, log_entry: dict[str, Any]) -> None:
        """Publish request metrics to the internal event bus."""
        try:
            from shared.events.event_bus import Event, get_event_bus

            bus = get_event_bus()

            metric_event = Event(
                type="metrics.http_request",
                payload={
                    "service": log_entry["service"],
                    "method": log_entry["method"],
                    "path": log_entry["path"],
                    "status_code": log_entry["status_code"],
                    "elapsed_ms": log_entry["elapsed_ms"],
                    "tenant_id": log_entry.get("tenant_id"),
                    "is_slow": log_entry["is_slow"],
                },
                source_service=self.service_name,
                correlation_id=log_entry["correlation_id"],
            )

            await bus.publish(metric_event)

        except Exception:
            # Metrics publishing should never break request handling
            logger.debug("Failed to publish request metrics", exc_info=True)
