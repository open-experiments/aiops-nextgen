# 01 - Core Data Models

## Document Info
| Field | Value |
|-------|-------|
| Version | 0.1.0 |
| Status | Draft |
| Last Updated | 2024-12-24 |

---

## 1. Overview

This document defines the shared data models used across all AIOps NextGen components. These models serve as the canonical schema for inter-component communication and data storage.

**Conventions:**
- All timestamps are ISO 8601 format with timezone (UTC preferred)
- All IDs are UUID v4 unless otherwise specified
- Enums are uppercase snake_case
- Field names are lowercase snake_case

---

## 2. Cluster Domain Models

### 2.1 Cluster

Represents a registered OpenShift/Kubernetes cluster.

```yaml
Cluster:
  type: object
  required:
    - id
    - name
    - api_server_url
    - status
    - created_at
  properties:
    id:
      type: string
      format: uuid
      description: Unique identifier
      example: "550e8400-e29b-41d4-a716-446655440000"

    name:
      type: string
      pattern: "^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$"
      description: Human-readable cluster name (DNS-compatible)
      example: "prod-east-1"

    display_name:
      type: string
      maxLength: 128
      description: Display name for UI
      example: "Production East 1"

    api_server_url:
      type: string
      format: uri
      description: Kubernetes API server URL
      example: "https://api.prod-east-1.example.com:6443"

    cluster_type:
      type: string
      enum: [HUB, SPOKE, EDGE, FAR_EDGE]
      default: SPOKE
      description: Cluster role in the fleet

    platform:
      type: string
      enum: [OPENSHIFT, KUBERNETES, MICROSHIFT]
      default: OPENSHIFT

    platform_version:
      type: string
      description: Platform version (e.g., "4.14.5")
      example: "4.14.5"

    region:
      type: string
      description: Geographic region or zone
      example: "us-east-1"

    environment:
      type: string
      enum: [PRODUCTION, STAGING, DEVELOPMENT, LAB]
      default: DEVELOPMENT

    status:
      $ref: "#/ClusterStatus"

    capabilities:
      $ref: "#/ClusterCapabilities"

    endpoints:
      $ref: "#/ClusterEndpoints"

    labels:
      type: object
      additionalProperties:
        type: string
      description: Key-value labels for filtering
      example:
        team: "platform"
        cost-center: "eng-001"

    created_at:
      type: string
      format: date-time

    updated_at:
      type: string
      format: date-time

    last_seen_at:
      type: string
      format: date-time
      description: Last successful health check
```

### 2.2 ClusterStatus

```yaml
ClusterStatus:
  type: object
  properties:
    state:
      type: string
      enum: [ONLINE, OFFLINE, DEGRADED, UNKNOWN, PROVISIONING]
      description: Current cluster state

    health_score:
      type: integer
      minimum: 0
      maximum: 100
      description: Overall health score (0-100)

    last_error:
      type: string
      description: Last error message if any

    connectivity:
      type: string
      enum: [CONNECTED, DISCONNECTED, INTERMITTENT]

    api_server_healthy:
      type: boolean

    prometheus_healthy:
      type: boolean

    tempo_healthy:
      type: boolean

    loki_healthy:
      type: boolean
```

### 2.3 ClusterCapabilities

```yaml
ClusterCapabilities:
  type: object
  description: Detected cluster capabilities
  properties:
    has_gpu_nodes:
      type: boolean
      default: false

    gpu_count:
      type: integer
      default: 0

    gpu_types:
      type: array
      items:
        type: string
      example: ["NVIDIA A100", "NVIDIA H100"]

    has_prometheus:
      type: boolean
      default: true

    has_thanos:
      type: boolean
      default: false

    has_tempo:
      type: boolean
      default: false

    has_loki:
      type: boolean
      default: false

    has_service_mesh:
      type: boolean
      default: false

    has_cnf_workloads:
      type: boolean
      default: false

    cnf_types:
      type: array
      items:
        type: string
        enum: [VDU, VCU, UPF, AMF, SMF, OTHER]
      description: Types of CNF workloads detected
```

### 2.4 ClusterEndpoints

```yaml
ClusterEndpoints:
  type: object
  description: Observability endpoints for the cluster
  properties:
    prometheus_url:
      type: string
      format: uri
      description: Prometheus/Thanos query endpoint
      example: "https://thanos-querier.openshift-monitoring.svc:9091"

    tempo_url:
      type: string
      format: uri
      description: Tempo query endpoint

    loki_url:
      type: string
      format: uri
      description: Loki query endpoint

    alertmanager_url:
      type: string
      format: uri
      description: Alertmanager API endpoint
```

