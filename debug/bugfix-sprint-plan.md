# Sprint Development Plan

This document organizes the identified issues (listed in debug/issues.md) into logical development sprints. Issues are grouped by coupling and dependencies to enable incremental delivery.

---

## Sprint Overview

| Sprint | Theme | Issues | Priority | Status |
|--------|-------|--------|----------|--------|
| Sprint 1 | Security Foundation | 4 | P0 - Blocker | ✅ COMPLETED |
| Sprint 2 | Kubernetes Integration | 3 | P0 - Blocker | ✅ COMPLETED |
| Sprint 3 | Prometheus & Metrics Auth | 2 | P1 - Critical | ✅ COMPLETED |
| Sprint 4 | Logs & Traces Collectors | 2 | P1 - Critical | ✅ COMPLETED |
| Sprint 5 | GPU Telemetry | 1 | P1 - Critical | ✅ COMPLETED |
| Sprint 6 | CNF/Telco Monitoring | 2 | P1 - Critical | ✅ COMPLETED |
| Sprint 7 | WebSocket Hardening | 3 | P2 - High | ✅ COMPLETED |
| Sprint 8 | Intelligence - Anomaly & RCA | 2 | P2 - High | 🔲 PENDING |
| Sprint 9 | Intelligence - Reports & Tools | 2 | P2 - High | 🔲 PENDING |
| Sprint 10 | API Gateway Polish | 3 | P3 - Medium | 🔲 PENDING |

---

## Progress Summary

**Last Updated:** 2025-12-29

### Track A: Security & Infrastructure - COMPLETED
- Sprint 1 (Security Foundation): ✅ Completed
- Sprint 2 (Kubernetes Integration): ✅ Completed
- Sprint 3 (Prometheus Auth): ✅ Completed

### Track B: Observability - COMPLETED
- Sprint 4 (Logs & Traces): ✅ Completed
- Sprint 5 (GPU Telemetry): ✅ Completed
- Sprint 6 (CNF Monitoring): ✅ Completed

### Track C: WebSocket & Intelligence - IN PROGRESS
- Sprint 7 (WebSocket Hardening): ✅ Completed
- Sprint 8 (Anomaly & RCA): 🔲 Pending
- Sprint 9 (Reports & MCP Tools): 🔲 Pending

### Deployment Status
- **Sandbox Cluster:** sandbox01.narlabs.io
- **Services Deployed:** cluster-registry, observability-collector
- **All API endpoints tested and functional**

---

## Sprint 1: Security Foundation

**Theme:** Authentication & Authorization - Cannot proceed without security
**Priority:** P0 - Blocker
**Dependencies:** None (foundational)

### Issues

| Issue | Title | Severity |
|-------|-------|----------|
| ISSUE-010 | Missing OpenShift OAuth Authentication | CRITICAL |
| ISSUE-011 | Missing RBAC Authorization | CRITICAL |
| ISSUE-015 | WebSocket Authentication is Bypassed | HIGH |

### Deliverables

1. **OAuth Middleware** (`src/api-gateway/app/middleware/auth.py`)
   - JWT token validation against OpenShift OAuth server
   - Token review API integration
   - Service account token support
   - Token caching (60s TTL per spec)

2. **RBAC Middleware** (`src/api-gateway/app/middleware/rbac.py`)
   - Role definitions (admin, operator, viewer)
   - Permission checking per endpoint
   - Cluster-scoped access filtering via SubjectAccessReview

3. **WebSocket Auth Validator** (`src/realtime-streaming/app/services/auth.py`)
   - Validate tokens via API Gateway's `/auth/validate` endpoint
   - Reject unauthenticated connections
   - Extract user context for subscription filtering

### Acceptance Criteria

- [ ] Unauthenticated requests return 401
- [ ] Invalid tokens return 401
- [ ] Users can only access clusters they have permissions for
- [ ] WebSocket connections require valid tokens
- [ ] Service-to-service calls use service account tokens

---

## Sprint 2: Kubernetes Integration

**Theme:** Real Kubernetes API Integration - Foundation for all cluster operations
**Priority:** P0 - Blocker
**Dependencies:** Sprint 1 (need credentials secured)

