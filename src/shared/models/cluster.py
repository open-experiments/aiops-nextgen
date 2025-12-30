"""Cluster domain models.

Spec Reference: specs/01-data-models.md Section 2 - Cluster Domain Models
"""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import Field, field_validator

from .base import AIOpsBaseModel


# Enums (uppercase SNAKE_CASE as per spec conventions)
class ClusterType(str, Enum):
    """Cluster role in the fleet. Spec: Section 2.1"""

    HUB = "HUB"
    SPOKE = "SPOKE"
    EDGE = "EDGE"
    FAR_EDGE = "FAR_EDGE"


class Platform(str, Enum):
    """Cluster platform type. Spec: Section 2.1"""

    OPENSHIFT = "OPENSHIFT"
    KUBERNETES = "KUBERNETES"
    MICROSHIFT = "MICROSHIFT"


class Environment(str, Enum):
    """Deployment environment. Spec: Section 2.1"""

    PRODUCTION = "PRODUCTION"
    STAGING = "STAGING"
    DEVELOPMENT = "DEVELOPMENT"
    LAB = "LAB"


class ClusterState(str, Enum):
    """Current cluster state. Spec: Section 2.2"""

    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    DEGRADED = "DEGRADED"
    UNKNOWN = "UNKNOWN"
    PROVISIONING = "PROVISIONING"


class Connectivity(str, Enum):
    """Cluster connectivity status. Spec: Section 2.2"""

    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    INTERMITTENT = "INTERMITTENT"


class AuthType(str, Enum):
    """Authentication type for cluster access. Spec: Section 2.5"""

    KUBECONFIG = "KUBECONFIG"
    SERVICE_ACCOUNT = "SERVICE_ACCOUNT"
    OIDC = "OIDC"
    TOKEN = "TOKEN"  # Bearer token
    BASIC = "BASIC"  # Basic auth (username/password)
    CERTIFICATE = "CERTIFICATE"  # Client certificate


class CNFType(str, Enum):
    """Types of CNF workloads. Spec: Section 2.3"""

    VDU = "VDU"
    VCU = "VCU"
    UPF = "UPF"
    AMF = "AMF"
    SMF = "SMF"
    OTHER = "OTHER"


# Models
class ClusterStatus(AIOpsBaseModel):
    """Cluster health and connectivity status.

    Spec Reference: Section 2.2
    """

    state: ClusterState = ClusterState.UNKNOWN
    health_score: int = Field(default=0, ge=0, le=100, description="Overall health score (0-100)")
    last_error: str | None = None
    connectivity: Connectivity = Connectivity.DISCONNECTED
    api_server_healthy: bool = False
    prometheus_healthy: bool = False
    tempo_healthy: bool = False
    loki_healthy: bool = False


class ClusterCapabilities(AIOpsBaseModel):
    """Detected cluster capabilities.

    Spec Reference: Section 2.3
    """

    has_gpu: bool = False  # Short alias for has_gpu_nodes
    has_gpu_nodes: bool = False
    gpu_count: int = Field(default=0, ge=0)
    gpu_types: list[str] = Field(default_factory=list)
    has_prometheus: bool = True
    has_thanos: bool = False
    has_tempo: bool = False
    has_loki: bool = False
    has_service_mesh: bool = False
    has_cnf_workloads: bool = False
    cnf_types: list[CNFType] = Field(default_factory=list)


class ClusterEndpoints(AIOpsBaseModel):
    """Observability endpoints for the cluster.

    Spec Reference: Section 2.4
    """

    prometheus_url: str | None = Field(default=None, description="Prometheus/Thanos query endpoint")
    tempo_url: str | None = Field(default=None, description="Tempo query endpoint")
    loki_url: str | None = Field(default=None, description="Loki query endpoint")
    alertmanager_url: str | None = Field(default=None, description="Alertmanager API endpoint")


class Cluster(AIOpsBaseModel):
    """Represents a registered OpenShift/Kubernetes cluster.

    Spec Reference: Section 2.1
    """

    id: UUID
    name: str = Field(
        min_length=3,
        max_length=63,
        pattern=r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$",
        description="DNS-compatible cluster name",
    )
    display_name: str | None = Field(default=None, max_length=128)
    api_server_url: str = Field(description="Kubernetes API server URL")
    cluster_type: ClusterType = ClusterType.SPOKE
    platform: Platform = Platform.OPENSHIFT
    platform_version: str | None = None
    region: str | None = None
    environment: Environment = Environment.DEVELOPMENT
    status: ClusterStatus = Field(default_factory=ClusterStatus)
    capabilities: ClusterCapabilities = Field(default_factory=ClusterCapabilities)
    endpoints: ClusterEndpoints = Field(default_factory=ClusterEndpoints)
    labels: dict[str, str] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime | None = None
    last_seen_at: datetime | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        import re

        if not re.match(r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$", v):
            raise ValueError("Name must be DNS-compatible (lowercase alphanumeric with hyphens)")
        return v


class ClusterCredentials(AIOpsBaseModel):
    """Cluster access credentials (stored encrypted, never returned via API).

    Spec Reference: Section 2.5
    """

    auth_type: AuthType
    # Token-based auth
    token: str | None = Field(default=None, description="Bearer token for API access")
    # Basic auth
    username: str | None = Field(default=None, description="Username for basic auth")
    password: str | None = Field(default=None, description="Password for basic auth")
    # Certificate auth
    client_cert: str | None = Field(default=None, description="Client certificate PEM")
    client_key: str | None = Field(default=None, description="Client key PEM")
    # Kubeconfig
    kubeconfig: str | None = Field(default=None, description="Full kubeconfig content")
    # TLS settings
    skip_tls_verify: bool = Field(default=False, description="Skip TLS verification")
    ca_cert: str | None = Field(default=None, description="CA certificate PEM")


class ClusterCredentialsStored(AIOpsBaseModel):
    """Stored cluster credentials with metadata (internal use only).

    Spec Reference: Section 2.5
    """

    cluster_id: UUID
    auth_type: AuthType
    kubeconfig_encrypted: bytes | None = Field(
        default=None, description="AES-256 encrypted kubeconfig"
    )
    service_account_token_secret_ref: str | None = Field(
        default=None, description="Reference to K8s Secret containing SA token"
    )
    prometheus_token_secret_ref: str | None = Field(
        default=None, description="Reference to K8s Secret for Prometheus auth"
    )
    created_at: datetime
    expires_at: datetime | None = None


# Request/Response models for API
class ClusterCreate(AIOpsBaseModel):
    """Request model for creating a cluster."""

    name: str = Field(
        min_length=3,
        max_length=63,
        pattern=r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$",
    )
    display_name: str | None = Field(default=None, max_length=128)
    api_server_url: str
    cluster_type: ClusterType = ClusterType.SPOKE
    platform: Platform = Platform.OPENSHIFT
    platform_version: str | None = None
    region: str | None = None
    environment: Environment = Environment.DEVELOPMENT
    labels: dict[str, str] = Field(default_factory=dict)


class ClusterUpdate(AIOpsBaseModel):
    """Request model for updating a cluster."""

    display_name: str | None = None
    cluster_type: ClusterType | None = None
    platform_version: str | None = None
    region: str | None = None
    environment: Environment | None = None
    labels: dict[str, str] | None = None
