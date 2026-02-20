from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum

import httpx
from fastapi import Request, Response

from .config import CircuitBreakerConfig, TimeoutConfig

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    config: CircuitBreakerConfig
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: float = 0.0
    half_open_calls: int = 0

    def record_success(self) -> None:
        self.failure_count = 0
        self.half_open_calls = 0
        self.state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.config.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning("Circuit breaker opened after %d failures", self.failure_count)

    def can_execute(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            elapsed = time.time() - self.last_failure_time
            if elapsed >= self.config.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
                logger.info("Circuit breaker transitioning to half-open")
                return True
            return False
        # half-open
        if self.half_open_calls < self.config.half_open_max_calls:
            self.half_open_calls += 1
            return True
        return False


@dataclass
class ServiceProxy:
    service_name: str
    base_url: str
    timeout_config: TimeoutConfig
    circuit_breaker_config: CircuitBreakerConfig
    max_retries: int = 3
    retry_base_delay: float = 0.5
    _client: httpx.AsyncClient | None = field(default=None, init=False, repr=False)
    _circuit_breaker: CircuitBreaker = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._circuit_breaker = CircuitBreaker(config=self.circuit_breaker_config)

    async def start(self) -> None:
        timeout = httpx.Timeout(
            connect=self.timeout_config.connect_timeout,
            read=self.timeout_config.read_timeout,
            write=self.timeout_config.write_timeout,
            pool=self.timeout_config.pool_timeout,
        )
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
                keepalive_expiry=30,
            ),
        )
        logger.info("Proxy started for service %s -> %s", self.service_name, self.base_url)

    async def stop(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def forward_request(self, request: Request, path: str) -> Response:
        if not self._circuit_breaker.can_execute():
            logger.error("Circuit breaker open for %s, rejecting request", self.service_name)
            return Response(
                content='{"detail":"Service temporarily unavailable"}',
                status_code=503,
                media_type="application/json",
            )

        body = await request.body()
        headers = dict(request.headers)
        # Remove hop-by-hop headers
        for h in ("host", "connection", "transfer-encoding"):
            headers.pop(h, None)

        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                response = await self._do_request(
                    method=request.method,
                    path=path,
                    headers=headers,
                    params=dict(request.query_params),
                    body=body,
                )
                self._circuit_breaker.record_success()
                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.headers.get("content-type"),
                )
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as exc:
                last_exc = exc
                self._circuit_breaker.record_failure()
                if attempt < self.max_retries - 1:
                    delay = self.retry_base_delay * (2 ** attempt)
                    logger.warning(
                        "Retry %d/%d for %s %s: %s (waiting %.1fs)",
                        attempt + 1, self.max_retries, request.method, path, exc, delay,
                    )
                    await asyncio.sleep(delay)
            except httpx.HTTPStatusError as exc:
                # Don't retry client errors
                if 400 <= exc.response.status_code < 500:
                    return Response(
                        content=exc.response.content,
                        status_code=exc.response.status_code,
                        headers=dict(exc.response.headers),
                    )
                last_exc = exc
                self._circuit_breaker.record_failure()
                if attempt < self.max_retries - 1:
                    delay = self.retry_base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)

        logger.error("All retries exhausted for %s %s: %s", request.method, path, last_exc)
        return Response(
            content='{"detail":"Service unavailable after retries"}',
            status_code=502,
            media_type="application/json",
        )

    async def _do_request(
        self,
        method: str,
        path: str,
        headers: dict[str, str],
        params: dict[str, str],
        body: bytes,
    ) -> httpx.Response:
        if not self._client:
            raise RuntimeError(f"Proxy for {self.service_name} not started")
        response = await self._client.request(
            method=method,
            url=path,
            headers=headers,
            params=params,
            content=body,
        )
        response.raise_for_status()
        return response

    async def health_check(self) -> bool:
        if not self._client:
            return False
        try:
            response = await self._client.get("/health")
            return response.status_code == 200
        except (httpx.RequestError, httpx.HTTPStatusError):
            return False
