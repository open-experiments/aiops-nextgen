"""API endpoints for Observability Collector.

Spec Reference: specs/03-observability-collector.md Section 4
"""

from . import alerts, gpu, health, metrics

__all__ = ["alerts", "gpu", "health", "metrics"]