### 2.5 ClusterCredentials

```yaml
ClusterCredentials:
  type: object
  description: Stored encrypted, never returned via API
  properties:
    cluster_id:
      type: string
      format: uuid

    auth_type:
      type: string
      enum: [KUBECONFIG, SERVICE_ACCOUNT, OIDC]

    kubeconfig_encrypted:
      type: string
      format: byte
      description: AES-256 encrypted kubeconfig

    service_account_token_secret_ref:
      type: string
      description: Reference to K8s Secret containing SA token

    prometheus_token_secret_ref:
      type: string
      description: Reference to K8s Secret for Prometheus auth

    created_at:
      type: string
      format: date-time

    expires_at:
      type: string
      format: date-time
      description: Token expiration time
```

---

## 3. Observability Domain Models

### 3.1 MetricQuery

```yaml
MetricQuery:
  type: object
  required:
    - query
  properties:
    query:
      type: string
      description: PromQL query string
      example: "sum(rate(container_cpu_usage_seconds_total[5m])) by (namespace)"

    cluster_ids:
      type: array
      items:
        type: string
        format: uuid
      description: Target clusters (empty = all clusters)

    start_time:
      type: string
      format: date-time
      description: Query start time (default: now - 1h)

    end_time:
      type: string
      format: date-time
      description: Query end time (default: now)

    step:
      type: string
      description: Query resolution step
      example: "1m"
      default: "1m"

    timeout:
      type: integer
      description: Query timeout in seconds
      default: 30
      maximum: 300
```

### 3.2 MetricResult

```yaml
MetricResult:
  type: object
  properties:
    cluster_id:
      type: string
      format: uuid

    cluster_name:
      type: string

    status:
      type: string
      enum: [SUCCESS, ERROR, TIMEOUT, PARTIAL]

    result_type:
      type: string
      enum: [MATRIX, VECTOR, SCALAR, STRING]

    data:
      type: array
      items:
        $ref: "#/MetricSeries"

    error:
      type: string
      description: Error message if status != SUCCESS

    query_time_ms:
      type: integer
      description: Query execution time in milliseconds
```

### 3.3 MetricSeries

```yaml
MetricSeries:
  type: object
  properties:
    metric:
      type: object
      additionalProperties:
        type: string
      description: Label set
      example:
        __name__: "container_cpu_usage_seconds_total"
        namespace: "default"
        pod: "nginx-abc123"

    values:
      type: array
      items:
        type: array
        items:
          - type: number
            description: Unix timestamp
          - type: string
            description: Value
      description: "[timestamp, value] pairs"
```

### 3.4 TraceQuery

```yaml
TraceQuery:
  type: object
  properties:
    cluster_ids:
      type: array
      items:
        type: string
        format: uuid

    service_name:
      type: string
      description: Filter by service name (supports wildcards)
      example: "order-*"

    operation_name:
      type: string
      description: Filter by operation/span name

    trace_id:
      type: string
      description: Specific trace ID to retrieve

    min_duration_ms:
      type: integer
      description: Minimum trace duration filter

    max_duration_ms:
      type: integer
      description: Maximum trace duration filter

    tags:
      type: object
      additionalProperties:
        type: string
      description: Tag filters
      example:
        http.status_code: "500"
        error: "true"

    start_time:
      type: string
      format: date-time

    end_time:
      type: string
      format: date-time

    limit:
      type: integer
      default: 20
      maximum: 100
```

### 3.5 Trace

```yaml
Trace:
  type: object
  properties:
    trace_id:
      type: string
      example: "abc123def456"

    cluster_id:
      type: string
      format: uuid

    cluster_name:
      type: string

    root_service:
      type: string
      description: Service that initiated the trace

    root_operation:
      type: string

    start_time:
      type: string
      format: date-time

    duration_ms:
      type: integer

    span_count:
      type: integer

    service_count:
      type: integer

    has_errors:
      type: boolean

    spans:
      type: array
      items:
        $ref: "#/Span"
```

### 3.6 Span

