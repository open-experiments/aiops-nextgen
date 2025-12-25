"""Health check endpoints.

Spec Reference: specs/08-integration-matrix.md Section 8
"""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get(
    "/health",
    summary="Health check",
    description="Basic health check endpoint.",
)
async def health():
    """Basic health check.

    Spec Reference: specs/08-integration-matrix.md Section 8
    """
    return {"status": "healthy", "service": "realtime-streaming"}


@router.get(
    "/ready",
    summary="Readiness check",
    description="Check if service is ready to receive traffic.",
)
async def ready(request: Request):
    """Readiness check.

    Verifies Redis connection and WebSocket hub are working.

    Spec Reference: specs/08-integration-matrix.md Section 8
    """
    checks = {
        "redis": False,
        "hub": False,
    }

    # Check Redis
    try:
        redis = request.app.state.redis
        health_result = await redis.health_check()
        checks["redis"] = health_result.get("status") == "healthy"
    except Exception:
        pass

    # Check WebSocket hub
    try:
        hub = request.app.state.hub
        checks["hub"] = hub is not None
    except Exception:
        pass

    all_ready = all(checks.values())

    return {
        "status": "ready" if all_ready else "not_ready",
        "checks": checks,
    }