### Issues

| Issue | Title | Severity |
|-------|-------|----------|
| ISSUE-002 | Credential Service Stores Secrets in Memory | CRITICAL |
| ISSUE-003 | Credential Validation is Completely Mocked | CRITICAL |
| ISSUE-004 | Missing DiscoveryService | CRITICAL |

### Deliverables

1. **Kubernetes Secrets Integration** (`src/cluster-registry/app/services/credential_service.py`)
   - Create/update/delete Kubernetes Secrets
   - AES-256-GCM encryption for sensitive values
   - Secret naming convention: `aiops-cluster-{cluster-id}`
   - Reference secrets by name, never store decrypted

2. **Credential Validator** (`src/cluster-registry/app/services/credential_validator.py`)
   - Test K8s API server connectivity with provided kubeconfig/token
   - Test Prometheus endpoint reachability
   - Test Tempo endpoint reachability
   - Test Loki endpoint reachability
   - Return detailed validation results per endpoint

3. **Discovery Service** (`src/cluster-registry/app/services/discovery_service.py`)
   - Query K8s API for cluster version
   - Detect GPU nodes via node labels (`nvidia.com/gpu`)
   - Detect SR-IOV capability via node resources
   - Detect PTP via `ptp` namespace/operator
   - Detect installed operators (ODF, NFD, GPU Operator)
   - Probe node types (worker, master, edge)

### Acceptance Criteria

- [ ] Credentials stored in Kubernetes Secrets, not memory
- [ ] Credentials encrypted at rest
- [ ] Credential validation actually tests endpoints
- [ ] Discovery detects GPU nodes correctly
- [ ] Discovery detects SR-IOV/PTP capabilities
- [ ] Cluster capabilities populated from real discovery

---

## Sprint 3: Prometheus & Metrics Authentication

**Theme:** Secure metrics collection from managed clusters
**Priority:** P1 - Critical
**Dependencies:** Sprint 2 (need credential storage)

### Issues

| Issue | Title | Severity |
|-------|-------|----------|
| ISSUE-012 | Prometheus Collector Missing Authentication Header Implementation | HIGH |

### Deliverables

1. **Prometheus Auth Integration** (`src/observability-collector/app/collectors/prometheus_collector.py`)
   - Retrieve cluster credentials from Cluster Registry
   - Add Bearer token to Prometheus requests
   - Support both direct Prometheus and Thanos Query
   - Handle token refresh on 401 responses

2. **Credential Client** (`src/observability-collector/app/clients/credential_client.py`)
   - Fetch decrypted credentials from Cluster Registry internal API
   - Cache credentials with short TTL
   - Handle credential rotation gracefully

### Acceptance Criteria

- [ ] Prometheus queries include auth headers
- [ ] Secured Prometheus endpoints work correctly
- [ ] Token refresh happens automatically
- [ ] Credential caching reduces API calls

---

## Sprint 4: Logs & Traces Collectors

**Theme:** Complete observability stack with Loki and Tempo
**Priority:** P1 - Critical
**Dependencies:** Sprint 3 (auth pattern established)

### Issues

| Issue | Title | Severity |
|-------|-------|----------|
| ISSUE-005 | Missing Loki/Logs Collector | HIGH |
| ISSUE-006 | Missing Tempo/Traces Collector | HIGH |

### Deliverables

1. **Loki Collector** (`src/observability-collector/app/collectors/loki_collector.py`)
   - LogQL query execution
   - Label-based filtering
   - Time range queries
   - Federated queries across clusters
   - Stream-based log tailing

2. **Loki API Endpoints** (`src/observability-collector/app/api/logs.py`)
   - `POST /api/v1/logs/query` - LogQL query
   - `GET /api/v1/logs/labels` - Get available labels
   - `GET /api/v1/logs/label/{name}/values` - Get label values

3. **Tempo Collector** (`src/observability-collector/app/collectors/tempo_collector.py`)
   - Trace search by service, operation, duration
   - Trace detail retrieval by trace ID
   - Service dependency graph generation

