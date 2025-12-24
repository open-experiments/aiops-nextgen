# 03 - Observability Collector Service

## Document Info
| Field | Value |
|-------|-------|
| Version | 0.1.0 |
| Status | Draft |
| Last Updated | 2024-12-24 |

---

## 1. Purpose

The Observability Collector Service provides unified access to metrics, traces, logs, and alerts across all managed clusters. It handles:

- Federated queries across multiple Prometheus/Thanos instances
- Distributed trace retrieval from Tempo endpoints
- Log aggregation from Loki instances
- Alert forwarding from Alertmanager
- Direct GPU telemetry collection (nvidia-smi)
- CNF-specific metric collection

---

## 2. Responsibilities

| Responsibility | Description |
|----------------|-------------|
| **Metric Federation** | Execute PromQL across multiple clusters, aggregate results |
| **Trace Collection** | Query Tempo instances, correlate cross-cluster traces |
| **Log Aggregation** | Execute LogQL across Loki instances |
| **Alert Handling** | Receive and forward alerts from cluster Alertmanagers |
| **GPU Telemetry** | Collect nvidia-smi data from GPU nodes |
| **CNF Metrics** | Collect specialized CNF metrics (DPDK, PTP, etc.) |
| **Data Caching** | Cache frequent queries for performance |

