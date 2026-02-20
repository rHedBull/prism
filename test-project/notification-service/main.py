from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from notification_service.api.notification_routes import set_dependencies as set_notif_deps
from notification_service.api.preference_routes import set_dependencies as set_pref_deps
from notification_service.api.routes import router as api_router
from notification_service.channels.email_channel import EmailChannel
from notification_service.channels.in_app_channel import InAppChannel
from notification_service.channels.webhook_channel import WebhookChannel
from notification_service.config.settings import settings
from notification_service.services.dispatcher import NotificationDispatcher
from notification_service.services.template_service import TemplateService

logger = logging.getLogger(settings.service_name)

engine = create_async_engine(
    settings.postgres_url,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

redis_pool: aioredis.Redis | None = None
dispatcher: NotificationDispatcher | None = None


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global redis_pool, dispatcher

    logger.info("Starting %s", settings.service_name)

    redis_pool = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        max_connections=50,
    )

    # Initialize channels
    email_channel = EmailChannel()
    in_app_channel = InAppChannel(redis_pool)
    webhook_channel = WebhookChannel()
    template_service = TemplateService()

    # Wire dependencies to route handlers
    set_notif_deps(get_db_session, dispatcher)
    set_pref_deps(get_db_session)

    async with engine.begin() as conn:
        logger.info("Database connection pool established")

    yield

    if redis_pool:
        await redis_pool.aclose()
    await engine.dispose()
    logger.info("Shutdown complete for %s", settings.service_name)


app = FastAPI(
    title="Notification Service",
    description="Multi-channel notification delivery with templates and preferences",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(api_router, prefix="/api/v1")
