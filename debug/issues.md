# Code Audit Issues

This document lists deviations, fake implementations, and missing features identified during the code audit against the specifications in `specs/` and `src/development-plan.md`.

---

## CRITICAL ISSUES

### ISSUE-001: GPU Collector Uses Fake Mock Data Instead of Real nvidia-smi Integration

**Severity:** CRITICAL
**File:** `src/observability-collector/app/collectors/gpu_collector.py`
**Spec Reference:** `specs/03-observability-collector.md` Section 6.2

**Description:**
The GPU collector is entirely fake. Instead of executing `nvidia-smi` via `kubectl exec` on nvidia-driver-daemonset pods as specified, it generates hardcoded mock data with comments like "For sandbox testing, returns mock data".

**Evidence:**
```python
# Lines 40-60
async def list_gpu_nodes(self, cluster: dict) -> list[dict[str, Any]]:
    """...
    For sandbox testing, returns mock data if cluster has GPU capability.
    """
    # Mock GPU node data for testing
    # In production, this would query the K8s API
    return [...]
```

The spec clearly requires:
- Execute `nvidia-smi` via kubectl exec into nvidia-driver-daemonset pods
- Parse CSV output from nvidia-smi
- Return real GPU metrics (utilization, memory, temperature, power, fan speed)

**Impact:** No real GPU telemetry is collected. The entire GPU monitoring feature is non-functional.

---

### ISSUE-002: Credential Service Stores Secrets in Memory - No Kubernetes Secrets Integration

**Severity:** CRITICAL
**File:** `src/cluster-registry/app/services/credential_service.py`
**Spec Reference:** `specs/02-cluster-registry.md` Section 5.2, 7.2

**Description:**
Credentials are stored in a Python dictionary (`_credential_store`) instead of Kubernetes Secrets. There is no encryption, no Kubernetes API integration, and credentials would be lost on service restart.

**Evidence:**
```python
# Line 32-33
# In-memory credential store for local development
_credential_store: dict[str, dict[str, Any]] = {}
```

The spec requires:
- Store credentials in Kubernetes Secrets
- AES-256-GCM encryption for tokens
- Reference secrets by name, never store decrypted values
- Credential rotation with zero-downtime

**Impact:** Credentials are insecure, non-persistent, and would be lost on restart. Production deployment would fail.

---

### ISSUE-003: Credential Validation is Completely Mocked

**Severity:** CRITICAL
**File:** `src/cluster-registry/app/services/credential_service.py`
**Spec Reference:** `specs/02-cluster-registry.md` Section 5.2

**Description:**
The `_validate_credentials` method always returns success without actually testing connectivity to any endpoints.

**Evidence:**
```python
# Lines 152-182
async def _validate_credentials(self, ...):
    """...
    In local development, this is mocked.
    """
    # Mock validation - always succeeds in local dev
    api_validation = EndpointValidation(status=ValidationStatus.SUCCESS)
```

The spec requires actually testing connectivity to:
- Kubernetes API server
- Prometheus endpoint
- Tempo endpoint
- Loki endpoint

**Impact:** Invalid credentials would be accepted without detection.

---

### ISSUE-004: Missing DiscoveryService - No Real Kubernetes API Integration

**Severity:** CRITICAL
**File:** Missing entirely from `src/cluster-registry/app/services/`
**Spec Reference:** `specs/02-cluster-registry.md` Section 6

**Description:**
The spec defines a `DiscoveryService` responsible for:
- Discovering cluster capabilities (GPU, SR-IOV, PTP, ODF)
- Getting version info from clusters
- Detecting node types (GPU nodes, edge nodes)
- Probing for installed operators

This service does not exist. The capability discovery in `ClusterService` is faked:

```python
# cluster_service.py - hardcoded capabilities
capabilities = ClusterCapabilities(
    has_gpu_nodes=False,
    gpu_count=0,
    gpu_types=[],
    # ... all hardcoded to defaults
)
```

**Impact:** No actual discovery of cluster capabilities. All capability data is fake.

---

### ISSUE-005: Missing Loki/Logs Collector

**Severity:** HIGH
**Files:** No log-related collectors in `src/observability-collector/app/collectors/`
**Spec Reference:** `specs/03-observability-collector.md` Section 6.4

**Description:**
The spec defines log querying via Loki with LogQL support, but there is no Loki collector implementation. The API endpoints for logs exist in the route mapping but have no backend implementation.

**Impact:** Log querying functionality is non-existent.

---

### ISSUE-006: Missing Tempo/Traces Collector

**Severity:** HIGH
**Files:** No trace-related collectors in `src/observability-collector/app/collectors/`
**Spec Reference:** `specs/03-observability-collector.md` Section 6.5

**Description:**
The spec defines trace querying via Tempo, but there is no Tempo collector implementation. Trace search, trace detail retrieval, and service map generation are all missing.

