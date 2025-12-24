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
    return {"status": "healthy", "service": "cluster-registry"}


@router.get(
    "/ready",
    summary="Readiness check",
    description="Check if service is ready to receive traffic.",
)
async def ready(request: Request):
    """Readiness check.

    Verifies database and Redis connections are working.

    Spec Reference: specs/08-integration-matrix.md Section 8
    """
    checks = {
        "database": False,
        "redis": False,
    }

    # Check database
    try:
        async with request.app.state.session_factory() as session:
            await session.execute("SELECT 1")
            checks["database"] = True
    except Exception:
        pass

    # Check Redis
    try:
        redis = request.app.state.redis
        await redis.ping()
        checks["redis"] = True
    except Exception:
        pass

    all_ready = all(checks.values())

    return {
        "status": "ready" if all_ready else "not_ready",
        "checks": checks,
    }
