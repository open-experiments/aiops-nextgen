"""Clients for Observability Collector.

Spec Reference: specs/03-observability-collector.md Section 9
"""

from .cluster_registry import ClusterRegistryClient
from .prometheus import (
    PrometheusAuthConfig,
    PrometheusAuthType,
    PrometheusClient,
    create_prometheus_client,
)

__all__ = [
    "ClusterRegistryClient",
    "PrometheusAuthConfig",
    "PrometheusAuthType",
    "PrometheusClient",
    "create_prometheus_client",
]
