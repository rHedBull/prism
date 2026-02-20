"""Redis-based rate limiting middleware using the token bucket algorithm.

Supports per-tenant and per-endpoint rate limits with configurable
bucket sizes and refill rates.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from shared.db.redis_client import get_redis

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RateLimitRule:
    """A single rate limit rule definition.

    Attributes:
        max_tokens: Maximum tokens in the bucket (burst capacity).
        refill_rate: Tokens added per second.
        refill_interval: Seconds between refill operations.
    """

    max_tokens: int = 100
    refill_rate: float = 10.0  # tokens per second
    refill_interval: float = 1.0  # seconds


# Lua script for atomic token bucket operations in Redis.
# Returns (allowed: 0|1, remaining_tokens, retry_after_seconds).
_TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local max_tokens = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])
local ttl = tonumber(ARGV[5])

local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(bucket[1])
local last_refill = tonumber(bucket[2])

if tokens == nil then
    tokens = max_tokens
    last_refill = now
end

-- Calculate refill
local elapsed = math.max(0, now - last_refill)
local new_tokens = elapsed * refill_rate
tokens = math.min(max_tokens, tokens + new_tokens)

-- Try to consume
local allowed = 0
local retry_after = 0

if tokens >= requested then
    tokens = tokens - requested
    allowed = 1
else
    retry_after = math.ceil((requested - tokens) / refill_rate)
end

-- Update bucket
redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
redis.call('EXPIRE', key, ttl)

return {allowed, math.floor(tokens), retry_after}
"""


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Token bucket rate limiter backed by Redis.

    Supports multiple limit tiers:
    - **Global**: applies to all requests.
    - **Per-tenant**: keyed by ``tenant_id`` from request state.
    - **Per-endpoint**: keyed by HTTP method + path.
    - **Per-tenant-endpoint**: combined tenant + endpoint key.
    """

    def __init__(
        self,
        app: Any,
        *,
        global_limit: RateLimitRule | None = None,
        tenant_limit: RateLimitRule | None = None,
        endpoint_limits: dict[str, RateLimitRule] | None = None,
        key_prefix: str = "ratelimit",
        bucket_ttl: int = 3600,
        exclude_paths: set[str] | None = None,
    ) -> None:
        super().__init__(app)
        self.global_limit = global_limit or RateLimitRule(max_tokens=1000, refill_rate=100)
        self.tenant_limit = tenant_limit or RateLimitRule(max_tokens=200, refill_rate=20)
        self.endpoint_limits = endpoint_limits or {}
        self.key_prefix = key_prefix
        self.bucket_ttl = bucket_ttl
        self.exclude_paths = exclude_paths or {"/health", "/healthz", "/metrics"}
        self._lua_sha: str | None = None

    async def _ensure_lua_script(self) -> str:
        """Load the Lua script into Redis and cache the SHA."""
        if self._lua_sha is None:
            redis = await get_redis()
            self._lua_sha = await redis.script_load(_TOKEN_BUCKET_LUA)
        return self._lua_sha

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Check rate limits before forwarding the request."""

        if request.url.path in self.exclude_paths:
            return await call_next(request)

        tenant_id = getattr(request.state, "tenant_id", None)
        endpoint_key = f"{request.method}:{request.url.path}"

        # Check all applicable limits
        checks = []

        # Global limit
        checks.append(("global", "global", self.global_limit))

        # Per-tenant limit
        if tenant_id:
            checks.append(("tenant", f"tenant:{tenant_id}", self.tenant_limit))

        # Per-endpoint limit
        if endpoint_key in self.endpoint_limits:
            rule = self.endpoint_limits[endpoint_key]
            checks.append(("endpoint", f"endpoint:{endpoint_key}", rule))

        # Per-tenant-endpoint combined
        if tenant_id and endpoint_key in self.endpoint_limits:
            rule = self.endpoint_limits[endpoint_key]
            checks.append((
                "tenant_endpoint",
                f"tenant:{tenant_id}:endpoint:{endpoint_key}",
                rule,
            ))

        # Evaluate limits
        most_restrictive_remaining = float("inf")
        most_restrictive_limit = 0

        for label, bucket_key, rule in checks:
            allowed, remaining, retry_after = await self._check_limit(bucket_key, rule)

            if not allowed:
                logger.warning(
                    "Rate limit exceeded: %s (tenant=%s, endpoint=%s, retry_after=%ds)",
                    label,
                    tenant_id,
                    endpoint_key,
                    retry_after,
                )
                return self._too_many_requests(
                    retry_after=retry_after,
                    limit=rule.max_tokens,
                    remaining=0,
                )

            if remaining < most_restrictive_remaining:
                most_restrictive_remaining = remaining
                most_restrictive_limit = rule.max_tokens

        response = await call_next(request)

        # Attach rate limit headers
        response.headers["X-RateLimit-Limit"] = str(most_restrictive_limit)
        response.headers["X-RateLimit-Remaining"] = str(int(most_restrictive_remaining))

        return response

    async def _check_limit(
        self,
        bucket_key: str,
        rule: RateLimitRule,
    ) -> tuple[bool, int, int]:
        """Execute the token bucket check against Redis.

        Returns:
            Tuple of (allowed, remaining_tokens, retry_after_seconds).
        """
        redis = await get_redis()
        lua_sha = await self._ensure_lua_script()

        full_key = f"{self.key_prefix}:{bucket_key}"
        now = time.time()

        try:
            result = await redis.evalsha(
                lua_sha,
                1,
                full_key,
                str(rule.max_tokens),
                str(rule.refill_rate),
                str(now),
                "1",  # consume 1 token per request
                str(self.bucket_ttl),
            )
            allowed = bool(result[0])
            remaining = int(result[1])
            retry_after = int(result[2])
            return allowed, remaining, retry_after

        except Exception:
            logger.exception("Rate limit check failed for key '%s'", full_key)
            # Fail open: allow the request if Redis is down
            return True, rule.max_tokens, 0

    @staticmethod
    def _too_many_requests(
        retry_after: int,
        limit: int,
        remaining: int,
    ) -> JSONResponse:
        """Build a 429 Too Many Requests response."""
        return JSONResponse(
            status_code=429,
            content={
                "error": "rate_limit_exceeded",
                "detail": "Too many requests. Please retry later.",
                "retry_after": retry_after,
            },
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": str(remaining),
            },
        )