4. **Traces API Endpoints** (`src/observability-collector/app/api/traces.py`)
   - `POST /api/v1/traces/search` - Search traces
   - `GET /api/v1/traces/{trace_id}` - Get trace detail
   - `GET /api/v1/traces/services` - List services
   - `GET /api/v1/traces/dependencies` - Service dependency graph

### Acceptance Criteria

- [x] LogQL queries execute across clusters
- [x] Log labels discoverable
- [x] Trace search returns matching traces
- [x] Trace detail shows full span tree
- [x] Service dependency graph generated

---

## Sprint 5: GPU Telemetry

**Theme:** Real GPU monitoring via nvidia-smi
**Priority:** P1 - Critical
**Dependencies:** Sprint 2 (K8s API access), Sprint 3 (auth)

### Issues

| Issue | Title | Severity |
|-------|-------|----------|
| ISSUE-001 | GPU Collector Uses Fake Mock Data | CRITICAL |

### Deliverables

1. **Real GPU Collector** (`src/observability-collector/app/collectors/gpu_collector.py`)
   - Find nvidia-driver-daemonset pods on target cluster
   - Execute `nvidia-smi` via `kubectl exec`
   - Parse CSV output for GPU metrics
   - Collect per-GPU: utilization, memory, temp, power, fan
   - Collect GPU processes

2. **GPU Node Discovery**
   - Query nodes with `nvidia.com/gpu` label
   - Map pods to nodes for targeted collection

3. **GPU Process Tracking**
   - Execute nvidia-smi process query
   - Map PIDs to container/pod names

### Acceptance Criteria

- [x] Real GPU metrics from nvidia-smi
- [x] All specified metrics collected (utilization, memory, temp, power, fan)
- [x] GPU processes tracked with pod correlation
- [x] Works across multiple GPU nodes
- [x] Handles clusters without GPUs gracefully

---

## Sprint 6: CNF/Telco Monitoring

**Theme:** Cloud-Native Network Function monitoring
**Priority:** P1 - Critical
**Dependencies:** Sprint 2 (K8s API), Sprint 3 (auth)

### Issues

| Issue | Title | Severity |
|-------|-------|----------|
| ISSUE-013 | Missing CNF/Network Tools and Collectors | HIGH |
| (Part of ISSUE-014) | Missing CNF-related MCP tools | HIGH |

### Deliverables

1. **PTP Collector** (`src/observability-collector/app/collectors/ptp_collector.py`)
   - Query PTP operator status
   - Get clock sync accuracy
   - Monitor PTP4L/PHC2SYS status

2. **SR-IOV Collector** (`src/observability-collector/app/collectors/sriov_collector.py`)
   - Get SR-IOV VF allocation status
   - Monitor VF usage per node
   - Track VF assignment to pods

3. **DPDK Stats Collector** (`src/observability-collector/app/collectors/dpdk_collector.py`)
   - Execute `dpdk-proc-info` in CNF pods
   - Collect packet processing stats
   - Monitor NIC queue stats

4. **CNF API Endpoints** (`src/observability-collector/app/api/cnf.py`)
   - `GET /api/v1/cnf/workloads` - List CNF workloads
   - `GET /api/v1/cnf/ptp/status` - PTP status
   - `GET /api/v1/cnf/sriov/status` - SR-IOV status
   - `GET /api/v1/cnf/{pod}/dpdk` - DPDK stats

### Acceptance Criteria

- [x] PTP sync status visible
- [x] SR-IOV VF allocation tracked
- [x] DPDK packet stats collected
- [x] CNF workloads discoverable by type (vDU, vCU, UPF)

---

## Sprint 7: WebSocket Hardening

**Theme:** Production-ready WebSocket infrastructure
**Priority:** P2 - High
**Dependencies:** Sprint 1 (auth)

### Issues

| Issue | Title | Severity |
|-------|-------|----------|
| ISSUE-016 | Missing Heartbeat Manager | MEDIUM |
| ISSUE-017 | Missing Backpressure Handler | MEDIUM |
| ISSUE-020 | Missing WebSocket Proxy in API Gateway | MEDIUM |

### Deliverables

1. **Heartbeat Manager** (`src/realtime-streaming/app/services/heartbeat.py`)
   - 30-second ping interval per client
   - 10-second pong timeout
   - Automatic disconnect on timeout
   - Track connection health metrics

