"""Observability module for structured logging, metrics, and tracing.

Spec References:
- specs/00-overview.md Section 9 - Observability requirements
- specs/09-deployment.md Section 8.1 - Configuration
- specs/09-deployment.md Section 10 - ServiceMonitor, PrometheusRule
"""

from .logging import (
    RequestContextManager,
    get_logger,
    log_database_query,
    log_external_call_end,
    log_external_call_start,
    log_request_end,
    log_request_start,
    request_id_var,
    setup_logging,
    span_id_var,
    trace_id_var,
    user_id_var,
)

__all__ = [
    # Setup
    "setup_logging",
    "get_logger",
    # Context
    "RequestContextManager",
    "request_id_var",
    "user_id_var",
    "trace_id_var",
    "span_id_var",
    # Logging helpers
    "log_request_start",
    "log_request_end",
    "log_external_call_start",
    "log_external_call_end",
    "log_database_query",
]