---

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       OBSERVABILITY COLLECTOR SERVICE                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                           API Layer                                    │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │ │
│  │  │ Metrics API  │  │ Traces API   │  │ Logs API     │                  │ │
│  │  │ /metrics/*   │  │ /traces/*    │  │ /logs/*      │                  │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                  │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │ │
│  │  │ Alerts API   │  │ GPU API      │  │ CNF API      │                  │ │
│  │  │ /alerts/*    │  │ /gpu/*       │  │ /cnf/*       │                  │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                  │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                      │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         Service Layer                                  │ │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐            │ │
│  │  │ MetricsService │  │ TracesService  │  │ LogsService    │            │ │
│  │  │                │  │                │  │                │            │ │
│  │  │ • query()      │  │ • search()     │  │ • query()      │            │ │
│  │  │ • query_range()│  │ • get_trace()  │  │ • tail()       │            │ │
│  │  │ • series()     │  │ • analyze()    │  │ • labels()     │            │ │
│  │  │ • labels()     │  │                │  │                │            │ │
│  │  └────────────────┘  └────────────────┘  └────────────────┘            │ │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐            │ │
│  │  │ AlertsService  │  │ GPUService     │  │ CNFService     │            │ │
│  │  │                │  │                │  │                │            │ │
│  │  │ • list()       │  │ • get_nodes()  │  │ • get_metrics()│            │ │
│  │  │ • get()        │  │ • get_gpus()   │  │ • get_ptp()    │            │ │
│  │  │ • subscribe()  │  │ • get_procs()  │  │ • get_dpdk()   │            │ │
│  │  └────────────────┘  └────────────────┘  └────────────────┘            │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                      │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                       Collector Layer                                  │ │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐            │ │
│  │  │ Prometheus     │  │ Tempo          │  │ Loki           │            │ │
│  │  │ Collector      │  │ Collector      │  │ Collector      │            │ │
│  │  └────────────────┘  └────────────────┘  └────────────────┘            │ │
│  │  ┌────────────────┐  ┌────────────────┐                                │ │
│  │  │ Alertmanager   │  │ K8s Exec       │                                │ │
│  │  │ Collector      │  │ Collector      │                                │ │
│  │  │ (webhook recv) │  │ (nvidia-smi)   │                                │ │
│  │  └────────────────┘  └────────────────┘                                │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                      │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                        Cache Layer                                     │ │
│  │  ┌────────────────────────────────────────────────────────────────┐    │ │
│  │  │                         Redis                                  │    │ │
│  │  │  • Query result cache (TTL: 30s-5m)                            │    │ │
│  │  │  • GPU telemetry cache (TTL: 5s)                               │    │ │
│  │  │  • Alert state cache                                           │    │ │
│  │  └────────────────────────────────────────────────────────────────┘    │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
         ┌────────────────────────────┼────────────────────────────┐
         ▼                            ▼                            ▼
 ┌───────────────┐           ┌───────────────┐           ┌───────────────┐
 │  Cluster A    │           │  Cluster B    │           │  Cluster N    │
 │               │           │               │           │               │
 │  Prometheus ──┼───────────┼── Thanos ─────┼───────────┼── Prometheus  │
 │  Tempo ───────┼───────────┼── Tempo ──────┼───────────┼── (none)      │
 │  Loki ────────┼───────────┼── Loki ───────┼───────────┼── (none)      │
 │  Alertmanager─┼───────────┼── Alertmanager┼───────────┼── Alertmanager│
 │  GPU Nodes ───┼───────────┼── (none) ─────┼───────────┼── GPU Nodes   │
 └───────────────┘           └───────────────┘           └───────────────┘
```

---

## 4. API Specification

### 4.1 Metrics API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/metrics/query` | Execute instant PromQL query |
| `POST` | `/api/v1/metrics/query_range` | Execute range PromQL query |
| `GET` | `/api/v1/metrics/series` | Get matching series |
| `GET` | `/api/v1/metrics/labels` | Get label names |
| `GET` | `/api/v1/metrics/label/{name}/values` | Get label values |
| `GET` | `/api/v1/metrics/metadata` | Get metric metadata |

### 4.2 Traces API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/traces/search` | Search traces by criteria |
| `GET` | `/api/v1/traces/{trace_id}` | Get specific trace |
| `GET` | `/api/v1/traces/{trace_id}/spans` | Get spans for trace |
| `GET` | `/api/v1/traces/services` | List services with traces |
| `GET` | `/api/v1/traces/operations` | List operations for service |

### 4.3 Logs API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/logs/query` | Execute LogQL query |
| `POST` | `/api/v1/logs/query_range` | Execute range LogQL query |
| `GET` | `/api/v1/logs/labels` | Get log label names |
| `GET` | `/api/v1/logs/label/{name}/values` | Get log label values |
| `GET` | `/api/v1/logs/tail` | Tail logs (WebSocket upgrade) |

### 4.4 Alerts API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/alerts` | List active alerts |
| `GET` | `/api/v1/alerts/{fingerprint}` | Get alert by fingerprint |
| `GET` | `/api/v1/alerts/history` | Get alert history |
| `POST` | `/api/v1/alerts/webhook` | Alertmanager webhook receiver |

### 4.5 GPU API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/gpu/nodes` | List GPU nodes across clusters |
| `GET` | `/api/v1/gpu/nodes/{cluster_id}/{node_name}` | Get GPU node details |
| `GET` | `/api/v1/gpu/summary` | Fleet GPU summary |
| `GET` | `/api/v1/gpu/processes` | List GPU processes |

### 4.6 CNF API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/cnf/workloads` | List CNF workloads |
| `GET` | `/api/v1/cnf/ptp/status` | Get PTP sync status |
| `GET` | `/api/v1/cnf/dpdk/stats` | Get DPDK statistics |
| `GET` | `/api/v1/cnf/sriov/status` | Get SR-IOV VF status |

---

### 4.7 Request/Response Examples

#### Federated Metric Query

**Request:**
```http
POST /api/v1/metrics/query_range
Content-Type: application/json

{
  "query": "sum(rate(container_cpu_usage_seconds_total{namespace='production'}[5m])) by (pod)",
  "cluster_ids": [
    "550e8400-e29b-41d4-a716-446655440000",
    "660e8400-e29b-41d4-a716-446655440001"
  ],
  "start_time": "2024-12-24T09:00:00Z",
  "end_time": "2024-12-24T10:00:00Z",
  "step": "1m"
}
```

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "results": [
    {
      "cluster_id": "550e8400-e29b-41d4-a716-446655440000",
      "cluster_name": "prod-east-1",
      "status": "SUCCESS",
      "result_type": "MATRIX",
      "data": [
        {
          "metric": {
            "pod": "api-server-abc123"
          },
          "values": [
            [1703408400, "0.45"],
            [1703408460, "0.52"],
            [1703408520, "0.48"]
          ]
        }
      ],
      "query_time_ms": 45
    },
    {
      "cluster_id": "660e8400-e29b-41d4-a716-446655440001",
      "cluster_name": "prod-west-1",
      "status": "SUCCESS",
      "result_type": "MATRIX",
      "data": [
        {
          "metric": {
            "pod": "api-server-def456"
          },
          "values": [
            [1703408400, "0.38"],
            [1703408460, "0.41"],
            [1703408520, "0.39"]
          ]
        }
      ],
      "query_time_ms": 52
    }
  ],
  "total_query_time_ms": 98,
  "clusters_queried": 2,
  "clusters_succeeded": 2
}
```

#### Trace Search

**Request:**
```http
POST /api/v1/traces/search
Content-Type: application/json

{
  "cluster_ids": [],
  "service_name": "order-service",
  "min_duration_ms": 1000,
  "tags": {
    "http.status_code": "500"
  },
  "start_time": "2024-12-24T09:00:00Z",
  "end_time": "2024-12-24T10:00:00Z",
  "limit": 20
}
```

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "traces": [
    {
      "trace_id": "abc123def456789",
      "cluster_id": "550e8400-e29b-41d4-a716-446655440000",
      "cluster_name": "prod-east-1",
      "root_service": "api-gateway",
      "root_operation": "POST /orders",
      "start_time": "2024-12-24T09:15:32Z",
      "duration_ms": 2450,
      "span_count": 12,
      "service_count": 4,
      "has_errors": true
    }
  ],
  "total": 1
}
```

#### GPU Nodes

**Request:**
```http
GET /api/v1/gpu/nodes?cluster_id=550e8400-e29b-41d4-a716-446655440000
```

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "nodes": [
    {
      "cluster_id": "550e8400-e29b-41d4-a716-446655440000",
      "cluster_name": "prod-east-1",
      "node_name": "worker-gpu-01",
      "gpus": [
        {
          "index": 0,
          "uuid": "GPU-abc123",
          "name": "NVIDIA A100-SXM4-80GB",
          "memory_total_mb": 81920,
          "memory_used_mb": 45000,
          "memory_free_mb": 36920,
          "utilization_gpu_percent": 78,
          "utilization_memory_percent": 55,
          "temperature_celsius": 62,
          "power_draw_watts": 285.5,
          "power_limit_watts": 400,
          "fan_speed_percent": 45,
          "processes": [
            {
              "pid": 12345,
              "process_name": "python",
              "used_memory_mb": 42000,
              "type": "COMPUTE"
            }
          ]
        }
      ],
      "last_updated": "2024-12-24T10:00:05Z"
    }
  ],
  "total": 1
}
```

#### Alerts List

**Request:**
```http
GET /api/v1/alerts?state=FIRING&severity=CRITICAL
```

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "alerts": [
    {
      "id": "770e8400-e29b-41d4-a716-446655440002",
      "fingerprint": "abc123fingerprint",
      "cluster_id": "550e8400-e29b-41d4-a716-446655440000",
      "cluster_name": "prod-east-1",
      "alertname": "HighMemoryUsage",
      "severity": "CRITICAL",
      "state": "FIRING",
      "labels": {
        "namespace": "production",
        "pod": "api-server-abc123"
      },
      "annotations": {
        "summary": "Memory usage above 95%",
        "description": "Pod api-server-abc123 memory > 95%"
      },
      "starts_at": "2024-12-24T09:45:00Z",
      "generator_url": "https://prometheus.prod-east-1/graph?..."
    }
  ],
  "total": 1,
  "by_severity": {
    "CRITICAL": 1,
    "WARNING": 5,
    "INFO": 12
  }
}
```

---

## 5. Internal Service Interfaces

### 5.1 MetricsService

```python
class MetricsService:
    async def query(
        self,
        query: str,
        cluster_ids: List[UUID] = None,  # None = all clusters
        time: datetime = None
    ) -> List[MetricResult]:
        """Execute instant query across clusters."""

    async def query_range(
        self,
        query: str,
        cluster_ids: List[UUID] = None,
        start_time: datetime,
        end_time: datetime,
        step: str = "1m"
    ) -> List[MetricResult]:
        """Execute range query across clusters."""

    async def get_series(
        self,
        match: List[str],
        cluster_ids: List[UUID] = None,
        start_time: datetime = None,
        end_time: datetime = None
    ) -> Dict[UUID, List[Dict]]:
        """Get matching series from clusters."""

    async def get_labels(
        self,
        cluster_ids: List[UUID] = None
    ) -> Dict[UUID, List[str]]:
        """Get label names from clusters."""

    async def get_label_values(
        self,
        label: str,
        cluster_ids: List[UUID] = None
    ) -> Dict[UUID, List[str]]:
        """Get values for a label from clusters."""
```

### 5.2 TracesService

```python
class TracesService:
    async def search(
        self,
        query: TraceQuery
    ) -> List[Trace]:
        """Search traces across clusters."""

    async def get_trace(
        self,
        trace_id: str,
        cluster_id: UUID = None  # If known
    ) -> Trace:
        """Get specific trace by ID."""

    async def get_services(
        self,
        cluster_ids: List[UUID] = None
    ) -> Dict[UUID, List[str]]:
        """Get services with traces."""

    async def analyze_trace(
        self,
        trace_id: str
    ) -> TraceAnalysis:
        """Analyze trace for performance issues."""
```

### 5.3 LogsService

```python
class LogsService:
    async def query(
        self,
        query: str,  # LogQL
        cluster_ids: List[UUID] = None,
        start_time: datetime = None,
        end_time: datetime = None,
        limit: int = 100
    ) -> List[LogEntry]:
        """Execute LogQL query across clusters."""

    async def tail(
        self,
        query: str,
        cluster_ids: List[UUID] = None
    ) -> AsyncIterator[LogEntry]:
        """Tail logs in real-time."""

    async def get_labels(
        self,
        cluster_ids: List[UUID] = None
    ) -> Dict[UUID, List[str]]:
        """Get log label names."""
```

### 5.4 AlertsService

```python
class AlertsService:
    async def list_alerts(
        self,
        cluster_ids: List[UUID] = None,
        state: str = None,  # FIRING, RESOLVED, PENDING
        severity: str = None
    ) -> List[Alert]:
        """List alerts from clusters."""

    async def get_alert(
        self,
        fingerprint: str
    ) -> Alert:
        """Get specific alert by fingerprint."""

    async def receive_webhook(
        self,
        payload: AlertmanagerWebhook
    ) -> None:
        """Receive alert from Alertmanager webhook."""

    async def subscribe(
        self,
        cluster_ids: List[UUID] = None,
        severity: List[str] = None
    ) -> AsyncIterator[Alert]:
        """Subscribe to alert events."""
```

### 5.5 GPUService

```python
class GPUService:
    async def get_nodes(
        self,
        cluster_ids: List[UUID] = None
    ) -> List[GPUNode]:
        """Get GPU nodes from clusters."""

    async def get_gpu_details(
        self,
        cluster_id: UUID,
        node_name: str
    ) -> GPUNode:
        """Get detailed GPU info for specific node."""

    async def get_summary(self) -> GPUSummary:
        """Get fleet-wide GPU summary."""

    async def get_processes(
        self,
        cluster_ids: List[UUID] = None
    ) -> List[GPUProcess]:
        """Get running GPU processes."""
```

### 5.6 CNFService

```python
class CNFService:
    async def get_workloads(
        self,
        cluster_ids: List[UUID] = None
    ) -> List[CNFWorkload]:
        """Get CNF workloads from clusters."""

    async def get_ptp_status(
        self,
        cluster_ids: List[UUID] = None
    ) -> List[PTPStatus]:
        """Get PTP synchronization status."""

    async def get_dpdk_stats(
        self,
        cluster_id: UUID,
        pod_name: str
    ) -> DPDKStats:
        """Get DPDK statistics for pod."""

    async def get_sriov_status(
        self,
        cluster_ids: List[UUID] = None
    ) -> List[SRIOVStatus]:
        """Get SR-IOV VF allocation status."""
```

---

## 6. Collector Implementations

### 6.1 Prometheus Collector

```python
class PrometheusCollector:
    """
    Handles communication with Prometheus/Thanos endpoints.
    """

    def __init__(self, cluster_registry: ClusterRegistry):
        self.cluster_registry = cluster_registry

    async def query(
        self,
        cluster_id: UUID,
        query: str,
        time: datetime = None
    ) -> MetricResult:
        """Execute instant query on single cluster."""

        cluster = await self.cluster_registry.get(cluster_id)
        credentials = await self.cluster_registry.get_credentials(cluster_id)

        url = f"{cluster.endpoints.prometheus_url}/api/v1/query"
        params = {"query": query}
        if time:
            params["time"] = time.isoformat()

        headers = {"Authorization": f"Bearer {credentials.prometheus_token}"}

        # Execute with timeout and retry
        response = await self._request(url, params, headers)
        return self._parse_response(cluster_id, response)

    async def query_parallel(
        self,
        cluster_ids: List[UUID],
        query: str,
        **kwargs
    ) -> List[MetricResult]:
        """Execute query on multiple clusters in parallel."""

        tasks = [
            self.query(cluster_id, query, **kwargs)
            for cluster_id in cluster_ids
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return self._handle_results(cluster_ids, results)
```

### 6.2 GPU Collector (nvidia-smi via K8s exec)

```python
class GPUCollector:
    """
    Collects GPU telemetry via kubectl exec nvidia-smi.
    """

    NVIDIA_SMI_CMD = [
        "nvidia-smi",
        "--query-gpu=index,uuid,name,driver_version,memory.total,memory.used,memory.free,utilization.gpu,utilization.memory,temperature.gpu,power.draw,power.limit,fan.speed",
        "--format=csv,noheader,nounits"
    ]

    NVIDIA_SMI_PROCESSES_CMD = [
        "nvidia-smi",
        "--query-compute-apps=pid,process_name,used_memory",
        "--format=csv,noheader,nounits"
    ]

    async def collect_from_node(
        self,
        cluster_id: UUID,
        node_name: str
    ) -> GPUNode:
        """Collect GPU data from specific node."""

        # Find nvidia-driver-daemonset pod on node
        pod = await self._find_nvidia_pod(cluster_id, node_name)

        # Execute nvidia-smi
        gpu_output = await self._exec_in_pod(
            cluster_id, pod, self.NVIDIA_SMI_CMD
        )
        proc_output = await self._exec_in_pod(
            cluster_id, pod, self.NVIDIA_SMI_PROCESSES_CMD
        )

        return self._parse_nvidia_output(
            cluster_id, node_name, gpu_output, proc_output
        )
```

### 6.3 Alertmanager Webhook Receiver

```python
class AlertmanagerWebhookReceiver:
    """
    Receives alerts via Alertmanager webhook.
    """

    async def handle_webhook(
        self,
        payload: AlertmanagerWebhookPayload,
        cluster_id: UUID  # Derived from webhook URL path
    ) -> None:
        """Process incoming alert webhook."""

        for alert_data in payload.alerts:
            alert = Alert(
                fingerprint=alert_data.fingerprint,
                cluster_id=cluster_id,
                alertname=alert_data.labels.get("alertname"),
                severity=alert_data.labels.get("severity", "WARNING").upper(),
                state="FIRING" if alert_data.status == "firing" else "RESOLVED",
                labels=alert_data.labels,
                annotations=alert_data.annotations,
                starts_at=alert_data.startsAt,
                ends_at=alert_data.endsAt,
                generator_url=alert_data.generatorURL
            )

            # Publish to event bus
            await self.event_service.publish(Event(
                event_type="ALERT_FIRED" if alert.state == "FIRING" else "ALERT_RESOLVED",
                cluster_id=cluster_id,
                payload=alert.dict()
            ))

            # Store in cache
            await self.cache.set(
                f"alert:{alert.fingerprint}",
                alert.json(),
                ttl=86400  # 24 hours
            )
```

---

## 7. Federation Strategy

### 7.1 Query Execution

```
Federated Query Flow:
─────────────────────

1. Request arrives at Observability Collector
   └── Parse query, extract cluster targets

2. If cluster_ids empty → query all online clusters
   └── Get cluster list from Cluster Registry

3. For each target cluster:
   └── Get credentials from Cluster Registry
   └── Execute query in parallel

4. Aggregate results
   └── Successful: Include in response
   └── Failed: Include error, mark partial
   └── Timeout: Include error, mark partial

5. Cache results (if cacheable)
   └── TTL based on query type

6. Return aggregated response
```

### 7.2 Result Aggregation

```python
class ResultAggregator:
    def aggregate_metrics(
        self,
        results: List[MetricResult]
    ) -> AggregatedMetricResult:
        """
        Aggregation strategies:
        - MERGE: Combine all series (default)
        - SUM: Sum values across clusters
        - AVG: Average values across clusters
        - MAX: Maximum value across clusters
        - MIN: Minimum value across clusters
        """
```

### 7.3 Caching Strategy

| Query Type | Cache TTL | Cache Key Pattern |
|------------|-----------|-------------------|
| Instant query | 30 seconds | `metrics:instant:{hash(query)}:{cluster_id}` |
| Range query (< 1h) | 60 seconds | `metrics:range:{hash(query)}:{cluster_id}:{start}:{end}` |
| Range query (> 1h) | 5 minutes | Same as above |
| Labels | 5 minutes | `metrics:labels:{cluster_id}` |
| GPU telemetry | 5 seconds | `gpu:{cluster_id}:{node_name}` |
| Active alerts | 10 seconds | `alerts:active:{cluster_id}` |

---

## 8. Events Emitted

| Event Type | Trigger | Payload |
|------------|---------|---------|
| `METRIC_UPDATE` | Significant metric change | `MetricEvent` |
| `ALERT_FIRED` | New alert firing | `Alert` |
| `ALERT_RESOLVED` | Alert resolved | `Alert` |
| `TRACE_RECEIVED` | New error trace | `TraceSummary` |
| `GPU_UPDATE` | GPU telemetry update | `GPUNode` |
| `ANOMALY_DETECTED` | Anomaly detection | `AnomalyDetection` |

---

## 9. Dependencies

### 9.1 Internal Dependencies

| Dependency | Purpose | Interface |
|------------|---------|-----------|
| Cluster Registry | Cluster info, credentials | REST API |
| Redis | Caching, event publishing | Redis client |

### 9.2 External Dependencies (per cluster)

| Dependency | Purpose | Optional |
|------------|---------|----------|
| Prometheus/Thanos | Metrics | Required |
| Tempo | Traces | Yes |
| Loki | Logs | Yes |
| Alertmanager | Alerts | Yes |
| K8s API | GPU exec | Required for GPU |

---

## 10. Configuration

```yaml
observability_collector:
  # Cluster Registry
  cluster_registry_url: "http://cluster-registry:8080"

  # Redis
  redis_url: "redis://redis:6379/0"

  # Query settings
  query:
    default_timeout_seconds: 30
    max_timeout_seconds: 300
    max_parallel_queries: 10
    retry_attempts: 3
    retry_delay_seconds: 1

  # GPU collection
  gpu:
    enabled: true
    collection_interval_seconds: 5
    nvidia_namespace: "nvidia-gpu-operator"
    nvidia_daemonset: "nvidia-driver-daemonset"

  # CNF collection
  cnf:
    enabled: true
    ptp_namespace: "openshift-ptp"
    sriov_namespace: "openshift-sriov-network-operator"

  # Caching
  cache:
    instant_query_ttl_seconds: 30
    range_query_ttl_seconds: 60
    labels_ttl_seconds: 300
    gpu_ttl_seconds: 5
    alerts_ttl_seconds: 10

  # Alertmanager webhook
  alertmanager_webhook:
    enabled: true
    path_prefix: "/api/v1/alerts/webhook"
```

---

## 11. Error Handling

| Error Code | HTTP Status | Description |
|------------|-------------|-------------|
| `CLUSTER_NOT_FOUND` | 404 | Target cluster not in registry |
| `CLUSTER_UNREACHABLE` | 503 | Cannot connect to cluster |
| `QUERY_TIMEOUT` | 504 | Query exceeded timeout |
| `INVALID_PROMQL` | 400 | Invalid PromQL syntax |
| `INVALID_LOGQL` | 400 | Invalid LogQL syntax |
| `PARTIAL_RESULTS` | 206 | Some clusters failed |
| `NO_GPU_NODES` | 404 | No GPU nodes in cluster |
| `TEMPO_NOT_AVAILABLE` | 503 | Tempo not configured for cluster |
| `LOKI_NOT_AVAILABLE` | 503 | Loki not configured for cluster |

---

## 12. Performance Considerations

1. **Parallel Execution**: All cross-cluster queries execute in parallel
2. **Connection Pooling**: Reuse HTTP connections per cluster
3. **Result Streaming**: Stream large result sets to reduce memory
4. **Query Optimization**: Push down aggregations to source when possible
5. **Selective Caching**: Cache based on query characteristics
6. **Circuit Breaker**: Disable failing clusters temporarily

---

## 13. Open Questions

1. **Query Federation**: Should we support Thanos global view instead of manual federation?
2. **GPU Collection Method**: nvidia-smi exec vs DCGM exporter metrics?
3. **Alert Deduplication**: How to handle same alert from multiple sources?
4. **Cross-Cluster Traces**: Support for traces spanning multiple clusters?
5. **CNF Metrics Standard**: Which CNF metrics are universally available?

---

## Next: [04-intelligence-engine.md](./04-intelligence-engine.md)
