"""Clients for Observability Collector.

Spec Reference: specs/03-observability-collector.md Section 9
"""

from .cluster_registry import ClusterRegistryClient

__all__ = ["ClusterRegistryClient"]
