"""Health check endpoints.

Spec Reference: specs/03-observability-collector.md
"""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
async def health_check(request: Request) -> dict:
    """Basic health check endpoint."""
    return {"status": "healthy", "service": "observability-collector"}


@router.get("/ready")
async def readiness_check(request: Request) -> dict:
    """Readiness check - verifies dependencies are available."""
    redis = request.app.state.redis

    # Check Redis connection
    try:
        health = await redis.health_check()
        redis_healthy = health.get("status") == "healthy"
    except Exception:
        redis_healthy = False

    if redis_healthy:
        return {"status": "ready", "redis": "connected"}
    else:
        return {"status": "not_ready", "redis": "disconnected"}
