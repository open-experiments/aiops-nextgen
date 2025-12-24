"""Redis client wrapper with pub/sub support.

Spec Reference: specs/08-integration-matrix.md Section 5 and 6.2

Database Layout:
- DB 0: PubSub, Events (aiops:events:*)
- DB 1: Rate Limiting (ratelimit:user:{user_id}:*)
- DB 2: Caching (cache:{service}:{key})
- DB 3: Sessions (session:{session_id})
"""

from .client import RedisClient, RedisDB

__all__ = [
    "RedisClient",
    "RedisDB",
]