**Impact:** Distributed tracing functionality is non-existent.

---

### ISSUE-007: Missing Anomaly Detection Service

**Severity:** HIGH
**Files:** No anomaly-related files in `src/intelligence-engine/app/services/`
**Spec Reference:** `specs/04-intelligence-engine.md` Section 8

**Description:**
The spec defines a comprehensive anomaly detection system with:
- Statistical detection (Z-score, IQR)
- ML-based detection (Isolation Forest, LSTM Autoencoder, Prophet)
- LLM-assisted pattern detection
- Configurable sensitivity levels

None of this is implemented. The `/api/v1/analysis/anomaly` endpoint defined in the spec does not exist.

**Impact:** No automated anomaly detection capability.

---

### ISSUE-008: Missing RCA (Root Cause Analysis) Service

**Severity:** HIGH
**Files:** No RCA-related files in `src/intelligence-engine/app/services/`
**Spec Reference:** `specs/04-intelligence-engine.md` Section 9

**Description:**
The spec defines an RCA service for:
- Collecting related signals (metrics, traces, logs, alerts)
- Building correlation graphs
- Identifying probable causes
- Integration with Korrel8r

None of this is implemented.

**Impact:** No root cause analysis capability.

---

### ISSUE-009: Missing Report Generation Service

**Severity:** HIGH
**Files:** No report-related files in `src/intelligence-engine/app/services/`
**Spec Reference:** `specs/04-intelligence-engine.md` Section 4.5

**Description:**
The spec defines report generation with:
- Multiple formats (HTML, PDF, Markdown)
- AI-powered summaries
- Object storage for report files
- Report listing and download

None of this is implemented.

**Impact:** No report generation capability.

---

### ISSUE-010: Missing OpenShift OAuth Authentication

**Severity:** CRITICAL
**Files:** No auth middleware in `src/api-gateway/app/middleware/`
**Spec Reference:** `specs/06-api-gateway.md` Section 5

**Description:**
The spec requires OpenShift OAuth integration for authentication:
- JWT token validation against OpenShift OAuth server
- Token review API integration
- Service account authentication
- RBAC policy enforcement

The API Gateway has NO authentication middleware. All endpoints are unprotected.

**Evidence:** `src/api-gateway/app/main.py` only includes `RateLimitMiddleware`, no auth middleware.

**Impact:** Any user can access any endpoint without authentication. Complete security failure.

---

### ISSUE-011: Missing RBAC Authorization

**Severity:** CRITICAL
**Files:** No authorization implementation
**Spec Reference:** `specs/06-api-gateway.md` Section 6

**Description:**
The spec defines RBAC with:
- Roles (admin, operator, viewer)
- Cluster-scoped access control
- SubjectAccessReview integration

None of this is implemented.

**Impact:** No access control. All authenticated users have full access.

---

### ISSUE-012: Prometheus Collector Missing Authentication Header Implementation

**Severity:** HIGH
**File:** `src/observability-collector/app/collectors/prometheus_collector.py`
**Spec Reference:** `specs/03-observability-collector.md` Section 6.1

**Description:**
The `_get_auth_headers` method returns empty headers with a TODO comment.

**Evidence:**
```python
# Lines 252-256
def _get_auth_headers(self, cluster: dict) -> dict[str, str]:
    """Get authentication headers for cluster."""
    # In a real implementation, this would get the token from credentials
    # For now, return empty headers
    return {}
```

**Impact:** Cannot authenticate to secured Prometheus endpoints.

---

### ISSUE-013: Missing CNF/Network Tools and Collectors

**Severity:** HIGH
**Files:** No CNF collectors
**Spec Reference:** `specs/03-observability-collector.md`, `specs/04-intelligence-engine.md` Section 6.1

**Description:**
The spec defines CNF-specific functionality:
- PTP (Precision Time Protocol) status collection
- SR-IOV VF allocation monitoring
- DPDK statistics collection
- CNF workload discovery

None of these collectors are implemented. The MCP tools `get_cnf_workloads`, `get_ptp_status`, `get_dpdk_stats`, `get_sriov_status` defined in the spec are missing from `tool_definitions.py` and `executor.py`.

**Impact:** No CNF/telco-specific monitoring capability.

---

### ISSUE-014: Missing MCP Tools - Only 6 of 15+ Specified Tools Implemented

**Severity:** HIGH
**File:** `src/intelligence-engine/app/tools/definitions.py`
**Spec Reference:** `specs/04-intelligence-engine.md` Section 6.1

**Description:**
The spec defines 15+ MCP tools. Only 6 are implemented:
- `list_clusters` - implemented
- `query_metrics` - implemented
- `list_alerts` - implemented
- `get_gpu_nodes` - implemented
- `get_gpu_summary` - implemented
- `get_fleet_summary` - implemented

