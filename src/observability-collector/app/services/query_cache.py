"""Query result caching with Redis.

Spec Reference: specs/03-observability-collector.md Section 3.1.3

Caches Prometheus query results to reduce load on target clusters
and improve response times for repeated queries.
"""

import hashlib
import json
from datetime import datetime

import redis.asyncio as redis
from pydantic import BaseModel

from shared.config import get_settings
from shared.observability import get_logger

logger = get_logger(__name__)

# Redis DB for caching
CACHE_DB = 2


class CacheEntry(BaseModel):
    """Cached query result."""

    data: dict
    cached_at: datetime
    ttl_seconds: int
    cluster_id: str
    query_hash: str


class QueryCache:
    """Redis-based query result cache."""

    def __init__(self):
        self.settings = get_settings()
        self._client: redis.Redis | None = None
        self._default_ttl = 30  # seconds

    async def _get_client(self) -> redis.Redis:
        """Get or create Redis client."""
        if self._client is None:
            self._client = redis.from_url(
                f"{self.settings.redis.url}/{CACHE_DB}",
                decode_responses=True,
            )

        return self._client

    def _make_cache_key(
        self,
        cluster_id: str,
        query: str,
        start: datetime | None = None,
        end: datetime | None = None,
        step: str | None = None,
    ) -> str:
        """Generate cache key from query parameters.

        Uses SHA256 hash of query components to ensure consistent keys.
        """
        key_parts = [
            cluster_id,
            query,
        ]

        if start:
            # Round to step interval for better cache hits
            key_parts.append(str(int(start.timestamp())))
        if end:
            key_parts.append(str(int(end.timestamp())))
        if step:
            key_parts.append(step)

        key_string = "|".join(key_parts)
        query_hash = hashlib.sha256(key_string.encode()).hexdigest()[:16]

        return f"prom:query:{cluster_id}:{query_hash}"

    async def get(
        self,
        cluster_id: str,
        query: str,
        start: datetime | None = None,
        end: datetime | None = None,
        step: str | None = None,
    ) -> dict | None:
        """Get cached query result.

        Args:
            cluster_id: Cluster identifier
            query: PromQL query
            start: Range query start time
            end: Range query end time
            step: Range query step

        Returns:
            Cached result dict or None if not cached
        """
        client = await self._get_client()
        cache_key = self._make_cache_key(cluster_id, query, start, end, step)

        try:
            cached = await client.get(cache_key)

            if cached:
                logger.debug(
                    "Cache hit",
                    cluster_id=cluster_id,
                    cache_key=cache_key,
                )
                return json.loads(cached)

            logger.debug(
                "Cache miss",
                cluster_id=cluster_id,
                cache_key=cache_key,
            )
            return None

        except redis.RedisError as e:
            logger.warning("Cache read error", error=str(e))
            return None

    async def set(
        self,
        cluster_id: str,
        query: str,
        result: dict,
        start: datetime | None = None,
        end: datetime | None = None,
        step: str | None = None,
        ttl_seconds: int | None = None,
    ) -> bool:
        """Cache query result.

        Args:
            cluster_id: Cluster identifier
            query: PromQL query
            result: Query result to cache
            start: Range query start time
            end: Range query end time
            step: Range query step
            ttl_seconds: Cache TTL (defaults to 30s)

        Returns:
            True if cached successfully
        """
        client = await self._get_client()
        cache_key = self._make_cache_key(cluster_id, query, start, end, step)
        ttl = ttl_seconds or self._default_ttl

        try:
            await client.setex(
                cache_key,
                ttl,
                json.dumps(result),
            )

            logger.debug(
                "Cached result",
                cluster_id=cluster_id,
                cache_key=cache_key,
                ttl=ttl,
            )
            return True

        except redis.RedisError as e:
            logger.warning("Cache write error", error=str(e))
            return False

    async def invalidate(
        self,
        cluster_id: str,
        query: str | None = None,
    ) -> int:
        """Invalidate cached results.

        Args:
            cluster_id: Cluster identifier
            query: Optional specific query to invalidate

        Returns:
            Number of invalidated entries
        """
        client = await self._get_client()

        # Invalidate all queries for cluster
        pattern = f"prom:query:{cluster_id}:*"

        try:
            keys = []
            async for key in client.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                await client.delete(*keys)

            logger.info(
                "Invalidated cache",
                cluster_id=cluster_id,
                count=len(keys),
            )
            return len(keys)

        except redis.RedisError as e:
            logger.warning("Cache invalidation error", error=str(e))
            return 0

    async def close(self):
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None


# Singleton instance
query_cache = QueryCache()
