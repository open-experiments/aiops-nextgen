"""Collectors for Observability Collector.

Spec Reference: specs/03-observability-collector.md Section 6
"""

from .cnf_collector import CNFCollector
from .gpu_collector import GPUCollector
from .loki_collector import LokiCollector
from .prometheus_collector import PrometheusCollector
from .tempo_collector import TempoCollector

__all__ = [
    "CNFCollector",
    "GPUCollector",
    "LokiCollector",
    "PrometheusCollector",
    "TempoCollector",
]
