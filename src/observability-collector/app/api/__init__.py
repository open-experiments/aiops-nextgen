"""API endpoints for Observability Collector.

Spec Reference: specs/03-observability-collector.md Section 4
"""

from . import alerts, cnf, gpu, health, logs, metrics, traces

__all__ = ["alerts", "cnf", "gpu", "health", "logs", "metrics", "traces"]
