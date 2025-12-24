# 08 - Integration Matrix

## Document Info
| Field | Value |
|-------|-------|
| Version | 0.1.0 |
| Status | Draft |
| Last Updated | 2024-12-24 |

---

## 1. Purpose

This document defines all integration points between AIOps NextGen components, including:

- Service-to-service communication
- Event flows
- Shared dependencies
- API contracts
- Data consistency requirements

---

## 2. Component Dependency Matrix

```
                          ┌─────────┬─────────┬─────────┬─────────┬─────────┬─────────┐
                          │Cluster  │Observ.  │Intel.   │Realtime │API      │Frontend │
                          │Registry │Collector│Engine   │Streaming│Gateway  │         │
┌─────────────────────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┤
│ Cluster Registry        │    -    │    ◄    │    ◄    │         │    ◄    │         │
├─────────────────────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┤
│ Observability Collector │    ►    │    -    │    ◄    │    ►    │    ◄    │         │
├─────────────────────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┤
│ Intelligence Engine     │    ►    │    ►    │    -    │    ►    │    ◄    │         │
├─────────────────────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┤
│ Realtime Streaming      │         │         │         │    -    │    ◄    │    ◄    │
├─────────────────────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┤
│ API Gateway             │    ►    │    ►    │    ►    │    ►    │    -    │    ◄    │
├─────────────────────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┤
│ Frontend                │         │         │         │    ►    │    ►    │    -    │
└─────────────────────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┘

Legend: ► = depends on (calls)    ◄ = depended by (called by)
```

---

## 3. Communication Patterns

### 3.1 Synchronous (REST API)

| From | To | Protocol | Purpose |
|------|-----|----------|---------|
| API Gateway | Cluster Registry | HTTP/REST | Cluster CRUD, fleet queries |
| API Gateway | Observability Collector | HTTP/REST | Metrics, traces, logs queries |
| API Gateway | Intelligence Engine | HTTP/REST | Chat, analysis, reports |
| API Gateway | Realtime Streaming | HTTP/REST | Status, admin endpoints |
| Observability Collector | Cluster Registry | HTTP/REST | Get cluster info, credentials |
| Intelligence Engine | Cluster Registry | HTTP/REST | Get cluster context |
| Intelligence Engine | Observability Collector | HTTP/REST | Tool execution (metrics, traces) |

### 3.2 Asynchronous (Redis PubSub)

| Publisher | Event Types | Subscribers |
|-----------|-------------|-------------|
| Cluster Registry | `CLUSTER_*` | Realtime Streaming |
| Observability Collector | `ALERT_*`, `METRIC_*`, `GPU_*` | Realtime Streaming, Intelligence Engine |
| Intelligence Engine | `ANOMALY_*`, `CHAT_*`, `RCA_*` | Realtime Streaming |

### 3.3 WebSocket

| From | To | Purpose |
|------|-----|---------|
| Frontend | Realtime Streaming | Live updates, alerts, GPU metrics |

### 3.4 MCP Protocol

| From | To | Purpose |
|------|-----|---------|
| External AI Clients | Intelligence Engine | Tool-augmented AI chat |
| Frontend | Intelligence Engine | AI chat with tools |

---

## 4. API Contracts

### 4.1 Cluster Registry → Other Services

**Base URL:** `http://cluster-registry:8080`

```yaml
# Get cluster by ID
GET /api/v1/clusters/{id}
Response: Cluster

# List clusters with filtering
GET /api/v1/clusters?environment=PRODUCTION&has_gpu=true
Response: PaginatedResponse<Cluster>

# Get cluster credentials (internal only)
GET /internal/v1/clusters/{id}/credentials
Response: ResolvedCredentials
Headers:
  X-Internal-Token: <service-account-token>
```

### 4.2 Observability Collector → Cluster Registry

