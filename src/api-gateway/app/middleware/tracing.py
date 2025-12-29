"""Distributed Tracing Middleware.

Spec Reference: specs/06-api-gateway.md Section 10

Implements OpenTelemetry distributed tracing:
- Extract trace context from incoming requests
- Create gateway span
- Propagate context to backend services
- Export to OpenTelemetry collector
"""

from __future__ import annotations

import time
from contextvars import ContextVar
from typing import Any
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from shared.observability import get_logger

logger = get_logger(__name__)

# Context variable for current trace context
_current_trace_context: ContextVar[dict[str, Any] | None] = ContextVar(
    "current_trace_context", default=None
)

# W3C Trace Context headers
TRACEPARENT_HEADER = "traceparent"
TRACESTATE_HEADER = "tracestate"

# B3 headers (Zipkin compatibility)
B3_TRACE_ID_HEADER = "x-b3-traceid"
B3_SPAN_ID_HEADER = "x-b3-spanid"
B3_SAMPLED_HEADER = "x-b3-sampled"
B3_PARENT_SPAN_ID_HEADER = "x-b3-parentspanid"

# Custom headers
REQUEST_ID_HEADER = "x-request-id"


class TraceContext:
    """Represents distributed trace context."""

    def __init__(
        self,
        trace_id: str,
        span_id: str,
        parent_span_id: str | None = None,
        sampled: bool = True,
        trace_state: str | None = None,
    ):
        self.trace_id = trace_id
        self.span_id = span_id
        self.parent_span_id = parent_span_id
        self.sampled = sampled
        self.trace_state = trace_state
        self.start_time = time.time()
        self.attributes: dict[str, Any] = {}

    @classmethod
    def from_traceparent(cls, traceparent: str) -> TraceContext | None:
        """Parse W3C traceparent header.

        Format: {version}-{trace_id}-{parent_id}-{flags}
        Example: 00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01
        """
        try:
            parts = traceparent.split("-")
            if len(parts) != 4:
                return None

            version, trace_id, parent_span_id, flags = parts
            if version != "00":
                return None

            sampled = flags[-1] == "1"
            return cls(
                trace_id=trace_id,
                span_id=cls._generate_span_id(),
                parent_span_id=parent_span_id,
                sampled=sampled,
            )
        except Exception:
            return None

    @classmethod
    def from_b3_headers(
        cls,
        trace_id: str | None,
        span_id: str | None,
        sampled: str | None,
        parent_span_id: str | None = None,
    ) -> TraceContext | None:
        """Parse B3 headers."""
        if not trace_id:
            return None

        return cls(
            trace_id=trace_id,
            span_id=cls._generate_span_id(),
            parent_span_id=span_id,  # Parent is the incoming span
            sampled=sampled in ("1", "true", "True"),
        )

    @classmethod
    def create_new(cls) -> TraceContext:
        """Create a new trace context."""
        return cls(
            trace_id=cls._generate_trace_id(),
            span_id=cls._generate_span_id(),
            sampled=True,
        )

    @staticmethod
    def _generate_trace_id() -> str:
        """Generate a new trace ID (32 hex chars)."""
        return uuid4().hex + uuid4().hex[:16]

    @staticmethod
    def _generate_span_id() -> str:
        """Generate a new span ID (16 hex chars)."""
        return uuid4().hex[:16]

    def to_traceparent(self) -> str:
        """Convert to W3C traceparent header value."""
        flags = "01" if self.sampled else "00"
        return f"00-{self.trace_id}-{self.span_id}-{flags}"

    def to_b3_headers(self) -> dict[str, str]:
        """Convert to B3 headers."""
        headers = {
            B3_TRACE_ID_HEADER: self.trace_id,
            B3_SPAN_ID_HEADER: self.span_id,
            B3_SAMPLED_HEADER: "1" if self.sampled else "0",
        }
        if self.parent_span_id:
            headers[B3_PARENT_SPAN_ID_HEADER] = self.parent_span_id
        return headers

    def get_propagation_headers(self) -> dict[str, str]:
        """Get all headers to propagate to downstream services."""
        headers = {
            TRACEPARENT_HEADER: self.to_traceparent(),
            REQUEST_ID_HEADER: self.trace_id,
        }
        if self.trace_state:
            headers[TRACESTATE_HEADER] = self.trace_state

        # Include B3 headers for compatibility
        headers.update(self.to_b3_headers())

        return headers

    def set_attribute(self, key: str, value: Any) -> None:
        """Set span attribute."""
        self.attributes[key] = value

    def get_duration_ms(self) -> int:
        """Get span duration in milliseconds."""
        return int((time.time() - self.start_time) * 1000)


