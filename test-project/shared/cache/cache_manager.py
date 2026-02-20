"""Multi-tier caching: local LRU (L1) + Redis (L2).

Provides a unified interface with automatic promotion/demotion between
tiers, TTL support, and pattern-based invalidation.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

import redis.asyncio as aioredis

from shared.db.redis_client import get_redis

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A single cache entry with value and expiration metadata."""

    value: Any
    expires_at: float | None = None  # Unix timestamp; None = no expiry

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.monotonic() > self.expires_at


class LRUCache:
    """Thread-safe in-process LRU cache (L1 tier)."""

    def __init__(self, max_size: int = 10_000) -> None:
        self._max_size = max_size
        self._store: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0

    async def get(self, key: str) -> Any | None:
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            if entry.is_expired:
                del self._store[key]
                self._misses += 1
                return None
            # Move to end (most recently used)
            self._store.move_to_end(key)
            self._hits += 1
            return entry.value

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        async with self._lock:
            expires_at = (time.monotonic() + ttl) if ttl else None
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = CacheEntry(value=value, expires_at=expires_at)

            # Evict oldest entries if over capacity
            while len(self._store) > self._max_size:
                self._store.popitem(last=False)

    async def delete(self, key: str) -> bool:
        async with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a glob pattern (e.g. ``user:*``)."""
        import fnmatch

        async with self._lock:
            matching = [k for k in self._store if fnmatch.fnmatch(k, pattern)]
            for k in matching:
                del self._store[k]
            return len(matching)

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()

    @property
    def stats(self) -> dict[str, int]:
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total, 4) if total else 0.0,
            "size": len(self._store),
        }


@dataclass
class CacheManager:
    """Two-tier cache: in-memory LRU (L1) backed by Redis (L2).

    Read path: L1 -> L2 -> miss.
    Write path: write to both L1 and L2.
    Invalidation: remove from both tiers.
    """

    namespace: str = "cache"
    l1_max_size: int = 10_000
    default_ttl: int = 300  # seconds
    _l1: LRUCache = field(init=False)

    def __post_init__(self) -> None:
        self._l1 = LRUCache(max_size=self.l1_max_size)

    def _redis_key(self, key: str) -> str:
        """Build a namespaced Redis key."""
        return f"{self.namespace}:{key}"

    async def get(self, key: str) -> Any | None:
        """Fetch a value from cache (L1 first, then L2).

        On L2 hit, the value is promoted into L1 for subsequent fast access.

        Args:
            key: Cache key.

        Returns:
            Cached value, or None on miss.
        """
        # L1 lookup
        value = await self._l1.get(key)
        if value is not None:
            return value

        # L2 lookup
        try:
            redis = await get_redis()
            raw = await redis.get(self._redis_key(key))
            if raw is not None:
                value = json.loads(raw)
                # Promote to L1
                ttl = await redis.ttl(self._redis_key(key))
                await self._l1.set(key, value, ttl=ttl if ttl > 0 else None)
                return value
        except Exception:
            logger.warning("Redis L2 cache read failed for key '%s'", key, exc_info=True)

        return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        """Store a value in both L1 and L2 caches.

        Args:
            key: Cache key.
            value: Value to cache (must be JSON-serializable).
            ttl: Time-to-live in seconds. Uses ``default_ttl`` if None.
        """
        ttl = ttl if ttl is not None else self.default_ttl

        # L1
        await self._l1.set(key, value, ttl=ttl)

        # L2
        try:
            redis = await get_redis()
            serialized = json.dumps(value, default=str)
            if ttl > 0:
                await redis.setex(self._redis_key(key), ttl, serialized)
            else:
                await redis.set(self._redis_key(key), serialized)
        except Exception:
            logger.warning("Redis L2 cache write failed for key '%s'", key, exc_info=True)

    async def invalidate(self, key: str) -> None:
        """Remove a key from both L1 and L2.

        Args:
            key: Cache key to invalidate.
        """
        await self._l1.delete(key)

        try:
            redis = await get_redis()
            await redis.delete(self._redis_key(key))
        except Exception:
            logger.warning("Redis L2 cache delete failed for key '%s'", key, exc_info=True)

    async def invalidate_pattern(self, pattern: str) -> int:
        """Remove all keys matching a glob pattern from both tiers.

        Args:
            pattern: Glob pattern (e.g. ``user:123:*``).

        Returns:
            Total number of keys removed across both tiers.
        """
        # L1
        l1_count = await self._l1.delete_pattern(pattern)

        # L2 — use SCAN to avoid blocking Redis
        l2_count = 0
        try:
            redis = await get_redis()
            redis_pattern = self._redis_key(pattern)
            cursor = 0
            while True:
                cursor, keys = await redis.scan(cursor, match=redis_pattern, count=200)
                if keys:
                    await redis.delete(*keys)
                    l2_count += len(keys)
                if cursor == 0:
                    break
        except Exception:
            logger.warning("Redis L2 pattern invalidation failed for '%s'", pattern, exc_info=True)

        logger.debug(
            "Invalidated pattern '%s': L1=%d, L2=%d",
            pattern,
            l1_count,
            l2_count,
        )
        return l1_count + l2_count

    @property
    def stats(self) -> dict[str, Any]:
        """Return L1 cache statistics."""
        return self._l1.stats
