"""Cluster request/response schemas.

Spec Reference: specs/02-cluster-registry.md Section 4.2
"""

from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from shared.models.cluster import (
    ClusterState,
    ClusterType,
    Connectivity,
    Environment,
    Platform,
)


class ClusterEndpoints(BaseModel):
    """Cluster observability endpoints.

    Spec Reference: specs/01-data-models.md Section 2.2
    """

    prometheus_url: str | None = None
    thanos_url: str | None = None
    tempo_url: str | None = None
    loki_url: str | None = None
    alertmanager_url: str | None = None


class ClusterStatus(BaseModel):
    """Cluster status model.

    Spec Reference: specs/01-data-models.md Section 2.3
    """

    state: ClusterState = ClusterState.UNKNOWN
    health_score: int = Field(default=0, ge=0, le=100)
    connectivity: Connectivity = Connectivity.DISCONNECTED
    last_check_at: datetime | None = None
    error_message: str | None = None
    prometheus_healthy: bool | None = None
    tempo_healthy: bool | None = None
    loki_healthy: bool | None = None


class ClusterCapabilities(BaseModel):
    """Cluster capabilities.

    Spec Reference: specs/01-data-models.md Section 2.4
    """

    has_gpu_nodes: bool = False
    gpu_count: int = 0
    gpu_types: list[str] = Field(default_factory=list)
    has_cnf_workloads: bool = False
    cnf_types: list[str] = Field(default_factory=list)
    has_prometheus: bool = False
    has_tempo: bool = False
    has_loki: bool = False
    has_alertmanager: bool = False
    openshift_version: str | None = None
    kubernetes_version: str | None = None


class ClusterCreateRequest(BaseModel):
    """Request to register a new cluster.

    Spec Reference: specs/02-cluster-registry.md Section 4.2
    """

    name: str = Field(
        ...,
        min_length=3,
        max_length=63,
        description="Unique cluster name (DNS-compatible)",
    )
    display_name: str | None = Field(
        None, max_length=128, description="Human-readable display name"
    )
    api_server_url: str = Field(..., description="Kubernetes API server URL")
    cluster_type: ClusterType = Field(
        default=ClusterType.SPOKE, description="Cluster type in hierarchy"
    )
    platform: Platform = Field(default=Platform.OPENSHIFT, description="Kubernetes platform")
    platform_version: str | None = Field(None, description="Platform version")
    region: str | None = Field(None, max_length=64, description="Geographic region")
    environment: Environment = Field(
        default=Environment.DEVELOPMENT, description="Deployment environment"
    )
    labels: dict[str, str] = Field(default_factory=dict, description="Custom labels for filtering")
    endpoints: ClusterEndpoints = Field(
        default_factory=ClusterEndpoints, description="Observability endpoints"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate cluster name is DNS-compatible.

        Spec Reference: specs/02-cluster-registry.md Section 7.1
        """
        pattern = r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$"
        if not re.match(pattern, v):
            raise ValueError(
                "Name must be DNS-compatible: lowercase alphanumeric, "
                "may include hyphens, 3-63 characters"
            )
        return v

    @field_validator("api_server_url")
    @classmethod
    def validate_api_server_url(cls, v: str) -> str:
        """Validate API server URL format."""
        if not v.startswith(("https://", "http://")):
            raise ValueError("API server URL must start with http:// or https://")
        return v


class ClusterUpdateRequest(BaseModel):
    """Request to update a cluster.

    Spec Reference: specs/02-cluster-registry.md Section 4.1
    """

    display_name: str | None = Field(None, max_length=128)
    cluster_type: ClusterType | None = None
    platform_version: str | None = None
    region: str | None = Field(None, max_length=64)
    environment: Environment | None = None
    labels: dict[str, str] | None = None
    endpoints: ClusterEndpoints | None = None


class ClusterResponse(BaseModel):
    """Cluster response model.

    Spec Reference: specs/02-cluster-registry.md Section 4.2
    """

    id: UUID
    name: str
    display_name: str | None
    api_server_url: str
    cluster_type: ClusterType
    platform: Platform
    platform_version: str | None
    region: str | None
    environment: Environment
    status: ClusterStatus
    capabilities: ClusterCapabilities | None
    endpoints: ClusterEndpoints
    labels: dict[str, str]
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime | None

    class Config:
        from_attributes = True


class ClusterListResponse(BaseModel):
    """Paginated cluster list response.

    Spec Reference: specs/02-cluster-registry.md Section 4.2
    """

    items: list[ClusterResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ClusterFilters(BaseModel):
    """Query filters for cluster list.

    Spec Reference: specs/02-cluster-registry.md Section 4.3
    """

    name: str | None = Field(None, description="Filter by cluster name (partial match)")
    cluster_type: ClusterType | None = Field(None, description="Filter by type")
    environment: Environment | None = Field(None, description="Filter by environment")
    region: str | None = Field(None, description="Filter by region")
    state: ClusterState | None = Field(None, description="Filter by status state")
    has_gpu: bool | None = Field(None, description="Filter clusters with GPU nodes")
    has_cnf: bool | None = Field(None, description="Filter clusters with CNF workloads")
    label: str | None = Field(None, description="Filter by label (key=value format)")
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")
