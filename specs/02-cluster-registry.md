# 02 - Cluster Registry Service

## Document Info
| Field | Value |
|-------|-------|
| Version | 0.1.0 |
| Status | Draft |
| Last Updated | 2024-12-24 |

---

## 1. Purpose

The Cluster Registry Service is the authoritative source for all managed cluster metadata, credentials, and health status. It provides:

- CRUD operations for cluster registration
- Secure credential storage and rotation
- Continuous health monitoring
- Capability discovery (GPU, CNF, observability stack)
- Event emission for cluster state changes

---

## 2. Responsibilities

| Responsibility | Description |
|----------------|-------------|
| **Cluster Lifecycle** | Register, update, delete clusters |
| **Credential Management** | Store, rotate, validate cluster credentials |
| **Health Monitoring** | Continuous cluster connectivity and health checks |
| **Capability Discovery** | Detect available features (GPU, Tempo, Loki, etc.) |
| **Event Publishing** | Emit events on cluster state changes |
| **Fleet Queries** | Provide filtered views of cluster fleet |

---

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CLUSTER REGISTRY SERVICE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                           API Layer                                     │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                 │ │
│  │  │ REST API     │  │ Internal API │  │ Health       │                 │ │
│  │  │ /api/v1/     │  │ (gRPC opt)   │  │ Endpoints    │                 │ │
│  │  │ clusters/*   │  │              │  │ /health,     │                 │ │
│  │  │              │  │              │  │ /ready       │                 │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                 │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         Service Layer                                   │ │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐ │ │
│  │  │ ClusterService   │  │ CredentialService│  │ DiscoveryService     │ │ │
│  │  │                  │  │                  │  │                      │ │ │
│  │  │ • create()       │  │ • store()        │  │ • discover_caps()    │ │ │
│  │  │ • update()       │  │ • rotate()       │  │ • detect_gpu()       │ │ │
│  │  │ • delete()       │  │ • validate()     │  │ • detect_cnf()       │ │ │
│  │  │ • get()          │  │ • get_for_use()  │  │ • detect_observ()    │ │ │
│  │  │ • list()         │  │                  │  │                      │ │ │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────────┘ │ │
│  │  ┌──────────────────┐  ┌──────────────────┐                           │ │
│  │  │ HealthService    │  │ EventService     │                           │ │
│  │  │                  │  │                  │                           │ │
│  │  │ • check_health() │  │ • publish()      │                           │ │
│  │  │ • run_checks()   │  │ • subscribe()    │                           │ │
│  │  │ • get_status()   │  │                  │                           │ │
│  │  └──────────────────┘  └──────────────────┘                           │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                        Data Layer                                       │ │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐ │ │
│  │  │ PostgreSQL       │  │ K8s Secrets      │  │ Redis                │ │ │
│  │  │ (Metadata)       │  │ (Credentials)    │  │ (Events, Cache)      │ │ │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
            ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
            │  Cluster A  │   │  Cluster B  │   │  Cluster N  │
            │  (K8s API)  │   │  (K8s API)  │   │  (K8s API)  │
            └─────────────┘   └─────────────┘   └─────────────┘
```

---

## 4. API Specification

### 4.1 REST Endpoints

#### Cluster CRUD

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/clusters` | Register new cluster |
| `GET` | `/api/v1/clusters` | List all clusters |
| `GET` | `/api/v1/clusters/{id}` | Get cluster by ID |
| `GET` | `/api/v1/clusters/by-name/{name}` | Get cluster by name |
| `PUT` | `/api/v1/clusters/{id}` | Update cluster |
| `DELETE` | `/api/v1/clusters/{id}` | Delete cluster |
| `GET` | `/api/v1/clusters/{id}/status` | Get cluster status |
| `POST` | `/api/v1/clusters/{id}/refresh` | Force refresh cluster data |

#### Credential Management

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/clusters/{id}/credentials` | Upload credentials |
| `POST` | `/api/v1/clusters/{id}/credentials/rotate` | Rotate credentials |
| `POST` | `/api/v1/clusters/{id}/credentials/validate` | Validate credentials |
| `DELETE` | `/api/v1/clusters/{id}/credentials` | Delete credentials |

#### Fleet Operations

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/fleet/summary` | Get fleet summary |
| `GET` | `/api/v1/fleet/health` | Get fleet health overview |
| `GET` | `/api/v1/fleet/capabilities` | Get aggregated capabilities |

---

### 4.2 Request/Response Examples

#### Register Cluster

**Request:**
```http
POST /api/v1/clusters
Content-Type: application/json

{
  "name": "prod-east-1",
  "display_name": "Production East 1",
  "api_server_url": "https://api.prod-east-1.example.com:6443",
  "cluster_type": "SPOKE",
  "platform": "OPENSHIFT",
  "region": "us-east-1",
  "environment": "PRODUCTION",
  "labels": {
    "team": "platform",
    "cost-center": "eng-001"
  },
  "endpoints": {
    "prometheus_url": "https://thanos-querier.openshift-monitoring.svc:9091"
  }
}
```

**Response:**
```http
HTTP/1.1 201 Created
Content-Type: application/json

{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "prod-east-1",
  "display_name": "Production East 1",
  "api_server_url": "https://api.prod-east-1.example.com:6443",
  "cluster_type": "SPOKE",
  "platform": "OPENSHIFT",
  "platform_version": null,
  "region": "us-east-1",
  "environment": "PRODUCTION",
  "status": {
    "state": "UNKNOWN",
    "health_score": 0,
    "connectivity": "DISCONNECTED"
  },
  "capabilities": null,
  "endpoints": {
    "prometheus_url": "https://thanos-querier.openshift-monitoring.svc:9091"
  },
  "labels": {
    "team": "platform",
    "cost-center": "eng-001"
  },
  "created_at": "2024-12-24T10:00:00Z",
  "updated_at": "2024-12-24T10:00:00Z"
}
```

#### Upload Credentials

**Request:**
```http
POST /api/v1/clusters/550e8400-e29b-41d4-a716-446655440000/credentials
Content-Type: application/json

{
  "auth_type": "KUBECONFIG",
  "kubeconfig": "apiVersion: v1\nkind: Config\n...",
  "prometheus_token": "sha256~xxxxx"
}
```

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "status": "stored",
  "validation": {
    "api_server": "success",
    "prometheus": "success"
  },
  "expires_at": "2025-01-24T10:00:00Z"
}
```

#### List Clusters with Filtering

**Request:**
```http
GET /api/v1/clusters?environment=PRODUCTION&has_gpu=true&page=1&page_size=20
```

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "prod-east-1",
      "status": {
        "state": "ONLINE",
        "health_score": 95
      },
      "capabilities": {
        "has_gpu_nodes": true,
        "gpu_count": 8
      }
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

#### Fleet Summary

**Request:**
```http
GET /api/v1/fleet/summary
```

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "total_clusters": 25,
  "by_state": {
    "ONLINE": 22,
    "DEGRADED": 2,
    "OFFLINE": 1
  },
  "by_type": {
    "HUB": 1,
    "SPOKE": 20,
    "EDGE": 4
  },
  "by_environment": {
    "PRODUCTION": 10,
    "STAGING": 8,
    "DEVELOPMENT": 7
  },
  "total_gpu_count": 128,
  "clusters_with_cnf": 5,
  "avg_health_score": 87.5
}
```

---

### 4.3 Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | string | Filter by cluster name (partial match) |
| `cluster_type` | enum | Filter by type (HUB, SPOKE, EDGE, FAR_EDGE) |
| `environment` | enum | Filter by environment |
| `region` | string | Filter by region |
| `state` | enum | Filter by status state |
| `has_gpu` | boolean | Filter clusters with GPU nodes |
| `has_cnf` | boolean | Filter clusters with CNF workloads |
| `label` | string | Filter by label (key=value format) |
| `page` | integer | Page number (default: 1) |
| `page_size` | integer | Items per page (default: 20, max: 100) |

---

## 5. Internal Service Interfaces

### 5.1 ClusterService

```python
class ClusterService:
    async def create(self, request: ClusterCreateRequest) -> Cluster:
        """Register a new cluster."""

    async def get(self, cluster_id: UUID) -> Cluster:
        """Get cluster by ID."""

    async def get_by_name(self, name: str) -> Cluster:
        """Get cluster by name."""

    async def list(self, filters: ClusterFilters, pagination: Pagination) -> PaginatedResponse[Cluster]:
        """List clusters with filtering."""

    async def update(self, cluster_id: UUID, request: ClusterUpdateRequest) -> Cluster:
        """Update cluster metadata."""

    async def delete(self, cluster_id: UUID) -> None:
        """Delete cluster and associated data."""

    async def refresh(self, cluster_id: UUID) -> Cluster:
        """Force refresh cluster status and capabilities."""
```

### 5.2 CredentialService

```python
class CredentialService:
    async def store(self, cluster_id: UUID, credentials: CredentialInput) -> CredentialStatus:
        """Store credentials securely in K8s Secrets."""

    async def validate(self, cluster_id: UUID) -> ValidationResult:
        """Validate stored credentials are working."""

    async def rotate(self, cluster_id: UUID, new_credentials: CredentialInput) -> CredentialStatus:
        """Rotate credentials with zero-downtime."""

    async def get_for_use(self, cluster_id: UUID) -> ResolvedCredentials:
        """Get decrypted credentials for internal use only."""

    async def delete(self, cluster_id: UUID) -> None:
        """Delete stored credentials."""
```

### 5.3 DiscoveryService

```python
class DiscoveryService:
    async def discover_capabilities(self, cluster_id: UUID) -> ClusterCapabilities:
        """Discover all cluster capabilities."""

    async def detect_gpu_nodes(self, cluster_id: UUID) -> GPUDiscoveryResult:
        """Detect GPU nodes and types."""

    async def detect_cnf_workloads(self, cluster_id: UUID) -> CNFDiscoveryResult:
        """Detect CNF workloads (vDU, vCU, etc.)."""

    async def detect_observability_stack(self, cluster_id: UUID) -> ObservabilityDiscoveryResult:
        """Detect Prometheus, Tempo, Loki availability."""
```

### 5.4 HealthService

```python
class HealthService:
    async def check_health(self, cluster_id: UUID) -> ClusterStatus:
        """Run health check on specific cluster."""

    async def run_all_checks(self) -> Dict[UUID, ClusterStatus]:
        """Run health checks on all clusters (background task)."""

    async def get_status(self, cluster_id: UUID) -> ClusterStatus:
        """Get cached status (no new check)."""
```

### 5.5 EventService

```python
class EventService:
    async def publish(self, event: Event) -> None:
        """Publish event to Redis."""

    async def subscribe(self, event_types: List[str]) -> AsyncIterator[Event]:
        """Subscribe to events (internal use)."""
```

---

## 6. Events Emitted

| Event Type | Trigger | Payload |
|------------|---------|---------|
| `CLUSTER_REGISTERED` | New cluster created | `Cluster` |
| `CLUSTER_UPDATED` | Cluster metadata updated | `Cluster` |
| `CLUSTER_DELETED` | Cluster removed | `{"cluster_id": UUID}` |
| `CLUSTER_STATUS_CHANGED` | Status state changed | `{"cluster_id": UUID, "old_state": str, "new_state": str}` |
| `CLUSTER_CREDENTIALS_UPDATED` | Credentials rotated | `{"cluster_id": UUID}` |
| `CLUSTER_CAPABILITIES_CHANGED` | Capabilities changed | `{"cluster_id": UUID, "capabilities": ClusterCapabilities}` |

---

## 7. Database Schema

### 7.1 PostgreSQL Tables

```sql
-- Clusters table
CREATE TABLE clusters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(63) UNIQUE NOT NULL,
    display_name VARCHAR(128),
    api_server_url VARCHAR(512) NOT NULL,
    cluster_type VARCHAR(20) NOT NULL DEFAULT 'SPOKE',
    platform VARCHAR(20) NOT NULL DEFAULT 'OPENSHIFT',
    platform_version VARCHAR(20),
    region VARCHAR(64),
    environment VARCHAR(20) DEFAULT 'DEVELOPMENT',
    labels JSONB DEFAULT '{}',
    endpoints JSONB DEFAULT '{}',
    capabilities JSONB,
    status JSONB NOT NULL DEFAULT '{"state": "UNKNOWN"}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ,

    CONSTRAINT valid_name CHECK (name ~ '^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$'),
    CONSTRAINT valid_cluster_type CHECK (cluster_type IN ('HUB', 'SPOKE', 'EDGE', 'FAR_EDGE')),
    CONSTRAINT valid_platform CHECK (platform IN ('OPENSHIFT', 'KUBERNETES', 'MICROSHIFT')),
    CONSTRAINT valid_environment CHECK (environment IN ('PRODUCTION', 'STAGING', 'DEVELOPMENT', 'LAB'))
);

-- Indexes for common queries
CREATE INDEX idx_clusters_name ON clusters(name);
CREATE INDEX idx_clusters_cluster_type ON clusters(cluster_type);
CREATE INDEX idx_clusters_environment ON clusters(environment);
CREATE INDEX idx_clusters_region ON clusters(region);
CREATE INDEX idx_clusters_status_state ON clusters((status->>'state'));
CREATE INDEX idx_clusters_labels ON clusters USING GIN(labels);
CREATE INDEX idx_clusters_capabilities_gpu ON clusters((capabilities->>'has_gpu_nodes'));

-- Health check history (optional, for trend analysis)
CREATE TABLE cluster_health_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_id UUID REFERENCES clusters(id) ON DELETE CASCADE,
    status JSONB NOT NULL,
    checked_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_health_history_cluster_time ON cluster_health_history(cluster_id, checked_at DESC);

-- Automatic cleanup of old health history
CREATE OR REPLACE FUNCTION cleanup_health_history() RETURNS TRIGGER AS $$
BEGIN
    DELETE FROM cluster_health_history
    WHERE checked_at < NOW() - INTERVAL '7 days';
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_cleanup_health_history
    AFTER INSERT ON cluster_health_history
    EXECUTE FUNCTION cleanup_health_history();
```

### 7.2 Kubernetes Secrets Structure

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: cluster-creds-{cluster-id}
  namespace: aiops-nextgen
  labels:
    app.kubernetes.io/component: cluster-registry
    aiops.io/cluster-id: "{cluster-id}"
type: Opaque
data:
  kubeconfig: <base64-encoded-kubeconfig>
  prometheus-token: <base64-encoded-token>
  tempo-token: <base64-encoded-token>
  loki-token: <base64-encoded-token>
```

---

## 8. Health Check Logic

### 8.1 Check Sequence

```
1. API Server Check
   └── Attempt: kubectl get namespaces (with timeout)
   └── Success: connectivity = CONNECTED
   └── Failure: connectivity = DISCONNECTED

2. Prometheus Check (if prometheus_url configured)
   └── Attempt: GET /-/ready
   └── Success: prometheus_healthy = true

3. Tempo Check (if tempo_url configured)
   └── Attempt: GET /ready
   └── Success: tempo_healthy = true

4. Loki Check (if loki_url configured)
   └── Attempt: GET /ready
   └── Success: loki_healthy = true

5. Calculate Health Score
   └── Base: 100
   └── -50 if API server down
   └── -20 if Prometheus down
   └── -15 if Tempo down
   └── -15 if Loki down
   └── Min: 0
```

### 8.2 State Transitions

```
UNKNOWN ──────► ONLINE (first successful check)
        │
        └─────► OFFLINE (first failed check)

ONLINE ───────► DEGRADED (partial failures)
        │
        └─────► OFFLINE (API server unreachable)

DEGRADED ─────► ONLINE (all checks pass)
        │
        └─────► OFFLINE (API server unreachable)

OFFLINE ──────► ONLINE (all checks pass)
        │
        └─────► DEGRADED (API up, some services down)
```

### 8.3 Check Intervals

| Cluster Type | Interval | Timeout |
|--------------|----------|---------|
| HUB | 15 seconds | 5 seconds |
| SPOKE | 30 seconds | 10 seconds |
| EDGE | 60 seconds | 15 seconds |
| FAR_EDGE | 120 seconds | 30 seconds |

---

## 9. Capability Discovery

### 9.1 GPU Detection

```python
async def detect_gpu_nodes(cluster_id: UUID) -> GPUDiscoveryResult:
    """
    Detection methods (in order):
    1. Check for nvidia.com/gpu resource on nodes
    2. Check for NVIDIA GPU Operator pods
    3. Query DCGM exporter metrics if available
    """
```

### 9.2 CNF Detection

```python
async def detect_cnf_workloads(cluster_id: UUID) -> CNFDiscoveryResult:
    """
    Detection methods:
    1. Check for known CNF namespaces (du-*, cu-*, upf-*, etc.)
    2. Check for SRIOV network node policies
    3. Check for PTP operator
    4. Query CNF-specific metrics if available
    """
```

### 9.3 Observability Detection

```python
async def detect_observability_stack(cluster_id: UUID) -> ObservabilityDiscoveryResult:
    """
    Detection methods:
    1. Prometheus: Check openshift-monitoring namespace
    2. Thanos: Check for thanos-querier service
    3. Tempo: Check for tempo-* pods in observability namespace
    4. Loki: Check for loki-* pods in openshift-logging
    """
```

---

## 10. Dependencies

### 10.1 Internal Dependencies

| Dependency | Purpose |
|------------|---------|
| PostgreSQL | Cluster metadata storage |
| Redis | Event publishing, status caching |
| Kubernetes API | Secret management |

### 10.2 External Dependencies

| Dependency | Purpose |
|------------|---------|
| Spoke Cluster APIs | Health checks, discovery |
| Spoke Prometheus | Metrics availability check |
| Spoke Tempo | Traces availability check |
| Spoke Loki | Logs availability check |

---

## 11. Configuration

```yaml
cluster_registry:
  # Database
  database_url: "postgresql://user:pass@postgres:5432/aiops"

  # Redis
  redis_url: "redis://redis:6379/0"

  # Health checks
  health_check:
    enabled: true
    hub_interval_seconds: 15
    spoke_interval_seconds: 30
    edge_interval_seconds: 60
    far_edge_interval_seconds: 120
    timeout_seconds: 10

  # Capability discovery
  discovery:
    on_registration: true
    periodic_refresh_hours: 24

  # Credentials
  credentials:
    secret_namespace: "aiops-nextgen"
    rotation_warning_days: 7
```

---

## 12. Error Handling

| Error Code | HTTP Status | Description |
|------------|-------------|-------------|
| `CLUSTER_NOT_FOUND` | 404 | Cluster with given ID/name not found |
| `CLUSTER_ALREADY_EXISTS` | 409 | Cluster with name already exists |
| `INVALID_CLUSTER_NAME` | 400 | Name doesn't match DNS pattern |
| `CREDENTIALS_INVALID` | 400 | Provided credentials failed validation |
| `CREDENTIALS_NOT_FOUND` | 404 | No credentials stored for cluster |
| `CLUSTER_UNREACHABLE` | 503 | Cannot connect to cluster API |
| `DISCOVERY_FAILED` | 500 | Capability discovery failed |

---

## 13. Security Considerations

1. **Credential Storage**: Kubeconfigs stored in K8s Secrets with RBAC restrictions
2. **Credential Exposure**: Never return credentials in API responses
3. **Token Rotation**: Support automated token rotation before expiry
4. **Network Isolation**: Use NetworkPolicies to restrict egress to known clusters
5. **Audit Logging**: Log all credential access and cluster modifications

---

## 14. Open Questions

1. **Credential Encryption**: Use K8s Secrets encryption at rest or add application-level encryption?
2. **Multi-region Hub**: Support for geo-distributed hub clusters?
3. **Import from ACM**: Auto-import clusters from Advanced Cluster Management?
4. **Credential Delegation**: Allow per-team credentials with scoped permissions?

---

## Next: [03-observability-collector.md](./03-observability-collector.md)