```yaml
# Required calls from Observability Collector:

# Get cluster info for context
GET /api/v1/clusters/{id}
Purpose: Get cluster name, endpoints, capabilities

# Get credentials for Prometheus/Tempo/Loki access
GET /internal/v1/clusters/{id}/credentials
Purpose: Get bearer tokens for querying

# Get all online clusters
GET /api/v1/clusters?state=ONLINE
Purpose: Federation queries to all clusters
```

### 4.3 Intelligence Engine → Observability Collector

**Base URL:** `http://observability-collector:8080`

```yaml
# Metrics queries (for tools)
POST /api/v1/metrics/query_range
Request: MetricQuery
Response: List[MetricResult]

# Trace searches (for tools)
POST /api/v1/traces/search
Request: TraceQuery
Response: List[Trace]

# Log queries (for tools)
POST /api/v1/logs/query
Request: LogQuery
Response: List[LogEntry]

# Alert listing (for tools)
GET /api/v1/alerts?state=FIRING
Response: List[Alert]

# GPU data (for tools)
GET /api/v1/gpu/nodes
Response: List[GPUNode]
```

### 4.4 Intelligence Engine → Cluster Registry

```yaml
# Get clusters for session context
GET /api/v1/clusters
Purpose: List available clusters for user selection

# Get specific cluster details
GET /api/v1/clusters/{id}
Purpose: Include cluster info in AI responses
```

---

## 5. Event Contracts

### 5.1 Redis Channel Structure

```
aiops:events:{type}:{optional-id}

Examples:
aiops:events:all                     # All events (main channel)
aiops:events:cluster:550e8400-...    # Events for specific cluster
aiops:events:alerts                  # All alert events
aiops:events:gpu                     # All GPU events
aiops:events:anomaly                 # All anomaly events
```

### 5.2 Event Message Format

```json
{
  "event_id": "uuid",
  "event_type": "ALERT_FIRED",
  "source": "observability-collector",
  "cluster_id": "uuid",
  "timestamp": "2024-12-24T10:00:00Z",
  "payload": {
    // Event-specific data
  }
}
```

### 5.3 Event Type Catalog

| Event Type | Source | Payload Schema | Description |
|------------|--------|----------------|-------------|
| `CLUSTER_REGISTERED` | Cluster Registry | `Cluster` | New cluster added |
| `CLUSTER_UPDATED` | Cluster Registry | `Cluster` | Cluster metadata changed |
| `CLUSTER_DELETED` | Cluster Registry | `{cluster_id}` | Cluster removed |
| `CLUSTER_STATUS_CHANGED` | Cluster Registry | `ClusterStatusChange` | Health state changed |
| `CLUSTER_CREDENTIALS_UPDATED` | Cluster Registry | `{cluster_id}` | Credentials rotated |
| `CLUSTER_CAPABILITIES_CHANGED` | Cluster Registry | `{cluster_id, capabilities}` | Capabilities changed |
| `ALERT_FIRED` | Observability Collector | `Alert` | New alert firing |
| `ALERT_RESOLVED` | Observability Collector | `Alert` | Alert resolved |
| `METRIC_UPDATE` | Observability Collector | `MetricEvent` | Significant metric change |
| `GPU_UPDATE` | Observability Collector | `GPUNode` | GPU telemetry update |
| `TRACE_RECEIVED` | Observability Collector | `TraceSummary` | New error trace |
| `ANOMALY_DETECTED` | Intelligence Engine | `AnomalyDetection` | Anomaly found |
| `CHAT_MESSAGE` | Intelligence Engine | `ChatMessage` | New chat message |
| `RCA_COMPLETE` | Intelligence Engine | `RCAResult` | RCA analysis done |
| `REPORT_GENERATED` | Intelligence Engine | `Report` | Report ready |

---

## 6. Shared Data Stores

### 6.1 PostgreSQL

**Single database `aiops` with separate schemas for isolation:**

| Schema | Owner | Tables | Consumers |
|--------|-------|--------|-----------|
| `clusters` | Cluster Registry | `clusters`, `cluster_health_history` | Read: All services |
| `intelligence` | Intelligence Engine | `chat_sessions`, `chat_messages`, `personas`, `reports` | Read: API Gateway |

