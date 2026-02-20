from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from file_service.api.file_routes import set_dependencies
from file_service.api.routes import router as api_router
from file_service.config.settings import settings
from file_service.storage.s3_storage import S3Storage

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

s3_storage: S3Storage | None = None


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
    global s3_storage

    logger.info("Starting %s", settings.service_name)

    s3_storage = S3Storage()

    set_dependencies(get_db_session, s3_storage)

    async with engine.begin() as conn:
        logger.info("Database connection pool established")

    yield

    await engine.dispose()
    logger.info("Shutdown complete for %s", settings.service_name)


app = FastAPI(
    title="File Service",
    description="File upload, download, and management with S3 storage",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(api_router, prefix="/api/v1")
