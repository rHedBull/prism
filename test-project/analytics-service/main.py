from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from clickhouse_driver import Client as ClickHouseClient
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from analytics_service.api.dashboard_routes import set_services as set_dashboard_services
from analytics_service.api.query_routes import set_query_service
from analytics_service.api.routes import router as api_router
from analytics_service.collectors.api_collector import (
    router as collector_router,
    set_ingestion_service,
)
from analytics_service.collectors.kafka_collector import KafkaCollector
from analytics_service.config.settings import settings
from analytics_service.services.aggregation_service import AggregationService
from analytics_service.services.ingestion_service import IngestionService
from analytics_service.services.query_service import QueryService

logger = logging.getLogger(settings.service_name)

engine = create_async_engine(
    settings.postgres_url,
    pool_size=10,
    max_overflow=5,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

clickhouse_client: ClickHouseClient | None = None
kafka_collector: KafkaCollector | None = None
ingestion_service: IngestionService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global clickhouse_client, kafka_collector, ingestion_service

    logger.info("Starting %s", settings.service_name)

    # Initialize ClickHouse client
    clickhouse_client = ClickHouseClient.from_url(settings.clickhouse_url)

    # Initialize services
    ingestion_service = IngestionService(clickhouse_client)
    query_service = QueryService(clickhouse_client)
    aggregation_service = AggregationService(clickhouse_client)

    # Wire up services to route handlers
    set_ingestion_service(ingestion_service)
    set_query_service(query_service)
    set_dashboard_services(query_service, aggregation_service)

    # Start ingestion buffer flush loop
    await ingestion_service.start()

    # Start Kafka consumer
    kafka_collector = KafkaCollector(ingestion_service)
    try:
        await kafka_collector.start()
    except Exception as exc:
        logger.warning("Failed to start Kafka collector (will retry): %s", exc)

    logger.info("All analytics services initialized")
    yield

    # Shutdown
    if kafka_collector:
        await kafka_collector.stop()
    if ingestion_service:
        await ingestion_service.stop()
    await engine.dispose()
    logger.info("Shutdown complete for %s", settings.service_name)


app = FastAPI(
    title="Analytics Service",
    description="Event ingestion, analytics queries, and dashboard aggregations",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(api_router, prefix="/api/v1")
app.include_router(collector_router, prefix="/api/v1")
