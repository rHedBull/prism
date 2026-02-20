from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class PlanConfig(BaseSettings):
    free_price_id: str = ""
    starter_price_id: str = ""
    pro_price_id: str = ""
    enterprise_price_id: str = ""


class BillingSettings(BaseSettings):
    billing_db_url: str = "postgresql+asyncpg://billing:billing@localhost:5433/billing_db"

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_api_version: str = "2024-12-18.acacia"

    plans: PlanConfig = Field(default_factory=PlanConfig)

    usage_quota_free: int = 1_000
    usage_quota_starter: int = 10_000
    usage_quota_pro: int = 100_000
    usage_quota_enterprise: int = -1  # unlimited

    auth_service_url: str = "http://auth-service:8000"
    service_name: str = "billing-service"
    debug: bool = False

    model_config = {"env_prefix": "BILLING_", "env_nested_delimiter": "__"}


settings = BillingSettings()