```
Database: aiops
├── Schema: clusters (owned by cluster-registry service account)
│   ├── clusters
│   └── cluster_health_history
└── Schema: intelligence (owned by intelligence-engine service account)
    ├── chat_sessions
    ├── chat_messages
    ├── personas
    └── reports
```

**Cross-Service Access:**
- Other services access Cluster Registry data through REST API only (no direct DB access)
- Intelligence Engine schema is private; accessed only through API
- Each service connects with its own credentials and schema permissions

### 6.2 Redis

| Database | Purpose | Key Patterns |
|----------|---------|--------------|
| `0` | PubSub, Events | `aiops:events:*` |
| `1` | Rate Limiting | `ratelimit:user:{user_id}:*` |
| `2` | Caching | `cache:{service}:{key}` |
| `3` | Sessions | `session:{session_id}` |

**Cache Key Patterns:**

```
# Cluster Registry
cache:clusters:list                    # Cluster list cache
cache:clusters:{id}                    # Single cluster cache
cache:clusters:credentials:{id}        # Credentials cache (short TTL)

# Observability Collector
cache:metrics:instant:{hash}:{cluster} # Instant query cache
cache:metrics:range:{hash}:{cluster}   # Range query cache
cache:gpu:{cluster}:{node}             # GPU telemetry cache
cache:alerts:active:{cluster}          # Active alerts cache

# Intelligence Engine
cache:personas:builtin                 # Built-in personas
cache:tools:schema                     # Tool schemas
```

### 6.3 Object Store (MinIO/S3)

| Bucket | Owner | Contents | Retention |
|--------|-------|----------|-----------|
| `aiops-reports` | Intelligence Engine | Generated reports | 90 days |
| `aiops-attachments` | Intelligence Engine | Chat file uploads | 7 days |

---

## 7. Authentication & Authorization Flow

### 7.1 External Request Flow

```
┌────────┐     ┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│ User   │────►│ OpenShift   │────►│ API Gateway  │────►│ Backend     │
│        │     │ OAuth       │     │              │     │ Service     │
└────────┘     └─────────────┘     └──────────────┘     └─────────────┘
     │              │                    │                    │
     │  1. Login    │                    │                    │
     │─────────────►│                    │                    │
     │              │                    │                    │
     │  2. JWT      │                    │                    │
     │◄─────────────│                    │                    │
     │                                   │                    │
     │  3. Request + JWT                 │                    │
     │──────────────────────────────────►│                    │
     │                                   │                    │
     │               4. Validate JWT     │                    │
     │               ┌──────────────────►│                    │
     │               │                   │                    │
     │               │  5. User Info     │                    │
     │               │◄──────────────────│                    │
     │                                   │                    │
     │                                   │ 6. Forward         │
     │                                   │   + X-User-Info    │
     │                                   │───────────────────►│
     │                                   │                    │
     │                                   │ 7. Response        │
     │                                   │◄───────────────────│
     │                                   │                    │
     │  8. Response                      │                    │
     │◄──────────────────────────────────│                    │
```

### 7.2 Service-to-Service Authentication

```yaml
# Internal requests include service account token
Headers:
  X-Internal-Token: <pod-service-account-token>
  X-Service-Name: observability-collector
  X-Request-ID: <uuid>

# Validated via Kubernetes TokenReview API
```

### 7.3 Authorization Headers

```yaml
# Forwarded by API Gateway to backends
Headers:
  X-User-ID: user@example.com
  X-User-Groups: platform-admins,developers
  X-Cluster-Access: 550e8400-...,660e8400-...  # Allowed clusters
```

---

## 8. Health Check Integration

### 8.1 Service Health Endpoints

| Service | Health | Ready |
|---------|--------|-------|
| Cluster Registry | `GET /health` | `GET /ready` |
| Observability Collector | `GET /health` | `GET /ready` |
| Intelligence Engine | `GET /health` | `GET /ready` |
| Realtime Streaming | `GET /health` | `GET /ready` |
| API Gateway | `GET /health` | `GET /ready` |

