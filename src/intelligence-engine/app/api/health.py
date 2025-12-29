"""Health check endpoints.

Spec Reference: specs/04-intelligence-engine.md
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
async def health_check(request: Request) -> dict:
    """Basic health check endpoint."""
    return {"status": "healthy", "service": "intelligence-engine"}


@router.get("/ready")
async def readiness_check(request: Request) -> dict:
    """Readiness check - verifies dependencies are available."""
    redis = request.app.state.redis
    llm_router = request.app.state.llm_router

    # Check Redis connection
    try:
        health = await redis.health_check()
        redis_healthy = health.get("status") == "healthy"
    except Exception:
        redis_healthy = False

    # Check LLM availability
    llm_available = llm_router is not None and llm_router.is_available()

    if redis_healthy and llm_available:
        return {
            "status": "ready",
            "redis": "connected",
            "llm": "available",
        }
    else:
        return {
            "status": "not_ready",
            "redis": "connected" if redis_healthy else "disconnected",
            "llm": "available" if llm_available else "unavailable",
        }


@router.get("/health/db")
async def database_health_check(request: Request) -> dict:
    """Database health check endpoint.

    Checks PostgreSQL connectivity if configured.
    """
    # Check if database session factory is available
    db_session_factory = getattr(request.app.state, "db_session_factory", None)

    if db_session_factory is None:
        return {
            "status": "unknown",
            "message": "Database not configured",
        }

    try:
        from sqlalchemy import select

        start = time.time()
        async with db_session_factory() as session:
            await session.execute(select(1))
        latency_ms = int((time.time() - start) * 1000)

        return {
            "status": "healthy",
            "latency_ms": latency_ms,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }
