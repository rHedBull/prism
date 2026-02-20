from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from auth_service.api.routes import api_router
from auth_service.config.settings import settings

logger = logging.getLogger(settings.service_name)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    engine = create_async_engine(
        settings.postgres_url,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
        echo=settings.debug,
    )
    app.state.db_pool = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    app.state.redis = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
    )
    logger.info("Database and Redis connection pools initialized")

    yield

    await app.state.redis.aclose()
    await engine.dispose()
    logger.info("Connection pools closed")


app = FastAPI(
    title="Auth Service",
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(api_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}