### 8.2 Aggregated Health (API Gateway)

```json
GET /health/detailed

{
  "status": "healthy",
  "services": {
    "cluster-registry": { "status": "healthy", "latency_ms": 5 },
    "observability-collector": { "status": "healthy", "latency_ms": 8 },
    "intelligence-engine": { "status": "healthy", "latency_ms": 12 },
    "realtime-streaming": { "status": "healthy", "latency_ms": 3 }
  },
  "dependencies": {
    "redis": { "status": "healthy", "latency_ms": 1 },
    "postgresql": { "status": "healthy", "latency_ms": 2 }
  }
}
```

---

## 9. Error Propagation

### 9.1 Error Code Mapping

| Backend Error | Gateway Response | Client Message |
|---------------|------------------|----------------|
| `CLUSTER_NOT_FOUND` | 404 | "Cluster not found" |
| `CLUSTER_UNREACHABLE` | 503 | "Cluster temporarily unavailable" |
| `QUERY_TIMEOUT` | 504 | "Query timed out" |
| `RATE_LIMITED` | 429 | "Too many requests" |
| `AUTH_FAILED` | 401 | "Authentication required" |
| `PERMISSION_DENIED` | 403 | "Access denied" |
| `INTERNAL_ERROR` | 500 | "Internal server error" |

### 9.2 Error Response Format

```json
{
  "error": {
    "code": "CLUSTER_NOT_FOUND",
    "message": "Cluster with ID 550e8400-... not found",
    "service": "cluster-registry",
    "trace_id": "abc123-def456",
    "timestamp": "2024-12-24T10:00:00Z"
  }
}
```

---

## 10. Data Consistency

### 10.1 Eventual Consistency

| Data Type | Consistency Model | Max Delay |
|-----------|-------------------|-----------|
| Cluster Status | Eventual | 30 seconds |
| GPU Metrics | Eventual | 5 seconds |
| Alerts | Eventual | 10 seconds |
| Chat Sessions | Strong (per session) | Immediate |

### 10.2 Cache Invalidation

```yaml
# On cluster update
Cluster Registry:
  - Invalidate: cache:clusters:{id}
  - Publish: CLUSTER_UPDATED event

# Subscribers (Observability Collector, Intelligence Engine)
  - Receive CLUSTER_UPDATED event
  - Invalidate local caches
```

---

## 11. Circuit Breaker Configuration

```yaml
circuit_breaker:
  cluster_registry:
    failure_threshold: 5
    recovery_timeout: 30s
    half_open_requests: 3

  observability_collector:
    failure_threshold: 10
    recovery_timeout: 60s
    half_open_requests: 5

  intelligence_engine:
    failure_threshold: 5
    recovery_timeout: 30s
    half_open_requests: 3
```

---

## 12. Request Tracing

### 12.1 Trace Context Propagation

```yaml
Headers (W3C Trace Context):
  traceparent: 00-abc123-def456-01
  tracestate: aiops=gateway

# All services propagate to downstream calls
```

### 12.2 Span Hierarchy

```
Gateway Span
├── Auth Validation Span
├── Rate Limit Check Span
└── Backend Request Span
    ├── Database Query Span
    ├── Redis Cache Span
    └── External API Span (Prometheus, etc.)
```

---

## 13. Integration Checklist

Before deployment, verify:

- [ ] All REST endpoints accessible between services
- [ ] Redis PubSub channels configured
- [ ] PostgreSQL databases created with correct permissions
- [ ] Object storage buckets created
- [ ] Service accounts with correct RBAC
- [ ] Network policies allow required traffic
- [ ] Health check endpoints responding
- [ ] Trace context propagating correctly
- [ ] Error responses in correct format
- [ ] Rate limiting working as expected

---

## Next: [09-deployment.md](./09-deployment.md)