```yaml
Span:
  type: object
  properties:
    span_id:
      type: string

    parent_span_id:
      type: string

    operation_name:
      type: string

    service_name:
      type: string

    start_time:
      type: string
      format: date-time

    duration_ms:
      type: integer

    status:
      type: string
      enum: [OK, ERROR, UNSET]

    tags:
      type: object
      additionalProperties:
        type: string

    logs:
      type: array
      items:
        type: object
        properties:
          timestamp:
            type: string
            format: date-time
          message:
            type: string
```

### 3.7 LogQuery

```yaml
LogQuery:
  type: object
  properties:
    cluster_ids:
      type: array
      items:
        type: string
        format: uuid

    query:
      type: string
      description: LogQL query string
      example: '{namespace="default"} |= "error"'

    start_time:
      type: string
      format: date-time

    end_time:
      type: string
      format: date-time

    limit:
      type: integer
      default: 100
      maximum: 5000

    direction:
      type: string
      enum: [FORWARD, BACKWARD]
      default: BACKWARD
```

### 3.8 LogEntry

```yaml
LogEntry:
  type: object
  properties:
    cluster_id:
      type: string
      format: uuid

    cluster_name:
      type: string

    timestamp:
      type: string
      format: date-time

    stream:
      type: object
      additionalProperties:
        type: string
      description: Log stream labels
      example:
        namespace: "default"
        pod: "nginx-abc123"
        container: "nginx"

    message:
      type: string
      description: Log line content
```

### 3.9 Alert

```yaml
Alert:
  type: object
  properties:
    id:
      type: string
      format: uuid

    fingerprint:
      type: string
      description: Unique alert fingerprint from Alertmanager

    cluster_id:
      type: string
      format: uuid

    cluster_name:
      type: string

    alertname:
      type: string
      example: "HighCPUUsage"

    severity:
      type: string
      enum: [CRITICAL, WARNING, INFO]

    state:
      type: string
      enum: [FIRING, RESOLVED, PENDING]

    labels:
      type: object
      additionalProperties:
        type: string

    annotations:
      type: object
      additionalProperties:
        type: string
      example:
        summary: "CPU usage above 90%"
        description: "Pod nginx-abc123 has CPU > 90%"

    starts_at:
      type: string
      format: date-time

    ends_at:
      type: string
      format: date-time

    generator_url:
      type: string
      format: uri
      description: Link to Prometheus/source
```

---

## 4. GPU Domain Models

### 4.1 GPUNode

```yaml
GPUNode:
  type: object
  properties:
    cluster_id:
      type: string
      format: uuid

    cluster_name:
      type: string

    node_name:
      type: string
      example: "worker-gpu-01"

    gpus:
      type: array
      items:
        $ref: "#/GPU"

    last_updated:
      type: string
      format: date-time
```

### 4.2 GPU

```yaml
GPU:
  type: object
  properties:
    index:
      type: integer
      description: GPU index on the node

    uuid:
      type: string
      description: NVIDIA GPU UUID
      example: "GPU-abc123-def456"

    name:
      type: string
      example: "NVIDIA A100-SXM4-80GB"

    driver_version:
      type: string
      example: "535.104.12"

    cuda_version:
      type: string
      example: "12.2"

    memory_total_mb:
      type: integer
      example: 81920

    memory_used_mb:
      type: integer

    memory_free_mb:
      type: integer

    utilization_gpu_percent:
      type: integer
      minimum: 0
      maximum: 100

    utilization_memory_percent:
      type: integer
      minimum: 0
      maximum: 100

    temperature_celsius:
      type: integer

    power_draw_watts:
      type: number

    power_limit_watts:
      type: number

    fan_speed_percent:
      type: integer
      minimum: 0
      maximum: 100

    processes:
      type: array
      items:
        $ref: "#/GPUProcess"
```

### 4.3 GPUProcess

```yaml
GPUProcess:
  type: object
  properties:
    pid:
      type: integer

    process_name:
      type: string

    used_memory_mb:
      type: integer

    type:
      type: string
      enum: [COMPUTE, GRAPHICS, MIXED]
```

---

## 5. Intelligence Domain Models

### 5.1 Persona

```yaml
Persona:
  type: object
  properties:
    id:
      type: string
      pattern: "^[a-z][a-z0-9-]{2,30}[a-z0-9]$"
      description: Unique persona identifier
      example: "platform-ops"

    name:
      type: string
      example: "Platform Operations Expert"

    description:
      type: string
      example: "Specializes in OpenShift platform operations"

    system_prompt:
      type: string
      description: System prompt defining persona behavior

    capabilities:
      type: array
      items:
        type: string
      description: MCP tools this persona can use
      example: ["query_metrics", "analyze_traces", "get_alerts"]

    icon:
      type: string
      description: Icon identifier for UI
      example: "server"

    is_builtin:
      type: boolean
      default: false
      description: Whether this is a system-provided persona

    created_by:
      type: string
      description: User who created custom persona
```