2. **Backpressure Handler** (`src/realtime-streaming/app/services/backpressure.py`)
   - Per-client message queue (max 100)
   - Drop oldest on overflow
   - Slow client detection (>1s delivery time)
   - Metrics for dropped messages

3. **WebSocket Proxy** (`src/api-gateway/app/api/websocket_proxy.py`)
   - WebSocket upgrade handling
   - Token extraction and validation
   - Proxy to realtime-streaming service
   - Connection lifecycle management

### Acceptance Criteria

- [ ] Dead connections detected within 40s
- [ ] Slow clients don't block event delivery
- [ ] Message drop metrics available
- [ ] WebSocket works through API Gateway

---

## Sprint 8: Intelligence - Anomaly & RCA

**Theme:** AI-powered anomaly detection and root cause analysis
**Priority:** P2 - High
**Dependencies:** Sprint 4 (logs/traces), Sprint 5 (GPU)

### Issues

| Issue | Title | Severity |
|-------|-------|----------|
| ISSUE-007 | Missing Anomaly Detection Service | HIGH |
| ISSUE-008 | Missing RCA Service | HIGH |

### Deliverables

1. **Anomaly Detection Service** (`src/intelligence-engine/app/services/anomaly.py`)
   - Statistical detection (Z-score, IQR)
   - Sensitivity levels (LOW/MEDIUM/HIGH/EXTREME)
   - Integration with metrics service
   - Anomaly event publishing

2. **Anomaly API** (`src/intelligence-engine/app/api/analysis.py`)
   - `POST /api/v1/analysis/anomaly` - Detect anomalies
   - `GET /api/v1/analysis/anomaly/{id}` - Get anomaly detail

3. **RCA Service** (`src/intelligence-engine/app/services/rca.py`)
   - Signal collection (metrics, traces, logs, alerts)
   - Temporal correlation
   - Causal graph building
   - LLM-powered explanation generation

4. **RCA API**
   - `POST /api/v1/analysis/rca` - Trigger RCA
   - `GET /api/v1/analysis/rca/{id}` - Get RCA result

### Acceptance Criteria

- [ ] Anomalies detected in metric data
- [ ] Sensitivity levels affect detection threshold
- [ ] RCA correlates signals within time window
- [ ] LLM generates human-readable explanations
- [ ] Events published for detected anomalies

---

## Sprint 9: Intelligence - Reports & MCP Tools

**Theme:** Complete Intelligence Engine capabilities
**Priority:** P2 - High
**Dependencies:** Sprint 8 (anomaly/RCA for report data)

### Issues

| Issue | Title | Severity |
|-------|-------|----------|
| ISSUE-009 | Missing Report Generation Service | HIGH |
| ISSUE-014 | Missing MCP Tools (9+ tools) | HIGH |

### Deliverables

1. **Report Service** (`src/intelligence-engine/app/services/reports.py`)
   - Report generation (HTML, PDF, Markdown)
   - AI-powered summaries via LLM
   - Object storage integration (MinIO/ODF)
   - Report scheduling (optional)

2. **Report API** (`src/intelligence-engine/app/api/reports.py`)
   - `POST /api/v1/reports` - Generate report
   - `GET /api/v1/reports` - List reports
   - `GET /api/v1/reports/{id}` - Get report metadata
   - `GET /api/v1/reports/{id}/download` - Download file
   - `DELETE /api/v1/reports/{id}` - Delete report

3. **Complete MCP Tool Set** (`src/intelligence-engine/app/tools/`)
   - `get_cluster_status` - Detailed cluster status
   - `get_metric_labels` - Prometheus label discovery
   - `search_traces` - Tempo trace search
   - `get_trace` - Trace detail
   - `query_logs` - Loki LogQL
   - `get_gpu_processes` - GPU process list
   - `get_cnf_workloads` - CNF workload list
   - `get_ptp_status` - PTP sync status
   - `get_dpdk_stats` - DPDK statistics
   - `get_sriov_status` - SR-IOV allocation

### Acceptance Criteria

