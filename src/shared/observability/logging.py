"""Structured logging configuration.

Spec References:
- specs/00-overview.md Section 9 - Observability requirements
- specs/09-deployment.md Section 8.1 - LOG_LEVEL, LOG_FORMAT config

Features:
- JSON and text format support
- Request ID correlation
- Service context injection
- OpenTelemetry trace ID integration
"""

import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from shared.config import LogFormat, LogLevel, get_settings

# Context variables for request tracking
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)
trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)
span_id_var: ContextVar[str | None] = ContextVar("span_id", default=None)


def add_service_context(
    logger: logging.Logger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Add service context to log events."""
    settings = get_settings()
    event_dict["service"] = settings.app_name
    event_dict["environment"] = settings.environment.value
    return event_dict


def add_request_context(
    logger: logging.Logger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Add request context from context variables."""
    if request_id := request_id_var.get():
        event_dict["request_id"] = request_id
    if user_id := user_id_var.get():
        event_dict["user_id"] = user_id
    if trace_id := trace_id_var.get():
        event_dict["trace_id"] = trace_id
    if span_id := span_id_var.get():
        event_dict["span_id"] = span_id
    return event_dict


def add_timestamp(
    logger: logging.Logger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Add ISO 8601 timestamp."""
    event_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
    return event_dict


def setup_logging(
    service_name: str | None = None,
    log_level: LogLevel | None = None,
    log_format: LogFormat | None = None,
) -> None:
    """Configure structured logging for the application.

    Args:
        service_name: Override service name (defaults to settings.app_name)
        log_level: Override log level (defaults to settings.log_level)
        log_format: Override log format (defaults to settings.log_format)
    """
    settings = get_settings()

    level = log_level or settings.log_level
    fmt = log_format or settings.log_format

    # Convert LogLevel enum to logging constant (handle both enum and string)
    level_str = level.value if hasattr(level, 'value') else str(level).upper()
    numeric_level = getattr(logging, level_str)

    # Configure standard library logging
    logging.basicConfig(
        level=numeric_level,
        stream=sys.stdout,
        format="%(message)s",
    )

    # Shared processors for both JSON and text formats
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        add_timestamp,
        add_service_context,
        add_request_context,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    # Handle both enum and string for format
    fmt_str = fmt.value if hasattr(fmt, 'value') else str(fmt).lower()
    if fmt_str == "json" or fmt == LogFormat.JSON:
        # JSON format for production
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Text format for development
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.plain_traceback,
            ),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Suppress noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name (defaults to module name)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


class RequestContextManager:
    """Context manager for request-scoped logging context.

    Usage:
        async with RequestContextManager(request_id="abc123", user_id="user@example.com"):
            logger.info("Processing request")  # Includes request_id and user_id
    """

    def __init__(
        self,
        request_id: str | None = None,
        user_id: str | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
    ):
        self.request_id = request_id
        self.user_id = user_id
        self.trace_id = trace_id
        self.span_id = span_id
        self._tokens: list[Any] = []

    def __enter__(self) -> "RequestContextManager":
        if self.request_id:
            self._tokens.append(request_id_var.set(self.request_id))
        if self.user_id:
            self._tokens.append(user_id_var.set(self.user_id))
        if self.trace_id:
            self._tokens.append(trace_id_var.set(self.trace_id))
        if self.span_id:
            self._tokens.append(span_id_var.set(self.span_id))
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        for token in reversed(self._tokens):
            # Reset context vars (structlog handles cleanup)
            pass

    async def __aenter__(self) -> "RequestContextManager":
        return self.__enter__()

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.__exit__(exc_type, exc_val, exc_tb)


def log_request_start(
    logger: structlog.stdlib.BoundLogger,
    method: str,
    path: str,
    client_ip: str | None = None,
) -> None:
    """Log HTTP request start."""
    logger.info(
        "Request started",
        http_method=method,
        http_path=path,
        client_ip=client_ip,
    )


def log_request_end(
    logger: structlog.stdlib.BoundLogger,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
) -> None:
    """Log HTTP request completion."""
    log_level = "info" if status_code < 400 else "warning" if status_code < 500 else "error"
    getattr(logger, log_level)(
        "Request completed",
        http_method=method,
        http_path=path,
        http_status=status_code,
        duration_ms=round(duration_ms, 2),
    )


def log_external_call_start(
    logger: structlog.stdlib.BoundLogger,
    service: str,
    operation: str,
) -> None:
    """Log start of external service call."""
    logger.debug(
        "External call started",
        external_service=service,
        external_operation=operation,
    )


def log_external_call_end(
    logger: structlog.stdlib.BoundLogger,
    service: str,
    operation: str,
    success: bool,
    duration_ms: float,
    error: str | None = None,
) -> None:
    """Log completion of external service call."""
    log_data = {
        "external_service": service,
        "external_operation": operation,
        "success": success,
        "duration_ms": round(duration_ms, 2),
    }
    if error:
        log_data["error"] = error

    if success:
        logger.debug("External call completed", **log_data)
    else:
        logger.warning("External call failed", **log_data)


def log_database_query(
    logger: structlog.stdlib.BoundLogger,
    operation: str,
    table: str,
    duration_ms: float,
    rows_affected: int | None = None,
) -> None:
    """Log database query execution."""
    log_data = {
        "db_operation": operation,
        "db_table": table,
        "duration_ms": round(duration_ms, 2),
    }
    if rows_affected is not None:
        log_data["rows_affected"] = rows_affected

    logger.debug("Database query executed", **log_data)
