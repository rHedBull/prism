"""ClickHouse async client for analytics workloads.

Wraps ``clickhouse-connect`` with connection pooling, batch inserts,
and query parameter binding for the analytics pipeline.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Sequence

import clickhouse_connect
from clickhouse_connect.driver.asyncclient import AsyncClient

logger = logging.getLogger(__name__)

_client: AsyncClient | None = None


async def connect(
    host: str = "localhost",
    port: int = 8443,
    username: str = "default",
    password: str = "",
    database: str = "analytics",
    *,
    secure: bool = True,
    connect_timeout: int = 10,
    send_receive_timeout: int = 300,
    compress: bool = True,
) -> AsyncClient:
    """Establish an async connection to ClickHouse.

    Args:
        host: ClickHouse server hostname.
        port: ClickHouse HTTPS native port.
        username: Authentication username.
        password: Authentication password.
        database: Default database to query against.
        secure: Use TLS for the connection.
        connect_timeout: Connection timeout in seconds.
        send_receive_timeout: Query timeout in seconds.
        compress: Enable LZ4 compression for data transfer.

    Returns:
        An :class:`AsyncClient` connected to ClickHouse.
    """
    global _client

    if _client is not None:
        return _client

    _client = await clickhouse_connect.get_async_client(
        host=host,
        port=port,
        username=username,
        password=password,
        database=database,
        secure=secure,
        connect_timeout=connect_timeout,
        send_receive_timeout=send_receive_timeout,
        compress=compress,
    )

    logger.info(
        "ClickHouse connection established: %s:%d/%s",
        host,
        port,
        database,
    )
    return _client


def _get_client() -> AsyncClient:
    """Return the active client or raise if not connected."""
    if _client is None:
        raise RuntimeError("ClickHouse not connected. Call connect() first.")
    return _client


async def execute_query(
    query: str,
    parameters: dict[str, Any] | None = None,
    *,
    settings: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Execute a SELECT query and return rows as a list of dicts.

    Args:
        query: ClickHouse SQL query with optional ``{param:Type}`` placeholders.
        parameters: Query parameter bindings.
        settings: Per-query ClickHouse settings overrides.

    Returns:
        List of row dicts keyed by column name.
    """
    client = _get_client()

    start = datetime.utcnow()
    result = await client.query(query, parameters=parameters, settings=settings)
    elapsed_ms = (datetime.utcnow() - start).total_seconds() * 1000

    columns = result.column_names
    rows = [dict(zip(columns, row)) for row in result.result_rows]

    logger.debug(
        "ClickHouse query returned %d rows in %.1fms: %s",
        len(rows),
        elapsed_ms,
        query[:120],
    )
    return rows


async def insert_batch(
    table: str,
    rows: Sequence[Sequence[Any]],
    column_names: list[str],
    *,
    settings: dict[str, Any] | None = None,
) -> int:
    """Insert a batch of rows into a ClickHouse table.

    Args:
        table: Target table name (may include database prefix).
        rows: Iterable of row tuples matching *column_names* order.
        column_names: Column names for the insert.
        settings: Per-query ClickHouse settings overrides.

    Returns:
        Number of rows inserted.
    """
    client = _get_client()

    if not rows:
        return 0

    start = datetime.utcnow()
    await client.insert(
        table,
        data=rows,
        column_names=column_names,
        settings=settings,
    )
    elapsed_ms = (datetime.utcnow() - start).total_seconds() * 1000

    logger.info(
        "Inserted %d rows into %s in %.1fms",
        len(rows),
        table,
        elapsed_ms,
    )
    return len(rows)


async def execute_command(query: str, parameters: dict[str, Any] | None = None) -> None:
    """Execute a DDL or non-SELECT statement (CREATE, ALTER, DROP, etc.).

    Args:
        query: ClickHouse SQL command.
        parameters: Optional query parameter bindings.
    """
    client = _get_client()
    await client.command(query, parameters=parameters)
    logger.debug("ClickHouse command executed: %s", query[:120])


async def close() -> None:
    """Close the ClickHouse connection."""
    global _client

    if _client is not None:
        await _client.close()
        _client = None
        logger.info("ClickHouse connection closed.")
