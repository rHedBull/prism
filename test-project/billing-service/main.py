from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from billing_service.api.routes import api_router
from billing_service.config.settings import settings

logger = logging.getLogger(settings.service_name)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    engine = create_async_engine(
        settings.billing_db_url,
        pool_size=15,
        max_overflow=5,
        pool_pre_ping=True,
        echo=settings.debug,
    )
    app.state.db_pool = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    logger.info("Billing database pool initialized (separate DB)")

    yield

    await engine.dispose()
    logger.info("Billing database pool closed")


app = FastAPI(
    title="Billing Service",
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(api_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}
