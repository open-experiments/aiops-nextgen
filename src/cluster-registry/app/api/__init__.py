"""API routers for Cluster Registry.

Spec Reference: specs/02-cluster-registry.md Section 4
"""

from . import clusters, fleet, health

__all__ = ["clusters", "fleet", "health"]
