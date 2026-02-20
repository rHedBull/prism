from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RateLimitConfig:
    requests_per_minute: int = 60
    burst_size: int = 10
    window_seconds: int = 60


@dataclass(frozen=True)
class TimeoutConfig:
    connect_timeout: float = 5.0
    read_timeout: float = 30.0
    write_timeout: float = 30.0
    pool_timeout: float = 10.0


@dataclass(frozen=True)
class CircuitBreakerConfig:
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_max_calls: int = 3


@dataclass
class GatewaySettings:
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Service URLs
    auth_service_url: str = "http://localhost:8001"
    billing_service_url: str = "http://localhost:8002"
    workspace_service_url: str = "http://localhost:8003"
    analytics_service_url: str = "http://localhost:8004"
    notification_service_url: str = "http://localhost:8005"
    file_service_url: str = "http://localhost:8006"

    # CORS
    cors_origins: list[str] = field(default_factory=lambda: [
        "http://localhost:3000",
        "http://localhost:5173",
    ])
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = field(default_factory=lambda: ["*"])
    cors_allow_headers: list[str] = field(default_factory=lambda: ["*"])

    # Rate limiting
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)

    # Timeouts
    timeout: TimeoutConfig = field(default_factory=TimeoutConfig)

    # Circuit breaker
    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)

    # JWT
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"

    @property
    def service_routes(self) -> dict[str, str]:
        return {
            "auth": self.auth_service_url,
            "billing": self.billing_service_url,
            "workspaces": self.workspace_service_url,
            "analytics": self.analytics_service_url,
            "notifications": self.notification_service_url,
            "files": self.file_service_url,
        }

    @classmethod
    def from_env(cls) -> GatewaySettings:
        return cls(
            host=os.getenv("GATEWAY_HOST", "0.0.0.0"),
            port=int(os.getenv("GATEWAY_PORT", "8000")),
            debug=os.getenv("GATEWAY_DEBUG", "false").lower() == "true",
            auth_service_url=os.getenv("AUTH_SERVICE_URL", "http://localhost:8001"),
            billing_service_url=os.getenv("BILLING_SERVICE_URL", "http://localhost:8002"),
            workspace_service_url=os.getenv("WORKSPACE_SERVICE_URL", "http://localhost:8003"),
            analytics_service_url=os.getenv("ANALYTICS_SERVICE_URL", "http://localhost:8004"),
            notification_service_url=os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8005"),
            file_service_url=os.getenv("FILE_SERVICE_URL", "http://localhost:8006"),
            jwt_secret=os.getenv("JWT_SECRET", "change-me-in-production"),
            cors_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(","),
        )
