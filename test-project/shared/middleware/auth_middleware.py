"""FastAPI authentication middleware.

Verifies JWT tokens, extracts tenant context, and injects identity
information into the request state for downstream handlers.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx
import jwt
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Paths that bypass authentication
_PUBLIC_PATHS: set[str] = {
    "/health",
    "/healthz",
    "/ready",
    "/metrics",
    "/docs",
    "/openapi.json",
    "/redoc",
}


class AuthMiddleware(BaseHTTPMiddleware):
    """JWT authentication middleware for FastAPI.

    Validates tokens against the auth-service, extracts tenant and user
    context, and injects them into ``request.state`` for downstream use.

    Attributes:
        auth_service_url: Base URL of the auth-service for token validation.
        jwt_public_key: RSA/EC public key for local JWT signature verification.
        jwt_algorithm: JWT signing algorithm (e.g. RS256, ES256).
        public_paths: Set of URL paths that skip authentication.
    """

    def __init__(
        self,
        app: Any,
        *,
        auth_service_url: str = "http://auth-service:8000",
        jwt_public_key: str | None = None,
        jwt_algorithm: str = "RS256",
        public_paths: set[str] | None = None,
        cache_ttl: int = 300,
    ) -> None:
        super().__init__(app)
        self.auth_service_url = auth_service_url.rstrip("/")
        self.jwt_public_key = jwt_public_key
        self.jwt_algorithm = jwt_algorithm
        self.public_paths = public_paths or _PUBLIC_PATHS
        self._cache_ttl = cache_ttl
        self._token_cache: dict[str, tuple[dict, float]] = {}
        self._http_client: httpx.AsyncClient | None = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Lazy-init a shared HTTP client for auth-service calls."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                base_url=self.auth_service_url,
                timeout=httpx.Timeout(5.0, connect=2.0),
            )
        return self._http_client

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Process each request: validate token and inject context."""

        # Skip auth for public paths
        if request.url.path in self.public_paths:
            return await call_next(request)

        # Skip auth for CORS preflight
        if request.method == "OPTIONS":
            return await call_next(request)

        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return self._unauthorized("Missing or malformed Authorization header")

        token = auth_header[7:]  # Strip "Bearer " prefix

        # Validate token
        claims = await self._validate_token(token)
        if claims is None:
            return self._unauthorized("Invalid or expired token")

        # Inject identity into request state
        request.state.user_id = claims.get("sub")
        request.state.tenant_id = claims.get("tenant_id")
        request.state.roles = claims.get("roles", [])
        request.state.permissions = claims.get("permissions", [])
        request.state.token_claims = claims
        request.state.session_id = claims.get("session_id")

        # Add tenant context header for downstream services
        response = await call_next(request)
        response.headers["X-Tenant-Id"] = str(request.state.tenant_id)
        response.headers["X-Request-User"] = str(request.state.user_id)

        return response

    async def _validate_token(self, token: str) -> dict[str, Any] | None:
        """Validate a JWT token, checking cache first.

        Attempts local verification if a public key is configured,
        otherwise falls back to the auth-service introspection endpoint.
        """
        # Check cache
        cached = self._token_cache.get(token)
        if cached is not None:
            claims, cached_at = cached
            if time.time() - cached_at < self._cache_ttl:
                return claims
            else:
                del self._token_cache[token]

        claims: dict[str, Any] | None = None

        # Local verification (fast path)
        if self.jwt_public_key:
            claims = self._verify_locally(token)

        # Remote verification (fallback or primary)
        if claims is None:
            claims = await self._verify_remotely(token)

        if claims is not None:
            # Prune cache if too large
            if len(self._token_cache) > 10_000:
                cutoff = time.time() - self._cache_ttl
                self._token_cache = {
                    k: (v, t)
                    for k, (v, t) in self._token_cache.items()
                    if t > cutoff
                }
            self._token_cache[token] = (claims, time.time())

        return claims

    def _verify_locally(self, token: str) -> dict[str, Any] | None:
        """Verify JWT signature and claims locally."""
        try:
            claims = jwt.decode(
                token,
                self.jwt_public_key,
                algorithms=[self.jwt_algorithm],
                options={
                    "verify_exp": True,
                    "verify_aud": False,
                    "require": ["sub", "tenant_id", "exp"],
                },
            )
            return claims
        except jwt.ExpiredSignatureError:
            logger.debug("Token expired.")
        except jwt.InvalidTokenError as exc:
            logger.debug("Local token verification failed: %s", exc)
        return None

    async def _verify_remotely(self, token: str) -> dict[str, Any] | None:
        """Validate the token against the auth-service introspection endpoint."""
        try:
            client = await self._get_http_client()
            response = await client.post(
                "/api/v1/auth/introspect",
                json={"token": token},
                headers={"Content-Type": "application/json"},
            )

            if response.status_code != 200:
                logger.warning(
                    "Auth-service returned %d for token introspection",
                    response.status_code,
                )
                return None

            data = response.json()
            if not data.get("active", False):
                return None

            return data.get("claims")

        except httpx.TimeoutException:
            logger.error("Auth-service introspection timed out.")
        except Exception:
            logger.exception("Auth-service introspection failed.")
        return None

    @staticmethod
    def _unauthorized(detail: str) -> JSONResponse:
        """Build a 401 Unauthorized response."""
        return JSONResponse(
            status_code=401,
            content={
                "error": "unauthorized",
                "detail": detail,
            },
        )
