from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from workspace_service.api.routes import router as api_router
from workspace_service.config.settings import settings

logger = logging.getLogger(settings.service_name)

engine = create_async_engine(
    settings.postgres_url,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    echo=False,
)

async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

redis_pool: aioredis.Redis | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global redis_pool

    logger.info("Starting %s", settings.service_name)

    redis_pool = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        max_connections=50,
    )

    async with engine.begin() as conn:
        logger.info("Database connection pool established")

    yield

    if redis_pool:
        await redis_pool.aclose()
    await engine.dispose()
    logger.info("Shutdown complete for %s", settings.service_name)


app = FastAPI(
    title="Workspace Service",
    description="Manages workspaces, projects, and team membership",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(api_router, prefix="/api/v1")


def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async def _get_session() -> AsyncGenerator[AsyncSession, None]:
        async with async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    return _get_session()


def get_redis() -> aioredis.Redis:
    assert redis_pool is not None, "Redis pool not initialized"
    return redis_pool
