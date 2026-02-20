"""Async PostgreSQL connection pool manager.

Supports multiple named connection pools (primary, analytics, billing)
using SQLAlchemy async engine with asyncpg driver.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from shared.schemas.base import TenantContext

logger = logging.getLogger(__name__)

# Default connection pool settings per database role
_POOL_DEFAULTS: dict[str, dict] = {
    "primary": {
        "pool_size": 20,
        "max_overflow": 10,
        "pool_timeout": 30,
        "pool_recycle": 1800,
        "pool_pre_ping": True,
    },
    "analytics": {
        "pool_size": 10,
        "max_overflow": 5,
        "pool_timeout": 60,
        "pool_recycle": 3600,
        "pool_pre_ping": True,
    },
    "billing": {
        "pool_size": 5,
        "max_overflow": 3,
        "pool_timeout": 15,
        "pool_recycle": 900,
        "pool_pre_ping": True,
    },
}

_engines: dict[str, AsyncEngine] = {}
_session_factories: dict[str, async_sessionmaker[AsyncSession]] = {}


async def create_pool(
    name: str,
    dsn: str,
    *,
    pool_size: int | None = None,
    max_overflow: int | None = None,
    pool_timeout: int | None = None,
    pool_recycle: int | None = None,
    echo: bool = False,
) -> AsyncEngine:
    """Create a named async connection pool.

    Args:
        name: Pool identifier (e.g. 'primary', 'analytics', 'billing').
        dsn: PostgreSQL DSN in the form ``postgresql+asyncpg://user:pass@host/db``.
        pool_size: Override default pool size for this role.
        max_overflow: Override default max overflow connections.
        pool_timeout: Seconds to wait for a connection from the pool.
        pool_recycle: Seconds before a connection is recycled.
        echo: If True, log all SQL statements.

    Returns:
        The created :class:`AsyncEngine`.

    Raises:
        ValueError: If a pool with *name* already exists.
    """
    if name in _engines:
        raise ValueError(f"Connection pool '{name}' already exists. Call close_pool('{name}') first.")

    defaults = _POOL_DEFAULTS.get(name, _POOL_DEFAULTS["primary"])

    engine = create_async_engine(
        dsn,
        pool_size=pool_size or defaults["pool_size"],
        max_overflow=max_overflow or defaults["max_overflow"],
        pool_timeout=pool_timeout or defaults["pool_timeout"],
        pool_recycle=pool_recycle or defaults["pool_recycle"],
        pool_pre_ping=defaults["pool_pre_ping"],
        echo=echo,
    )

    _engines[name] = engine
    _session_factories[name] = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    logger.info("Created connection pool '%s' -> %s (size=%d)", name, _sanitize_dsn(dsn), engine.pool.size())
    return engine


@asynccontextmanager
async def get_session(
    name: str = "primary",
    *,
    tenant: TenantContext | None = None,
) -> AsyncGenerator[AsyncSession, None]:
    """Yield an async session from the named pool.

    Automatically commits on success, rolls back on exception, and closes
    the session when the context exits.

    Args:
        name: Pool identifier.
        tenant: Optional tenant context; if provided, sets
            ``search_path`` to the tenant schema for row-level isolation.

    Yields:
        An :class:`AsyncSession` bound to the named engine.

    Raises:
        KeyError: If the named pool has not been created yet.
    """
    if name not in _session_factories:
        raise KeyError(
            f"No connection pool named '{name}'. "
            f"Available pools: {list(_session_factories.keys())}"
        )

    factory = _session_factories[name]
    session = factory()

    try:
        if tenant is not None:
            # Set tenant schema search path for row-level isolation
            await session.execute(
                f"SET search_path TO tenant_{tenant.tenant_id}, public"  # noqa: S608
            )
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def close_pool(name: str) -> None:
    """Dispose of a named connection pool and release all connections.

    Args:
        name: Pool identifier to close.

    Raises:
        KeyError: If the named pool does not exist.
    """
    if name not in _engines:
        raise KeyError(f"No connection pool named '{name}'.")

    engine = _engines.pop(name)
    _session_factories.pop(name, None)

    await engine.dispose()
    logger.info("Closed connection pool '%s'.", name)


async def close_all_pools() -> None:
    """Dispose of every registered connection pool."""
    names = list(_engines.keys())
    for name in names:
        await close_pool(name)
    logger.info("All connection pools closed.")


def get_engine(name: str = "primary") -> AsyncEngine:
    """Return the raw :class:`AsyncEngine` for a named pool.

    Useful for Alembic migrations or raw connection access.
    """
    if name not in _engines:
        raise KeyError(f"No connection pool named '{name}'.")
    return _engines[name]


def _sanitize_dsn(dsn: str) -> str:
    """Redact password from DSN for safe logging."""
    try:
        from urllib.parse import urlparse, urlunparse

        parsed = urlparse(dsn)
        if parsed.password:
            netloc = f"{parsed.username}:***@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
            return urlunparse(parsed._replace(netloc=netloc))
    except Exception:
        pass
    return "<dsn>"
