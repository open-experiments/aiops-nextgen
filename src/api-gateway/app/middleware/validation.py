"""Request Validation Middleware.

Spec Reference: specs/06-api-gateway.md Section 5

Validates incoming requests:
- JSON schema validation per endpoint
- Query parameter validation
- Returns 422 with detailed errors
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from shared.observability import get_logger

logger = get_logger(__name__)


# Request body size limits per endpoint pattern
REQUEST_SIZE_LIMITS = {
    "/api/v1/chat/": 64 * 1024,  # 64KB for chat messages
    "/api/v1/reports/": 16 * 1024,  # 16KB for report requests
    "/api/v1/clusters/": 128 * 1024,  # 128KB for cluster registration
    "default": 1024 * 1024,  # 1MB default
}

# Required fields per endpoint pattern
REQUIRED_FIELDS = {
    "POST:/api/v1/clusters": ["name", "api_server_url"],
    "POST:/api/v1/chat/sessions": [],
    "POST:/api/v1/chat/sessions/{session_id}/messages": ["content"],
    "POST:/api/v1/reports/generate": ["report_type", "cluster_ids"],
    "POST:/api/v1/anomaly/detect": ["cluster_id"],
    "POST:/api/v1/anomaly/rca": ["cluster_id"],
}

# Field type validators
FIELD_VALIDATORS = {
    "cluster_id": lambda x: isinstance(x, str) and len(x) > 0,
    "cluster_ids": lambda x: isinstance(x, list) and all(isinstance(i, str) for i in x),
    "name": lambda x: isinstance(x, str) and 1 <= len(x) <= 63,
    "api_server_url": lambda x: isinstance(x, str) and x.startswith(("http://", "https://")),
    "content": lambda x: isinstance(x, str) and len(x) > 0,
    "report_type": lambda x: x
    in ["executive_summary", "detailed_analysis", "incident_report", "capacity_plan"],
    "hours": lambda x: isinstance(x, int) and 1 <= x <= 720,
    "limit": lambda x: isinstance(x, int) and 1 <= x <= 1000,
}


class ValidationError:
    """Represents a validation error."""

    def __init__(self, field: str, message: str, value: Any = None):
        self.field = field
        self.message = message
        self.value = value

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        result = {
            "field": self.field,
            "message": self.message,
        }
        if self.value is not None:
            result["value"] = str(self.value)[:100]  # Truncate long values
        return result


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """Middleware for validating incoming requests."""

    async def dispatch(self, request: Request, call_next):
        """Process request through validation."""
        # Skip validation for certain paths
        skip_paths = ["/health", "/ready", "/metrics", "/docs", "/openapi.json", "/redoc"]
        if request.url.path in skip_paths:
            return await call_next(request)

        # Skip validation for GET requests (query params handled by FastAPI)
        if request.method == "GET":
            return await call_next(request)

        # Validate content type for POST/PUT/PATCH
        if request.method in ("POST", "PUT", "PATCH"):
            content_type = request.headers.get("content-type", "")
            if not content_type.startswith("application/json"):
                # Allow requests without body
                content_length = request.headers.get("content-length", "0")
                if content_length != "0":
                    return JSONResponse(
                        status_code=415,
                        content={
                            "detail": "Unsupported Media Type",
                            "message": "Content-Type must be application/json",
                        },
                    )

        # Validate request body size
        size_error = await self._validate_body_size(request)
        if size_error:
            return size_error

        # Validate request body content
        if request.method in ("POST", "PUT", "PATCH"):
            body_error = await self._validate_body(request)
            if body_error:
                return body_error

        return await call_next(request)

    async def _validate_body_size(self, request: Request) -> JSONResponse | None:
        """Validate request body size."""
        content_length = request.headers.get("content-length")
        if not content_length:
            return None

        try:
            size = int(content_length)
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={
                    "detail": "Invalid Content-Length",
                    "message": "Content-Length header must be a valid integer",
                },
            )

        # Find applicable limit
        limit = REQUEST_SIZE_LIMITS["default"]
        for pattern, pattern_limit in REQUEST_SIZE_LIMITS.items():
            if pattern != "default" and request.url.path.startswith(pattern):
                limit = pattern_limit
                break

        if size > limit:
            return JSONResponse(
                status_code=413,
                content={
                    "detail": "Request Entity Too Large",
                    "message": f"Request body exceeds maximum size of {limit} bytes",
                    "max_size": limit,
                    "actual_size": size,
                },
            )

        return None

    async def _validate_body(self, request: Request) -> JSONResponse | None:
        """Validate request body content."""
        # Read body
        try:
            body = await request.body()
            if not body:
                return None  # Empty body is OK for some endpoints
            data = json.loads(body)
        except json.JSONDecodeError as e:
            return JSONResponse(
                status_code=422,
                content={
                    "detail": "Validation Error",
                    "errors": [
                        {
                            "field": "body",
                            "message": f"Invalid JSON: {e.msg}",
                        }
                    ],
                },
            )

        # Find required fields for this endpoint
        endpoint_key = f"{request.method}:{request.url.path}"
        required = REQUIRED_FIELDS.get(endpoint_key)

        # Try pattern matching for dynamic paths
        if required is None:
            for pattern, fields in REQUIRED_FIELDS.items():
                if self._path_matches_pattern(endpoint_key, pattern):
                    required = fields
                    break

        if required is None:
            return None  # No validation rules for this endpoint

        # Validate required fields
        errors = []
        for field in required:
            if field not in data:
                errors.append(ValidationError(field, f"Field '{field}' is required"))
            elif field in FIELD_VALIDATORS:
                validator = FIELD_VALIDATORS[field]
                if not validator(data[field]):
                    errors.append(
                        ValidationError(
                            field,
                            f"Invalid value for field '{field}'",
                            data[field],
                        )
                    )

        # Validate optional fields if present
        for field, value in data.items():
            if field in FIELD_VALIDATORS and value is not None:
                validator = FIELD_VALIDATORS[field]
                if not validator(value):
                    errors.append(
                        ValidationError(
                            field,
                            f"Invalid value for field '{field}'",
                            value,
                        )
                    )

        if errors:
            return JSONResponse(
                status_code=422,
                content={
                    "detail": "Validation Error",
                    "errors": [e.to_dict() for e in errors],
                },
            )

        return None

    def _path_matches_pattern(self, path: str, pattern: str) -> bool:
        """Check if path matches pattern with placeholders."""
        path_parts = path.split("/")
        pattern_parts = pattern.split("/")

        if len(path_parts) != len(pattern_parts):
            return False

        for path_part, pattern_part in zip(path_parts, pattern_parts, strict=True):
            if pattern_part.startswith("{") and pattern_part.endswith("}"):
                continue  # Placeholder matches anything
            if path_part != pattern_part:
                return False

        return True


def create_validation_error_response(errors: list[ValidationError]) -> JSONResponse:
    """Create a validation error response.

    Args:
        errors: List of validation errors

    Returns:
        JSONResponse with 422 status
    """
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation Error",
            "errors": [e.to_dict() for e in errors],
        },
    )
