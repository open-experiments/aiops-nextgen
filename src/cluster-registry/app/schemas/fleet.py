"""Fleet summary schemas.

Spec Reference: specs/02-cluster-registry.md Section 4.2
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class FleetSummary(BaseModel):
    """Fleet summary statistics.

    Spec Reference: specs/02-cluster-registry.md Section 4.2 - Fleet Summary
    """

    total_clusters: int = Field(description="Total number of clusters")
    by_state: dict[str, int] = Field(default_factory=dict, description="Cluster count by state")
    by_type: dict[str, int] = Field(default_factory=dict, description="Cluster count by type")
    by_environment: dict[str, int] = Field(
        default_factory=dict, description="Cluster count by environment"
    )
    total_gpu_count: int = Field(default=0, description="Total GPU count across fleet")
    clusters_with_cnf: int = Field(default=0, description="Clusters with CNF workloads")
    avg_health_score: float = Field(default=0.0, description="Average health score across fleet")


class ClusterHealthSummary(BaseModel):
    """Health summary for a single cluster."""

    cluster_id: str
    cluster_name: str
    state: str
    health_score: int
    last_check_at: str | None


class FleetHealth(BaseModel):
    """Fleet health overview.

    Spec Reference: specs/02-cluster-registry.md Section 4.1 - Fleet Operations
    """

    total_clusters: int
    healthy: int
    degraded: int
    offline: int
    unknown: int
    clusters: list[ClusterHealthSummary]
