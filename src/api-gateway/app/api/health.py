"""Health check endpoints.

Spec Reference: specs/06-api-gateway.md Section 12
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Request

router = APIRouter()

# Track service start time
_start_time = time.time()


@router.get(
    "/health",
    summary="Health check",
    description="Basic health check endpoint.",
)
async def health():
    """Basic health check.

    Spec Reference: specs/06-api-gateway.md Section 12.1
    """
    return {
        "status": "healthy",
        "service": "api-gateway",
        "version": "0.1.0",
        "uptime_seconds": int(time.time() - _start_time),
    }


@router.get(
    "/ready",
    summary="Readiness check",
    description="Check if service is ready to receive traffic.",
)
async def ready(request: Request):
    """Readiness check.

    Verifies Redis and backend services are reachable.

    Spec Reference: specs/06-api-gateway.md Section 12.1
    """
    checks = {
        "redis": False,
    }

    # Check Redis
    try:
        redis = request.app.state.redis
        health_result = await redis.health_check()
        checks["redis"] = health_result.get("status") == "healthy"
    except Exception:
        pass

    all_ready = all(checks.values())

    return {
        "status": "ready" if all_ready else "not_ready",
        "checks": checks,
    }


@router.get(
    "/health/detailed",
    summary="Detailed health check",
    description="Aggregated health from all backend services.",
)
async def health_detailed(request: Request):
    """Detailed health check with backend status.

    Spec Reference: specs/06-api-gateway.md Section 12.2
    """
    http_client = request.app.state.http_client
    backends = request.app.state.backends

    components = {}

    for name, url in backends.items():
        try:
            start = time.time()
            response = await http_client.get(f"{url}/health", timeout=5.0)
            latency_ms = int((time.time() - start) * 1000)

            if response.status_code == 200:
                components[name] = {
                    "status": "healthy",
                    "latency_ms": latency_ms,
                }
            else:
                components[name] = {
                    "status": "unhealthy",
                    "latency_ms": latency_ms,
                    "error": f"HTTP {response.status_code}",
                }
        except Exception as e:
            components[name] = {
                "status": "unhealthy",
                "error": str(e),
            }

    # Check Redis
    try:
        redis = request.app.state.redis
        start = time.time()
        await redis.health_check()
        latency_ms = int((time.time() - start) * 1000)
        components["redis"] = {"status": "healthy", "latency_ms": latency_ms}
    except Exception as e:
        components["redis"] = {"status": "unhealthy", "error": str(e)}

    all_healthy = all(
        c.get("status") == "healthy" for c in components.values()
    )

    return {
        "status": "healthy" if all_healthy else "degraded",
        "components": components,
    }
