from __future__ import annotations

from pydantic_settings import BaseSettings


class WorkspaceSettings(BaseSettings):
    """Configuration for the workspace service."""

    model_config = {"env_prefix": "WORKSPACE_"}

    postgres_url: str = "postgresql+asyncpg://prism:prism@localhost:5432/prism_workspaces"
    redis_url: str = "redis://localhost:6379/0"

    max_workspaces_per_tenant: int = 50
    max_members_per_workspace: int = 200

    billing_service_url: str = "http://billing-service:8000"
    notification_service_url: str = "http://notification-service:8000"
    event_bus_url: str = "amqp://guest:guest@localhost:5672/"

    service_name: str = "workspace-service"
    log_level: str = "INFO"


settings = WorkspaceSettings()