**Missing tools:**
- `get_cluster_status`
- `get_metric_labels`
- `search_traces`
- `get_trace`
- `query_logs`
- `get_gpu_processes`
- `get_cnf_workloads`
- `get_ptp_status`
- `get_dpdk_stats`
- `get_sriov_status`

**Impact:** LLM personas cannot access most observability data.

---

### ISSUE-015: WebSocket Authentication is Bypassed

**Severity:** HIGH
**File:** `src/realtime-streaming/app/api/websocket.py`
**Spec Reference:** `specs/05-realtime-streaming.md` Section 4.2

**Description:**
WebSocket authentication accepts any token without validation.

**Evidence:**
```python
# Lines 107-113
if msg_type == "auth":
    # For MVP, accept any auth (in production, validate token)
    await websocket.send_json({
        "type": "auth_response",
        "status": "authenticated",
        "client_id": client_id,
    })
```

**Impact:** Any client can connect and receive all events without authentication.

---

### ISSUE-016: Missing Heartbeat Manager for WebSocket Connections

**Severity:** MEDIUM
**Files:** No heartbeat implementation
**Spec Reference:** `specs/05-realtime-streaming.md` Section 8.1

**Description:**
The spec defines a heartbeat mechanism:
- 30-second ping interval
- 10-second timeout for pong response
- Automatic disconnect on timeout

This is not implemented. The WebSocket only responds to client-initiated pings but doesn't proactively send them.

**Impact:** Dead connections won't be detected and cleaned up.

---

### ISSUE-017: Missing Backpressure Handler for WebSocket

**Severity:** MEDIUM
**Files:** No backpressure implementation
**Spec Reference:** `specs/05-realtime-streaming.md` Section 8.3

**Description:**
The spec defines backpressure handling:
- Message queue per client (max 100)
- Drop oldest messages when full
- Slow client detection threshold

The `WebSocketHub` has a `MAX_QUEUE_SIZE` constant but no actual backpressure logic is implemented.

**Impact:** Slow clients could cause memory issues or block event delivery.

---

### ISSUE-018: Chat Sessions Not Persisted to PostgreSQL

**Severity:** MEDIUM
**File:** `src/intelligence-engine/app/services/chat.py`
**Spec Reference:** `specs/04-intelligence-engine.md` Section 3

**Description:**
Chat sessions are stored only in Redis with a 24-hour TTL. The spec architecture diagram shows PostgreSQL for session persistence.

**Evidence:**
```python
# Lines 107-108
# For now, scan Redis for user's sessions
# In production, this would query PostgreSQL
```

**Impact:** Chat history is lost after 24 hours. No long-term session storage.

---

### ISSUE-019: Health Check Aggregation Not Implemented

**Severity:** MEDIUM
**File:** `src/api-gateway/app/api/health.py`
**Spec Reference:** `specs/06-api-gateway.md` Section 12.2

**Description:**
The spec defines a `/health/detailed` endpoint that aggregates health from all backend services and dependencies. Only basic health check exists.

**Impact:** No visibility into overall system health.

---

### ISSUE-020: Missing WebSocket Proxy in API Gateway

**Severity:** MEDIUM
**File:** `src/api-gateway/app/api/proxy.py`
**Spec Reference:** `specs/06-api-gateway.md` Section 4.2

**Description:**
The API Gateway route mapping includes `/ws` to Real-Time Streaming, but the proxy only handles HTTP requests, not WebSocket upgrades.

**Impact:** WebSocket connections cannot go through the API Gateway.

---

### ISSUE-021: Missing Request Validation Middleware

**Severity:** LOW
**Files:** No validation middleware
**Spec Reference:** `specs/06-api-gateway.md` Section 8

**Description:**
The spec defines JSON schema validation for requests. No validation middleware is implemented in the API Gateway.

**Impact:** Invalid requests reach backend services without validation.

---

### ISSUE-022: Missing Distributed Tracing/OpenTelemetry Integration

**Severity:** LOW
**Files:** Incomplete implementation
**Spec Reference:** `specs/06-api-gateway.md` Section 11.2

**Description:**
The spec requires distributed tracing with trace context propagation. While `shared/observability.py` may have some setup, there's no evidence of trace context injection in the API Gateway proxy.

**Impact:** No end-to-end tracing capability.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 6 |
| HIGH | 10 |
| MEDIUM | 5 |
| LOW | 2 |
| **Total** | **23** |

### Most Impactful Issues

1. **No Authentication/Authorization** (ISSUE-010, ISSUE-011) - Complete security failure
2. **Fake GPU Collector** (ISSUE-001) - Key feature is non-functional
3. **In-Memory Credentials** (ISSUE-002, ISSUE-003) - Security and persistence failure
4. **Missing Core Services** (ISSUE-005 through ISSUE-009) - Logs, Traces, Anomaly, RCA, Reports all missing
5. **Missing Discovery Service** (ISSUE-004) - No real Kubernetes integration for capability discovery
