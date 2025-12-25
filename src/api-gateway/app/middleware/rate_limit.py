"""Rate limiting middleware.

Spec Reference: specs/06-api-gateway.md Section 7
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from shared.observability import get_logger

logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using Redis.

    Spec Reference: specs/06-api-gateway.md Section 7

    Rate limits:
    - Per-user: 300 requests per minute
    - Per-endpoint: Configurable per endpoint
    """

    # Default rate limits per spec Section 7.1
    DEFAULT_LIMIT = 300  # requests per minute
    DEFAULT_WINDOW = 60  # seconds

    # Endpoint-specific limits per spec Section 7.1
    ENDPOINT_LIMITS = {
        "/api/v1/metrics/query": {"limit": 60, "window": 60},
        "/api/v1/chat/sessions": {"limit": 30, "window": 60},
        "/api/v1/reports": {"limit": 10, "window": 60},
    }

    # Paths to skip rate limiting
    SKIP_PATHS = {"/health", "/ready", "/docs", "/openapi.json", "/redoc"}

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request through rate limiter."""
        path = request.url.path

        # Skip rate limiting for health checks and docs
        if path in self.SKIP_PATHS:
            return await call_next(request)

        # Get user ID from header or use IP as fallback
        user_id = request.headers.get("X-User-ID")
        if not user_id:
            user_id = request.client.host if request.client else "anonymous"

        # Get rate limit config for endpoint
        limit_config = self._get_limit_config(path)
        limit = limit_config["limit"]
        window = limit_config["window"]

        # Check rate limit using Redis
        try:
            redis = request.app.state.redis
            allowed, remaining = await redis.check_rate_limit(
                user_id=user_id,
                endpoint=self._normalize_path(path),
                limit=limit,
                window_seconds=window,
            )

            if not allowed:
                logger.warning(
                    "Rate limit exceeded",
                    user_id=user_id,
                    path=path,
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": "Too many requests. Please retry later.",
                        }
                    },
                    headers={
                        "X-RateLimit-Limit": str(limit),
                        "X-RateLimit-Remaining": "0",
                        "Retry-After": str(window),
                    },
                )

            # Add rate limit headers to response
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(remaining)

            return response

        except Exception as e:
            # On Redis error, allow request but log warning
            logger.warning(
                "Rate limit check failed, allowing request",
                error=str(e),
            )
            return await call_next(request)

    def _get_limit_config(self, path: str) -> dict:
        """Get rate limit configuration for path."""
        for endpoint, config in self.ENDPOINT_LIMITS.items():
            if path.startswith(endpoint):
                return config
        return {"limit": self.DEFAULT_LIMIT, "window": self.DEFAULT_WINDOW}

    def _normalize_path(self, path: str) -> str:
        """Normalize path for rate limit key.

        Removes IDs from paths to group similar endpoints.
        """
        parts = path.split("/")
        normalized = []
        for part in parts:
            # Skip UUID-like parts
            if len(part) == 36 and "-" in part:
                normalized.append("*")
            else:
                normalized.append(part)
        return "/".join(normalized)