- [ ] Reports generated in all 3 formats
- [ ] Reports stored in object storage
- [ ] All 15+ MCP tools implemented
- [ ] LLM can call all tools successfully
- [ ] Persona capabilities filter available tools

---

## Sprint 10: API Gateway Polish

**Theme:** Production hardening and observability
**Priority:** P3 - Medium
**Dependencies:** All previous sprints

### Issues

| Issue | Title | Severity |
|-------|-------|----------|
| ISSUE-018 | Chat Sessions Not Persisted to PostgreSQL | MEDIUM |
| ISSUE-019 | Health Check Aggregation Not Implemented | MEDIUM |
| ISSUE-021 | Missing Request Validation Middleware | LOW |
| ISSUE-022 | Missing Distributed Tracing Integration | LOW |

### Deliverables

1. **Chat Persistence** (`src/intelligence-engine/app/services/chat.py`)
   - PostgreSQL schema for chat sessions/messages
   - Async SQLAlchemy integration
   - Redis as cache layer, PostgreSQL as source of truth

2. **Aggregated Health Check** (`src/api-gateway/app/api/health.py`)
   - `/health/detailed` endpoint
   - Probe all backend services
   - Include Redis, PostgreSQL health
   - Return component-level status with latency

3. **Request Validation Middleware** (`src/api-gateway/app/middleware/validation.py`)
   - JSON schema validation per endpoint
   - Query parameter validation
   - Return 422 with detailed errors

4. **Distributed Tracing** (`src/api-gateway/app/middleware/tracing.py`)
   - Extract trace context from incoming requests
   - Create gateway span
   - Propagate context to backend services
   - Export to OpenTelemetry collector

### Acceptance Criteria

- [ ] Chat sessions persist across restarts
- [ ] `/health/detailed` shows all component status
- [ ] Invalid requests rejected with 422
- [ ] Traces visible in Tempo from gateway through backends

---

## Dependency Graph

```
Sprint 1 (Security)
    │
    ├──► Sprint 2 (K8s Integration)
    │        │
    │        ├──► Sprint 3 (Prometheus Auth)
    │        │        │
    │        │        ├──► Sprint 4 (Logs/Traces)
    │        │        │        │
    │        │        │        └──► Sprint 8 (Anomaly/RCA)
    │        │        │                  │
    │        │        │                  └──► Sprint 9 (Reports/Tools)
    │        │        │
    │        │        └──► Sprint 5 (GPU)
    │        │
    │        └──► Sprint 6 (CNF)
    │
    └──► Sprint 7 (WebSocket)

Sprint 10 (Polish) ──► After all other sprints
```

---

## Estimated Effort

| Sprint | Story Points | Complexity |
|--------|--------------|------------|
| Sprint 1 | 13 | High |
| Sprint 2 | 21 | Very High |
| Sprint 3 | 8 | Medium |
| Sprint 4 | 13 | High |
| Sprint 5 | 13 | High |
| Sprint 6 | 13 | High |
| Sprint 7 | 8 | Medium |
| Sprint 8 | 21 | Very High |
| Sprint 9 | 13 | High |
| Sprint 10 | 8 | Medium |
| **Total** | **131** | - |

---

## Recommended Team Allocation

### Track A: Security & Infrastructure (Sprints 1, 2, 3)
- Senior backend developer with K8s experience
- Security specialist (or security review)

### Track B: Observability (Sprints 4, 5, 6)
- Backend developer with Prometheus/Loki/Tempo experience
- Can start after Sprint 2 completes

### Track C: Intelligence (Sprints 8, 9)
- ML/AI engineer or senior backend developer
- LLM integration experience helpful

### Track D: WebSocket & Polish (Sprints 7, 10)
- Full-stack developer
- Can run in parallel with Track C

---

## Release Milestones

| Milestone | Sprints | Key Capability |
|-----------|---------|----------------|
| **M1: Secure Foundation** | 1, 2 | Authenticated, K8s-integrated |
| **M2: Metrics Complete** | 3, 5, 6 | Full metrics collection |
| **M3: Full Observability** | 4 | Logs + Traces + Metrics |
| **M4: AI-Powered** | 8, 9 | Anomaly, RCA, Reports |
| **M5: Production Ready** | 7, 10 | Hardened, observable |
