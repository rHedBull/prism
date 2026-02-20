from __future__ import annotations

from pydantic_settings import BaseSettings


class AnalyticsSettings(BaseSettings):
    """Configuration for the analytics service."""

    model_config = {"env_prefix": "ANALYTICS_"}

    clickhouse_url: str = "clickhouse://default:@localhost:9000/prism_analytics"
    postgres_url: str = "postgresql+asyncpg://prism:prism@localhost:5432/prism_analytics_config"
    kafka_brokers: str = "localhost:9092"
    kafka_consumer_group: str = "analytics-service"
    kafka_events_topic: str = "platform-events"

    batch_size: int = 1000
    batch_flush_interval_seconds: float = 5.0

    service_name: str = "analytics-service"
    log_level: str = "INFO"


settings = AnalyticsSettings()