### 5.2 ChatMessage

```yaml
ChatMessage:
  type: object
  properties:
    id:
      type: string
      format: uuid

    session_id:
      type: string
      format: uuid

    role:
      type: string
      enum: [USER, ASSISTANT, SYSTEM, TOOL]

    content:
      type: string

    persona_id:
      type: string
      description: Active persona when message was sent

    tool_calls:
      type: array
      items:
        $ref: "#/ToolCall"
      description: Tools invoked by assistant

    tool_results:
      type: array
      items:
        $ref: "#/ToolResult"
      description: Results from tool calls

    model:
      type: string
      description: LLM model used
      example: "meta-llama/Llama-3.2-3B-Instruct"

    tokens_used:
      type: integer

    latency_ms:
      type: integer

    created_at:
      type: string
      format: date-time
```

### 5.3 ToolCall

```yaml
ToolCall:
  type: object
  properties:
    id:
      type: string

    name:
      type: string
      description: MCP tool name
      example: "query_metrics"

    arguments:
      type: object
      description: Tool arguments as JSON
```

### 5.4 ToolResult

```yaml
ToolResult:
  type: object
  properties:
    tool_call_id:
      type: string

    status:
      type: string
      enum: [SUCCESS, ERROR, TIMEOUT]

    result:
      type: object
      description: Tool result as JSON

    error:
      type: string
```

### 5.5 ChatSession

```yaml
ChatSession:
  type: object
  properties:
    id:
      type: string
      format: uuid

    user_id:
      type: string
      description: User who owns the session

    title:
      type: string
      description: Auto-generated or user-set title
      example: "GPU utilization investigation"

    persona_id:
      type: string
      default: "default"

    cluster_context:
      type: array
      items:
        type: string
        format: uuid
      description: Clusters in scope for this session

    message_count:
      type: integer

    created_at:
      type: string
      format: date-time

    updated_at:
      type: string
      format: date-time

    expires_at:
      type: string
      format: date-time
      description: Session expiration (default: 24h from last activity)
```

### 5.6 AnomalyDetection

```yaml
AnomalyDetection:
  type: object
  properties:
    id:
      type: string
      format: uuid

    cluster_id:
      type: string
      format: uuid

    metric_name:
      type: string
      example: "container_cpu_usage_seconds_total"

    labels:
      type: object
      additionalProperties:
        type: string

    detection_type:
      type: string
      enum: [STATISTICAL, ML_BASED, LLM_ASSISTED]

    severity:
      type: string
      enum: [HIGH, MEDIUM, LOW]

    confidence_score:
      type: number
      minimum: 0
      maximum: 1
      example: 0.92

    anomaly_type:
      type: string
      enum: [SPIKE, DROP, TREND_CHANGE, PATTERN_BREAK, THRESHOLD_BREACH]

    expected_value:
      type: number

    actual_value:
      type: number

    deviation_percent:
      type: number

    explanation:
      type: string
      description: Human-readable explanation

    detected_at:
      type: string
      format: date-time

    related_alerts:
      type: array
      items:
        type: string
        format: uuid
```

---

## 6. Event Models (for Streaming)

### 6.1 Event

Base event model for real-time streaming.

```yaml
Event:
  type: object
  required:
    - event_type
    - timestamp
  properties:
    event_id:
      type: string
      format: uuid

    event_type:
      type: string
      enum:
        - CLUSTER_STATUS_CHANGED
        - METRIC_UPDATE
        - ALERT_FIRED
        - ALERT_RESOLVED
        - TRACE_RECEIVED
        - GPU_UPDATE
        - ANOMALY_DETECTED
        - CHAT_MESSAGE

    cluster_id:
      type: string
      format: uuid

    timestamp:
      type: string
      format: date-time

    payload:
      type: object
      description: Event-specific payload
```

### 6.2 Subscription

```yaml
Subscription:
  type: object
  properties:
    id:
      type: string
      format: uuid

    client_id:
      type: string
      description: WebSocket client identifier

    event_types:
      type: array
      items:
        type: string
      description: Event types to receive

    cluster_filter:
      type: array
      items:
        type: string
        format: uuid
      description: Filter by cluster IDs (empty = all)

    namespace_filter:
      type: array
      items:
        type: string
      description: Filter by namespaces

    created_at:
      type: string
      format: date-time
```

