"""Elasticsearch async client wrapper.

Provides document indexing, search, bulk operations, and index lifecycle
management for full-text search and log aggregation.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Sequence

from elasticsearch import AsyncElasticsearch, helpers

logger = logging.getLogger(__name__)

_client: AsyncElasticsearch | None = None


async def connect(
    hosts: list[str] | None = None,
    *,
    api_key: str | None = None,
    basic_auth: tuple[str, str] | None = None,
    ca_certs: str | None = None,
    verify_certs: bool = True,
    request_timeout: int = 30,
    max_retries: int = 3,
    retry_on_timeout: bool = True,
) -> AsyncElasticsearch:
    """Establish an async connection to Elasticsearch.

    Args:
        hosts: List of Elasticsearch node URLs (e.g. ``["https://es:9200"]``).
        api_key: API key for authentication (preferred over basic_auth).
        basic_auth: Tuple of ``(username, password)`` for basic auth.
        ca_certs: Path to CA certificate bundle for TLS verification.
        verify_certs: Whether to verify TLS certificates.
        request_timeout: Default request timeout in seconds.
        max_retries: Number of retries on connection failure.
        retry_on_timeout: Retry requests that time out.

    Returns:
        A connected :class:`AsyncElasticsearch` client.
    """
    global _client

    if _client is not None:
        return _client

    if hosts is None:
        hosts = ["https://localhost:9200"]

    kwargs: dict[str, Any] = {
        "hosts": hosts,
        "verify_certs": verify_certs,
        "request_timeout": request_timeout,
        "max_retries": max_retries,
        "retry_on_timeout": retry_on_timeout,
    }

    if api_key:
        kwargs["api_key"] = api_key
    elif basic_auth:
        kwargs["basic_auth"] = basic_auth

    if ca_certs:
        kwargs["ca_certs"] = ca_certs

    _client = AsyncElasticsearch(**kwargs)

    # Verify connectivity
    info = await _client.info()
    logger.info(
        "Elasticsearch connected: %s (cluster: %s, version: %s)",
        hosts,
        info["cluster_name"],
        info["version"]["number"],
    )
    return _client


def _get_client() -> AsyncElasticsearch:
    """Return the active client or raise if not connected."""
    if _client is None:
        raise RuntimeError("Elasticsearch not connected. Call connect() first.")
    return _client


async def index_document(
    index: str,
    document: dict[str, Any],
    *,
    doc_id: str | None = None,
    pipeline: str | None = None,
    refresh: bool = False,
) -> str:
    """Index a single document.

    Args:
        index: Target index name.
        document: Document body as a dict.
        doc_id: Optional explicit document ID.
        pipeline: Ingest pipeline to apply.
        refresh: If True, make the document searchable immediately.

    Returns:
        The document ID assigned by Elasticsearch.
    """
    client = _get_client()

    kwargs: dict[str, Any] = {"index": index, "document": document}
    if doc_id:
        kwargs["id"] = doc_id
    if pipeline:
        kwargs["pipeline"] = pipeline
    if refresh:
        kwargs["refresh"] = "true"

    result = await client.index(**kwargs)
    logger.debug("Indexed document %s in '%s'", result["_id"], index)
    return result["_id"]


async def search(
    index: str,
    query: dict[str, Any],
    *,
    size: int = 20,
    from_: int = 0,
    sort: list[dict[str, Any]] | None = None,
    source_includes: list[str] | None = None,
    highlight: dict[str, Any] | None = None,
    aggregations: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute a search query against an index.

    Args:
        index: Index name or pattern (e.g. ``logs-*``).
        query: Elasticsearch query DSL body.
        size: Maximum number of hits to return.
        from_: Offset for pagination.
        sort: Sort clause.
        source_includes: Fields to include in ``_source``.
        highlight: Highlight configuration.
        aggregations: Aggregation definitions.

    Returns:
        The full Elasticsearch response dict including ``hits`` and ``aggregations``.
    """
    client = _get_client()

    body: dict[str, Any] = {"query": query, "size": size, "from": from_}
    if sort:
        body["sort"] = sort
    if source_includes:
        body["_source"] = {"includes": source_includes}
    if highlight:
        body["highlight"] = highlight
    if aggregations:
        body["aggs"] = aggregations

    start = datetime.utcnow()
    result = await client.search(index=index, body=body)
    elapsed_ms = (datetime.utcnow() - start).total_seconds() * 1000

    total = result["hits"]["total"]["value"]
    logger.debug(
        "Search '%s' returned %d/%d hits in %.1fms",
        index,
        len(result["hits"]["hits"]),
        total,
        elapsed_ms,
    )
    return result


async def bulk_index(
    index: str,
    documents: Sequence[dict[str, Any]],
    *,
    id_field: str | None = None,
    pipeline: str | None = None,
    chunk_size: int = 500,
    raise_on_error: bool = True,
) -> tuple[int, list[dict[str, Any]]]:
    """Bulk-index a batch of documents using the streaming helper.

    Args:
        index: Target index name.
        documents: Sequence of document dicts.
        id_field: If set, use this field from each document as ``_id``.
        pipeline: Ingest pipeline to apply.
        chunk_size: Number of documents per bulk request.
        raise_on_error: Raise on any indexing error.

    Returns:
        Tuple of (success_count, error_list).
    """
    client = _get_client()

    def _action_gen():
        for doc in documents:
            action = {"_index": index, "_source": doc}
            if id_field and id_field in doc:
                action["_id"] = doc[id_field]
            if pipeline:
                action["pipeline"] = pipeline
            yield action

    start = datetime.utcnow()
    success_count, errors = await helpers.async_bulk(
        client,
        _action_gen(),
        chunk_size=chunk_size,
        raise_on_error=raise_on_error,
        stats_only=False,
    )
    elapsed_ms = (datetime.utcnow() - start).total_seconds() * 1000

    logger.info(
        "Bulk indexed %d documents into '%s' in %.1fms (%d errors)",
        success_count,
        index,
        elapsed_ms,
        len(errors),
    )
    return success_count, errors


async def close() -> None:
    """Close the Elasticsearch connection."""
    global _client

    if _client is not None:
        await _client.close()
        _client = None
        logger.info("Elasticsearch connection closed.")
