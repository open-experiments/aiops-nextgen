"""Redis client wrapper.

Spec Reference: specs/08-integration-matrix.md Section 5 and 6.2

Redis Database Layout:
- DB 0: PubSub, Events (aiops:events:*)
- DB 1: Rate Limiting (ratelimit:user:{user_id}:*)
- DB 2: Caching (cache:{service}:{key})
- DB 3: Sessions (session:{session_id})
"""

import json
from collections.abc import Callable
from enum import IntEnum
from typing import Any

import redis.asyncio as redis
from pydantic import BaseModel

from shared.models import Event


class RedisDB(IntEnum):
    """Redis database numbers. Spec: Section 6.2"""

    PUBSUB = 0
    RATE_LIMIT = 1
    CACHE = 2
    SESSION = 3


class RedisClient:
    """Async Redis client with connection pooling.

    Spec Reference: specs/08-integration-matrix.md Section 6.2
    """

    def __init__(self, url: str = "redis://localhost:6379"):
        """Initialize Redis client.

        Args:
            url: Redis connection URL
        """
        self._url = url
        self._pools: dict[int, redis.ConnectionPool] = {}
        self._clients: dict[int, redis.Redis] = {}

    async def connect(self) -> None:
        """Initialize connection pools for all databases."""
        for db in RedisDB:
            pool = redis.ConnectionPool.from_url(
                self._url,
                db=db.value,
                decode_responses=True,
            )
            self._pools[db] = pool
            self._clients[db] = redis.Redis(connection_pool=pool)

    async def close(self) -> None:
        """Close all connections."""
        for client in self._clients.values():
            await client.close()
        for pool in self._pools.values():
            await pool.disconnect()

    def get_client(self, db: RedisDB) -> redis.Redis:
        """Get Redis client for specific database."""
        if db not in self._clients:
            raise RuntimeError("Redis client not connected. Call connect() first.")
        return self._clients[db]

    # =========================================================================
    # PubSub Operations (DB 0) - Spec Section 5
    # =========================================================================

    async def publish_event(self, event: Event) -> int:
        """Publish event to Redis PubSub.

        Spec Reference: Section 5.1 - Channel structure
        Channel: aiops:events:{type}:{optional-id}

        Args:
            event: Event to publish

        Returns:
            Number of subscribers that received the message
        """
        client = self.get_client(RedisDB.PUBSUB)

        # Main channel receives all events
        main_channel = "aiops:events:all"

        # Type-specific channel (handle both enum and string due to use_enum_values=True)
        event_type_str = (
            event.event_type.value if hasattr(event.event_type, "value") else event.event_type
        )
        type_channel = f"aiops:events:{event_type_str.lower().split('_')[0]}"

        # Cluster-specific channel if applicable
        cluster_channel = None
        if event.cluster_id:
            cluster_channel = f"aiops:events:cluster:{event.cluster_id}"

        # Serialize event
        message = event.model_dump_json()

        # Publish to all relevant channels
        receivers = await client.publish(main_channel, message)

        await client.publish(type_channel, message)

        if cluster_channel:
            await client.publish(cluster_channel, message)

        return receivers

    async def subscribe(
        self,
        channels: list[str],
        callback: Callable[[str, str], Any],
    ) -> redis.client.PubSub:
        """Subscribe to Redis PubSub channels.

        Spec Reference: Section 5.1 - Channel structure

        Args:
            channels: List of channel patterns to subscribe to
            callback: Async callback function(channel, message)

        Returns:
            PubSub instance for managing subscription
        """
        client = self.get_client(RedisDB.PUBSUB)
        pubsub = client.pubsub()

        async def message_handler(message: dict[str, Any]) -> None:
            if message["type"] == "message":
                await callback(message["channel"], message["data"])

        for channel in channels:
            if "*" in channel:
                await pubsub.psubscribe(**{channel: message_handler})
            else:
                await pubsub.subscribe(**{channel: message_handler})

        return pubsub

    # =========================================================================
    # Rate Limiting Operations (DB 1) - Spec Section 6.2
    # =========================================================================

    async def check_rate_limit(
        self,
        user_id: str,
        endpoint: str,
        limit: int,
        window_seconds: int,
    ) -> tuple[bool, int]:
        """Check and increment rate limit counter.

        Key pattern: ratelimit:user:{user_id}:{endpoint}

        Args:
            user_id: User identifier
            endpoint: API endpoint being accessed
            limit: Maximum requests allowed in window
            window_seconds: Time window in seconds

        Returns:
            Tuple of (allowed: bool, remaining: int)
        """
        client = self.get_client(RedisDB.RATE_LIMIT)
        key = f"ratelimit:user:{user_id}:{endpoint}"

        # Use pipeline for atomic operations
        async with client.pipeline(transaction=True) as pipe:
            try:
                await pipe.incr(key)
                await pipe.expire(key, window_seconds)
                results = await pipe.execute()
                current = results[0]
            except redis.RedisError:
                # On error, allow the request
                return True, limit

        allowed = current <= limit
        remaining = max(0, limit - current)
        return allowed, remaining

    async def get_rate_limit_status(
        self,
        user_id: str,
        endpoint: str,
        limit: int,
    ) -> dict[str, Any]:
        """Get current rate limit status without incrementing.

        Args:
            user_id: User identifier
            endpoint: API endpoint
            limit: Maximum requests allowed

        Returns:
            Rate limit status dict
        """
        client = self.get_client(RedisDB.RATE_LIMIT)
        key = f"ratelimit:user:{user_id}:{endpoint}"

        current = await client.get(key)
        current_count = int(current) if current else 0
        ttl = await client.ttl(key)

        return {
            "limit": limit,
            "remaining": max(0, limit - current_count),
            "reset_in_seconds": max(0, ttl),
        }

    # =========================================================================
    # Cache Operations (DB 2) - Spec Section 6.2
    # =========================================================================

    async def cache_get(self, service: str, key: str) -> str | None:
        """Get cached value.

        Key pattern: cache:{service}:{key}

        Args:
            service: Service name (e.g., 'clusters', 'metrics')
            key: Cache key

        Returns:
            Cached value or None
        """
        client = self.get_client(RedisDB.CACHE)
        cache_key = f"cache:{service}:{key}"
        return await client.get(cache_key)

    async def cache_get_json(self, service: str, key: str) -> dict[str, Any] | None:
        """Get cached JSON value.

        Args:
            service: Service name
            key: Cache key

        Returns:
            Parsed JSON dict or None
        """
        value = await self.cache_get(service, key)
        if value:
            return json.loads(value)
        return None

    async def cache_set(
        self,
        service: str,
        key: str,
        value: str | dict[str, Any] | list[Any] | BaseModel,
        ttl_seconds: int = 300,
    ) -> None:
        """Set cached value.

        Key pattern: cache:{service}:{key}

        Args:
            service: Service name
            key: Cache key
            value: Value to cache (string, dict, or Pydantic model)
            ttl_seconds: Time-to-live in seconds (default: 5 minutes)
        """
        client = self.get_client(RedisDB.CACHE)
        cache_key = f"cache:{service}:{key}"

        if isinstance(value, BaseModel):
            serialized = value.model_dump_json()
        elif isinstance(value, (dict, list)):
            serialized = json.dumps(value, default=str)
        else:
            serialized = value

        await client.setex(cache_key, ttl_seconds, serialized)

    async def cache_delete(self, service: str, key: str) -> bool:
        """Delete cached value.

        Args:
            service: Service name
            key: Cache key

        Returns:
            True if key was deleted
        """
        client = self.get_client(RedisDB.CACHE)
        cache_key = f"cache:{service}:{key}"
        result = await client.delete(cache_key)
        return result > 0

    async def cache_invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all cache keys matching pattern.

        Spec Reference: Section 10.2 - Cache invalidation

        Args:
            pattern: Key pattern with wildcards (e.g., 'cache:clusters:*')

        Returns:
            Number of keys deleted
        """
        client = self.get_client(RedisDB.CACHE)
        deleted = 0

        async for key in client.scan_iter(match=pattern):
            await client.delete(key)
            deleted += 1

        return deleted

    # =========================================================================
    # Session Operations (DB 3) - Spec Section 6.2
    # =========================================================================

    async def session_get(self, session_id: str) -> dict[str, Any] | None:
        """Get session data.

        Key pattern: session:{session_id}

        Args:
            session_id: Session identifier

        Returns:
            Session data dict or None
        """
        client = self.get_client(RedisDB.SESSION)
        key = f"session:{session_id}"
        value = await client.get(key)
        if value:
            return json.loads(value)
        return None

    async def session_set(
        self,
        session_id: str,
        data: dict[str, Any],
        ttl_seconds: int = 3600,
    ) -> None:
        """Set session data.

        Args:
            session_id: Session identifier
            data: Session data to store
            ttl_seconds: Time-to-live in seconds (default: 1 hour)
        """
        client = self.get_client(RedisDB.SESSION)
        key = f"session:{session_id}"
        await client.setex(key, ttl_seconds, json.dumps(data, default=str))

    async def session_delete(self, session_id: str) -> bool:
        """Delete session.

        Args:
            session_id: Session identifier

        Returns:
            True if session was deleted
        """
        client = self.get_client(RedisDB.SESSION)
        key = f"session:{session_id}"
        result = await client.delete(key)
        return result > 0

    async def session_extend(self, session_id: str, ttl_seconds: int = 3600) -> bool:
        """Extend session TTL.

        Args:
            session_id: Session identifier
            ttl_seconds: New TTL in seconds

        Returns:
            True if TTL was set
        """
        client = self.get_client(RedisDB.SESSION)
        key = f"session:{session_id}"
        return await client.expire(key, ttl_seconds)

    # =========================================================================
    # Health Check
    # =========================================================================

    async def health_check(self) -> dict[str, Any]:
        """Check Redis connectivity.

        Returns:
            Health status dict
        """
        results = {}
        for db in RedisDB:
            try:
                client = self.get_client(db)
                await client.ping()
                results[db.name.lower()] = {"status": "healthy"}
            except Exception as e:
                results[db.name.lower()] = {"status": "unhealthy", "error": str(e)}

        all_healthy = all(r["status"] == "healthy" for r in results.values())
        return {
            "status": "healthy" if all_healthy else "unhealthy",
            "databases": results,
        }
