from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import jwt
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from .config import GatewaySettings
from .proxy import ServiceProxy
from .service_registry import ServiceRegistry

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

settings = GatewaySettings.from_env()
registry = ServiceRegistry(health_check_interval=15.0)

# Proxies keyed by route prefix
_proxies: dict[str, ServiceProxy] = {}

# Route mapping: URL prefix -> (service_name, proxy_key)
ROUTE_MAP: dict[str, str] = {
    "/api/v1/auth": "auth",
    "/api/v1/billing": "billing",
    "/api/v1/workspaces": "workspaces",
    "/api/v1/analytics": "analytics",
    "/api/v1/notifications": "notifications",
    "/api/v1/files": "files",
}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Register services and create proxies
    for service_name, service_url in settings.service_routes.items():
        await registry.register(service_name, service_url)
        proxy = ServiceProxy(
            service_name=service_name,
            base_url=service_url,
            timeout_config=settings.timeout,
            circuit_breaker_config=settings.circuit_breaker,
        )
        await proxy.start()
        _proxies[service_name] = proxy

    await registry.start()
    logger.info("Gateway started with %d services registered", len(_proxies))

    yield

    # Shutdown
    await registry.stop()
    for proxy in _proxies.values():
        await proxy.stop()
    _proxies.clear()
    logger.info("Gateway shut down")


app = FastAPI(
    title="Prism API Gateway",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)


# --- Rate Limiting Middleware ---

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI, requests_per_minute: int = 60, window_seconds: int = 60) -> None:
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.window_seconds = window_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - self.window_seconds

        # Clean old entries
        bucket = self._buckets[client_ip]
        self._buckets[client_ip] = [t for t in bucket if t > window_start]
        bucket = self._buckets[client_ip]

        if len(bucket) >= self.requests_per_minute:
            retry_after = int(bucket[0] - window_start) + 1
            return Response(
                content='{"detail":"Rate limit exceeded"}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(retry_after)},
            )

        bucket.append(now)
        return await call_next(request)


app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=settings.rate_limit.requests_per_minute,
    window_seconds=settings.rate_limit.window_seconds,
)


# --- Request Logging Middleware ---

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = str(uuid.uuid4())[:8]
        start = time.perf_counter()

        logger.info(
            "[%s] -> %s %s",
            request_id, request.method, request.url.path,
        )

        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "[%s] <- %d (%.1fms)",
            request_id, response.status_code, elapsed_ms,
        )
        response.headers["X-Request-ID"] = request_id
        return response


app.add_middleware(RequestLoggingMiddleware)


# --- Auth Middleware ---

# Public paths that don't require auth
PUBLIC_PATHS = {
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
    "/health",
    "/services",
}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        # Skip auth for public paths and OPTIONS
        if request.method == "OPTIONS" or path in PUBLIC_PATHS:
            return await call_next(request)

        # Skip auth for non-API paths
        if not path.startswith("/api/"):
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return Response(
                content='{"detail":"Missing or invalid authorization header"}',
                status_code=401,
                media_type="application/json",
            )

        token = auth_header[7:]
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret,
                algorithms=[settings.jwt_algorithm],
            )
            # Attach user info to request state
            request.state.user_id = payload.get("sub")
            request.state.user_email = payload.get("email")
            request.state.user_role = payload.get("role", "member")
        except jwt.ExpiredSignatureError:
            return Response(
                content='{"detail":"Token expired"}',
                status_code=401,
                media_type="application/json",
            )
        except jwt.InvalidTokenError:
            return Response(
                content='{"detail":"Invalid token"}',
                status_code=401,
                media_type="application/json",
            )

        return await call_next(request)


app.add_middleware(AuthMiddleware)


# --- Health & Discovery Endpoints ---

@app.get("/health")
async def health_check() -> dict:
    statuses = await registry.health_check_all()
    all_healthy = all(s.value == "healthy" for s in statuses.values())
    return {
        "status": "healthy" if all_healthy else "degraded",
        "services": {name: status.value for name, status in statuses.items()},
    }


@app.get("/services")
async def list_services() -> dict:
    services = await registry.get_all_services()
    return {
        name: {
            "url": svc.url,
            "status": svc.status.value,
            "last_check": svc.last_health_check,
        }
        for name, svc in services.items()
    }


# --- Catch-all Proxy Route ---

@app.api_route("/api/v1/{service_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy_request(request: Request, service_path: str) -> Response:
    # Determine which service handles this path
    full_path = f"/api/v1/{service_path}"
    target_service: str | None = None
    remaining_path: str = ""

    for prefix, service_name in ROUTE_MAP.items():
        if full_path.startswith(prefix):
            target_service = service_name
            remaining_path = full_path[len(prefix):] or "/"
            break

    if target_service is None:
        return Response(
            content='{"detail":"No service registered for this path"}',
            status_code=404,
            media_type="application/json",
        )

    proxy = _proxies.get(target_service)
    if proxy is None:
        return Response(
            content='{"detail":"Service proxy not available"}',
            status_code=503,
            media_type="application/json",
        )

    return await proxy.forward_request(request, remaining_path)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)
