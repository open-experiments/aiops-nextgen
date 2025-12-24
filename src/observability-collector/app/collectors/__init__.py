"""Collectors for Observability Collector.

Spec Reference: specs/03-observability-collector.md Section 6
"""

from .gpu_collector import GPUCollector
from .prometheus_collector import PrometheusCollector

__all__ = ["GPUCollector", "PrometheusCollector"]