---

## 7. Report Models

### 7.1 Report

```yaml
Report:
  type: object
  properties:
    id:
      type: string
      format: uuid

    title:
      type: string
      example: "Weekly GPU Utilization Report"

    report_type:
      type: string
      enum: [EXECUTIVE_SUMMARY, DETAILED_ANALYSIS, INCIDENT_REPORT, CAPACITY_PLAN]

    format:
      type: string
      enum: [HTML, PDF, MARKDOWN, JSON]

    cluster_scope:
      type: array
      items:
        type: string
        format: uuid

    time_range:
      type: object
      properties:
        start:
          type: string
          format: date-time
        end:
          type: string
          format: date-time

    generated_by:
      type: string
      description: User or "system" for scheduled reports

    storage_path:
      type: string
      description: Object storage path

    size_bytes:
      type: integer

    created_at:
      type: string
      format: date-time

    expires_at:
      type: string
      format: date-time
```

---

## 8. Common Types

### 8.1 Pagination

```yaml
PaginationParams:
  type: object
  properties:
    page:
      type: integer
      minimum: 1
      default: 1

    page_size:
      type: integer
      minimum: 1
      maximum: 100
      default: 20

PaginatedResponse:
  type: object
  properties:
    items:
      type: array

    total:
      type: integer
      description: Total number of items

    page:
      type: integer

    page_size:
      type: integer

    total_pages:
      type: integer
```

### 8.2 TimeRange

```yaml
TimeRange:
  type: object
  properties:
    start:
      type: string
      format: date-time

    end:
      type: string
      format: date-time

    duration:
      type: string
      description: Alternative to start/end - relative duration
      example: "1h"
      pattern: "^[0-9]+[smhdw]$"
```

### 8.3 ErrorResponse

```yaml
ErrorResponse:
  type: object
  required:
    - error_code
    - message
  properties:
    error_code:
      type: string
      example: "CLUSTER_NOT_FOUND"

    message:
      type: string
      example: "Cluster with ID xyz not found"

    details:
      type: object
      description: Additional error context

    trace_id:
      type: string
      description: Request trace ID for debugging

    timestamp:
      type: string
      format: date-time
```

---

## 9. Model Relationships

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA MODEL RELATIONSHIPS                          │
└─────────────────────────────────────────────────────────────────────────────┘

Cluster (1) ─────────┬────────── (N) MetricResult
                     │
                     ├────────── (N) Trace
                     │
                     ├────────── (N) LogEntry
                     │
                     ├────────── (N) Alert
                     │
                     ├────────── (N) GPUNode ──── (N) GPU ──── (N) GPUProcess
                     │
                     └────────── (N) AnomalyDetection

Cluster (1) ────────────────── (1) ClusterCredentials (stored separately)

ChatSession (1) ────────────── (N) ChatMessage ──── (N) ToolCall
                                                    │
                                                    └─── (1) ToolResult

Persona (1) ────────────────── (N) ChatSession

Report (N) ────────────────── (N) Cluster (many-to-many via cluster_scope)

Event ─────────────────────── Ephemeral (not persisted, streamed only)
Subscription ──────────────── Session-scoped (WebSocket connection lifetime)
```

---

## 10. Validation Rules Summary

| Model | Field | Rule |
|-------|-------|------|
| Cluster | name | DNS-compatible, 3-63 chars |
| Cluster | api_server_url | Valid HTTPS URL |
| MetricQuery | query | Valid PromQL syntax |
| MetricQuery | timeout | 1-300 seconds |
| LogQuery | limit | 1-5000 |
| TraceQuery | limit | 1-100 |
| Persona | id | Lowercase alphanumeric with hyphens |
| ChatSession | expires_at | Max 7 days from creation |
| Report | format | Must be supported format |
| TimeRange | duration | Valid duration pattern |

---

## 11. Open Questions

1. **Encryption at Rest**: Should ClusterCredentials use K8s Secrets or external vault (HashiCorp)?
2. **Soft Delete**: Should we support soft delete for audit trail on Clusters/Sessions?
3. **Event TTL**: How long should events be retained in Redis for late subscribers?
4. **Multi-tenancy**: Should models include `tenant_id` for future multi-tenant support?

---

## Next: [02-cluster-registry.md](./02-cluster-registry.md)
