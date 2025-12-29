"""Proxy endpoints for routing to backend services.

Spec Reference: specs/06-api-gateway.md Section 4.2
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from shared.observability import get_logger

logger = get_logger(__name__)

router = APIRouter()

# Route mapping per spec Section 4.2
ROUTE_MAP = {
    "/api/v1/clusters": "cluster-registry",
    "/api/v1/fleet": "cluster-registry",
    "/api/v1/metrics": "observability-collector",
    "/api/v1/traces": "observability-collector",
    "/api/v1/logs": "observability-collector",
    "/api/v1/alerts": "observability-collector",
    "/api/v1/gpu": "observability-collector",
    "/api/v1/cnf": "observability-collector",
    "/api/v1/chat": "intelligence-engine",
    "/api/v1/personas": "intelligence-engine",
    "/api/v1/analysis": "intelligence-engine",
    "/api/v1/reports": "intelligence-engine",
    "/api/v1/streaming": "realtime-streaming",
}


def get_backend_for_path(path: str) -> str | None:
    """Determine backend service for a given path.

    Args:
        path: Request path

    Returns:
        Backend service name or None if no match
    """
    for prefix, backend in ROUTE_MAP.items():
        if path.startswith(prefix):
            return backend
    return None


async def proxy_request(
    request: Request,
    backend: str,
    path: str,
) -> Response:
    """Proxy request to backend service.

    Args:
        request: Incoming request
        backend: Backend service name
        path: Request path

    Returns:
        Response from backend
    """
    http_client = request.app.state.http_client
    backends = request.app.state.backends

    backend_url = backends.get(backend)
    if not backend_url:
        return Response(
            content=f'{{"error": "Backend not configured: {backend}"}}',
            status_code=502,
            media_type="application/json",
        )

    # Build target URL
    target_url = f"{backend_url}{path}"
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"

    # Forward headers (exclude hop-by-hop headers)
    headers = {}
    for key, value in request.headers.items():
        if key.lower() not in (
            "host",
            "connection",
            "keep-alive",
            "transfer-encoding",
        ):
            headers[key] = value

    # Get request body
    body = await request.body()

    try:
        # Make request to backend
        response = await http_client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body,
        )

        # Build response headers
        response_headers = {}
        for key, value in response.headers.items():
            if key.lower() not in (
                "content-encoding",
                "content-length",
                "transfer-encoding",
            ):
                response_headers[key] = value

        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=response_headers,
            media_type=response.headers.get("content-type"),
        )

    except Exception as e:
        logger.error(
            "Backend request failed",
            backend=backend,
            path=path,
            error=str(e),
        )
        return Response(
            content=f'{{"error": "Backend unavailable: {str(e)}"}}',
            status_code=502,
            media_type="application/json",
        )


# Catch-all route for proxying
@router.api_route(
    "/api/v1/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    summary="Proxy to backend services",
    description="Routes requests to appropriate backend service.",
)
async def proxy_api(request: Request, path: str):
    """Proxy API requests to backend services.

    Spec Reference: specs/06-api-gateway.md Section 4.2
    """
    full_path = f"/api/v1/{path}"
    backend = get_backend_for_path(full_path)

    if not backend:
        return Response(
            content='{"error": "No backend configured for this path"}',
            status_code=404,
            media_type="application/json",
        )

    logger.debug(
        "Proxying request",
        path=full_path,
        backend=backend,
        method=request.method,
    )

    return await proxy_request(request, backend, full_path)


@router.api_route(
    "/mcp/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    summary="Proxy MCP protocol",
    description="Routes MCP requests to Intelligence Engine.",
)
async def proxy_mcp(request: Request, path: str):
    """Proxy MCP requests to Intelligence Engine.

    Spec Reference: specs/06-api-gateway.md Section 4.2
    """
    full_path = f"/mcp/{path}" if path else "/mcp"
    return await proxy_request(request, "intelligence-engine", full_path)
