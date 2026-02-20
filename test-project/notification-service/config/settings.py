from __future__ import annotations

from pydantic_settings import BaseSettings


class NotificationSettings(BaseSettings):
    """Configuration for the notification service."""

    model_config = {"env_prefix": "NOTIFICATION_"}

    postgres_url: str = "postgresql+asyncpg://prism:prism@localhost:5432/prism_notifications"
    redis_url: str = "redis://localhost:6379/1"

    smtp_host: str = "smtp.sendgrid.net"
    smtp_port: int = 587
    smtp_user: str = "apikey"
    smtp_password: str = ""
    smtp_from_email: str = "noreply@prism.app"
    smtp_from_name: str = "Prism Platform"

    sendgrid_api_key: str = ""
    use_sendgrid_api: bool = False

    webhook_timeout: float = 10.0
    webhook_max_retries: int = 3
    webhook_retry_delay: float = 5.0

    template_directory: str = "templates"

    service_name: str = "notification-service"
    log_level: str = "INFO"


settings = NotificationSettings()