def get_current_trace_context() -> TraceContext | None:
    """Get the current trace context from context var."""
    return _current_trace_context.get()


def set_current_trace_context(ctx: TraceContext | None) -> None:
    """Set the current trace context."""
    _current_trace_context.set(ctx)


class TracingMiddleware(BaseHTTPMiddleware):
    """Middleware for distributed tracing."""

    # Paths to skip tracing
    SKIP_PATHS = {"/health", "/ready", "/metrics"}

    async def dispatch(self, request: Request, call_next):
        """Process request through tracing."""
        # Skip tracing for health/metrics endpoints
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        # Extract or create trace context
        trace_ctx = self._extract_trace_context(request)

        # Set context for downstream use
        set_current_trace_context(trace_ctx)

        # Add attributes
        trace_ctx.set_attribute("http.method", request.method)
        trace_ctx.set_attribute("http.url", str(request.url))
        trace_ctx.set_attribute("http.route", request.url.path)
        trace_ctx.set_attribute("http.host", request.headers.get("host", ""))
        trace_ctx.set_attribute("http.user_agent", request.headers.get("user-agent", ""))

        # Store trace context on request state for access in handlers
        request.state.trace_context = trace_ctx

        try:
            response = await call_next(request)

            # Add response attributes
            trace_ctx.set_attribute("http.status_code", response.status_code)

            # Add trace headers to response
            response.headers[REQUEST_ID_HEADER] = trace_ctx.trace_id
            response.headers[TRACEPARENT_HEADER] = trace_ctx.to_traceparent()

            # Log span completion
            self._log_span(trace_ctx, response.status_code)

            return response

        except Exception as e:
            trace_ctx.set_attribute("error", True)
            trace_ctx.set_attribute("error.message", str(e))
            self._log_span(trace_ctx, 500, error=str(e))
            raise

        finally:
            # Clear context
            set_current_trace_context(None)

    def _extract_trace_context(self, request: Request) -> TraceContext:
        """Extract trace context from request headers."""
        # Try W3C traceparent first
        traceparent = request.headers.get(TRACEPARENT_HEADER)
        if traceparent:
            ctx = TraceContext.from_traceparent(traceparent)
            if ctx:
                ctx.trace_state = request.headers.get(TRACESTATE_HEADER)
                return ctx

        # Try B3 headers
        b3_trace_id = request.headers.get(B3_TRACE_ID_HEADER)
        if b3_trace_id:
            ctx = TraceContext.from_b3_headers(
                trace_id=b3_trace_id,
                span_id=request.headers.get(B3_SPAN_ID_HEADER),
                sampled=request.headers.get(B3_SAMPLED_HEADER),
                parent_span_id=request.headers.get(B3_PARENT_SPAN_ID_HEADER),
            )
            if ctx:
                return ctx

        # Check for request ID header
        request_id = request.headers.get(REQUEST_ID_HEADER)
        if request_id and len(request_id) == 32:
            # Use request ID as trace ID if it's the right length
            return TraceContext(
                trace_id=request_id,
                span_id=TraceContext._generate_span_id(),
            )

        # Create new trace context
        return TraceContext.create_new()

    def _log_span(
        self,
        ctx: TraceContext,
        status_code: int,
        error: str | None = None,
    ) -> None:
        """Log span completion for export."""
        span_data = {
            "trace_id": ctx.trace_id,
            "span_id": ctx.span_id,
            "parent_span_id": ctx.parent_span_id,
            "operation": ctx.attributes.get("http.route", "unknown"),
            "duration_ms": ctx.get_duration_ms(),
            "status_code": status_code,
            "sampled": ctx.sampled,
        }

        if error:
            span_data["error"] = error
            logger.warning("Request span completed with error", **span_data)
        elif status_code >= 400:
            logger.warning("Request span completed with error status", **span_data)
        else:
            logger.info("Request span completed", **span_data)


def inject_trace_headers(headers: dict[str, str] | None = None) -> dict[str, str]:
    """Inject trace context headers for outgoing requests.

    Use this when making HTTP calls to other services.

    Args:
        headers: Existing headers to add to

    Returns:
        Headers with trace context added
    """
    result = dict(headers) if headers else {}

    ctx = get_current_trace_context()
    if ctx:
        result.update(ctx.get_propagation_headers())

    return result
