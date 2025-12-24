# 04 - Intelligence Engine Service

## Document Info
| Field | Value |
|-------|-------|
| Version | 0.1.0 |
| Status | Draft |
| Last Updated | 2024-12-24 |

---

## 1. Purpose

The Intelligence Engine Service provides AI-powered analysis and interaction capabilities. It handles:

- Multi-provider LLM routing (local vLLM, Anthropic, OpenAI, Google)
- Domain expert personas for specialized knowledge
- Natural language chat with tool calling (MCP)
- Anomaly detection on metrics
- Root cause analysis correlation
- Report generation with AI summaries

---

## 2. Responsibilities

| Responsibility | Description |
|----------------|-------------|
| **LLM Routing** | Route requests to appropriate LLM provider |
| **Persona Management** | Manage and apply domain expert personas |
| **Chat Sessions** | Maintain conversation context and history |
| **Tool Execution** | Execute MCP tools and process results |
| **Anomaly Detection** | Detect anomalies in metric time series |
| **Root Cause Analysis** | Correlate signals for root cause identification |
| **Report Generation** | Generate AI-summarized reports |

---

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         INTELLIGENCE ENGINE SERVICE                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                           API Layer                                    │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │ │
│  │  │ Chat API     │  │ MCP Endpoint │  │ Analysis API │                  │ │
│  │  │ /chat/*      │  │ /mcp         │  │ /analysis/*  │                  │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                  │ │
│  │  ┌──────────────┐  ┌──────────────┐                                    │ │
│  │  │ Persona API  │  │ Report API   │                                    │ │
│  │  │ /personas/*  │  │ /reports/*   │                                    │ │
│  │  └──────────────┘  └──────────────┘                                    │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                      │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         Service Layer                                  │ │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐            │ │
│  │  │ ChatService    │  │ PersonaService │  │ ToolService    │            │ │
│  │  │                │  │                │  │                │            │ │
│  │  │ • send_message│   │ • list()       │  │ • list_tools() │            │ │
│  │  │ • stream()     │  │ • get()        │  │ • call_tool()  │            │ │
│  │  │ • get_session()│  │ • create()     │  │ • get_schema() │            │ │
│  │  └────────────────┘  └────────────────┘  └────────────────┘            │ │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐            │ │
│  │  │ AnomalyService │  │ RCAService     │  │ ReportService  │            │ │
│  │  │                │  │                │  │                │            │ │
│  │  │ • detect()     │  │ • analyze()    │  │ • generate()   │            │ │
│  │  │ • train()      │  │ • correlate()  │  │ • get()        │            │ │
│  │  │ • get_config() │  │ • explain()    │  │ • list()       │            │ │
│  │  └────────────────┘  └────────────────┘  └────────────────┘            │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                      │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         LLM Layer                                      │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐  │ │
│  │  │                      LLM Router                                  │  │ │
│  │  │                                                                  │  │ │
│  │  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐              │  │ │
│  │  │  │  vLLM   │  │Anthropic│  │ OpenAI  │  │ Google  │              │  │ │
│  │  │  │ (Local) │  │ Claude  │  │  GPT    │  │ Gemini  │              │  │ │
│  │  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘              │  │ │
│  │  └──────────────────────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                      │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                        Data Layer                                      │ │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │ │
│  │  │ PostgreSQL       │  │ Redis            │  │ Object Store         │  │ │
│  │  │ (Sessions,       │  │ (Session Cache,  │  │ (Reports,            │  │ │
│  │  │  Personas)       │  │  Tool Results)   │  │  Attachments)        │  │ │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    ▼                                   ▼
          ┌─────────────────┐                 ┌─────────────────┐
          │ Observability   │                 │ Cluster         │
          │ Collector       │                 │ Registry        │
          │ (Tool Calls)    │                 │ (Context)       │
          └─────────────────┘                 └─────────────────┘
```

---

## 4. API Specification

### 4.1 Chat API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/chat/sessions` | Create new chat session |
| `GET` | `/api/v1/chat/sessions` | List user's sessions |
| `GET` | `/api/v1/chat/sessions/{id}` | Get session details |
| `DELETE` | `/api/v1/chat/sessions/{id}` | Delete session |
| `POST` | `/api/v1/chat/sessions/{id}/messages` | Send message |
| `GET` | `/api/v1/chat/sessions/{id}/messages` | Get session messages |
| `POST` | `/api/v1/chat/sessions/{id}/stream` | Stream message (SSE) |

### 4.2 MCP Endpoint

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/mcp` | MCP Streamable HTTP endpoint |
| `GET` | `/mcp/sse` | MCP SSE endpoint (subscribe) |
| `POST` | `/mcp/sse/message` | MCP SSE message endpoint |

### 4.3 Persona API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/personas` | List available personas |
| `GET` | `/api/v1/personas/{id}` | Get persona details |
| `POST` | `/api/v1/personas` | Create custom persona |
| `PUT` | `/api/v1/personas/{id}` | Update custom persona |
| `DELETE` | `/api/v1/personas/{id}` | Delete custom persona |

### 4.4 Analysis API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/analysis/anomaly` | Detect anomalies in metrics |
| `POST` | `/api/v1/analysis/rca` | Perform root cause analysis |
| `POST` | `/api/v1/analysis/explain` | Get AI explanation of data |

### 4.5 Report API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/reports` | Generate report |
| `GET` | `/api/v1/reports` | List reports |
| `GET` | `/api/v1/reports/{id}` | Get report |
| `GET` | `/api/v1/reports/{id}/download` | Download report file |
| `DELETE` | `/api/v1/reports/{id}` | Delete report |

---

### 4.6 Request/Response Examples

#### Create Chat Session

**Request:**
```http
POST /api/v1/chat/sessions
Content-Type: application/json

{
  "title": "GPU Performance Investigation",
  "persona_id": "gpu-expert",
  "cluster_context": [
    "550e8400-e29b-41d4-a716-446655440000"
  ],
  "model": "meta-llama/Llama-3.2-3B-Instruct"
}
```

**Response:**
```http
HTTP/1.1 201 Created
Content-Type: application/json

{
  "id": "880e8400-e29b-41d4-a716-446655440003",
  "title": "GPU Performance Investigation",
  "persona_id": "gpu-expert",
  "cluster_context": [
    "550e8400-e29b-41d4-a716-446655440000"
  ],
  "model": "meta-llama/Llama-3.2-3B-Instruct",
  "message_count": 0,
  "created_at": "2024-12-24T10:00:00Z",
  "expires_at": "2024-12-25T10:00:00Z"
}
```

#### Send Message (Non-Streaming)

**Request:**
```http
POST /api/v1/chat/sessions/880e8400-e29b-41d4-a716-446655440003/messages
Content-Type: application/json

{
  "content": "What's the current GPU utilization across all nodes?"
}
```

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "id": "990e8400-e29b-41d4-a716-446655440004",
  "session_id": "880e8400-e29b-41d4-a716-446655440003",
  "role": "ASSISTANT",
  "content": "Based on the current GPU metrics from cluster prod-east-1, here's the utilization summary:\n\n| Node | GPU | Utilization | Memory | Temp |\n|------|-----|------------|--------|------|\n| worker-gpu-01 | A100 #0 | 78% | 55% | 62°C |\n| worker-gpu-01 | A100 #1 | 65% | 48% | 58°C |\n| worker-gpu-02 | A100 #0 | 92% | 89% | 71°C |\n\n**Observation**: GPU #0 on worker-gpu-02 shows high utilization (92%) and elevated temperature (71°C). The memory usage is also high at 89%. This could indicate a memory-intensive workload that may benefit from optimization.",
  "tool_calls": [
    {
      "id": "call_001",
      "name": "get_gpu_nodes",
      "arguments": {
        "cluster_ids": ["550e8400-e29b-41d4-a716-446655440000"]
      }
    }
  ],
  "tool_results": [
    {
      "tool_call_id": "call_001",
      "status": "SUCCESS",
      "result": { "nodes": [...] }
    }
  ],
  "model": "meta-llama/Llama-3.2-3B-Instruct",
  "tokens_used": 847,
  "latency_ms": 1250,
  "created_at": "2024-12-24T10:01:15Z"
}
```

#### Stream Message (SSE)

**Request:**
```http
POST /api/v1/chat/sessions/880e8400-e29b-41d4-a716-446655440003/stream
Content-Type: application/json

{
  "content": "Analyze the memory usage trend over the last hour"
}
```

**Response (SSE):**
```
event: message_start
data: {"id": "msg_001", "role": "ASSISTANT"}

event: tool_use
data: {"tool_call_id": "call_002", "name": "query_metrics", "arguments": {...}}

event: tool_result
data: {"tool_call_id": "call_002", "status": "SUCCESS"}

event: content_delta
data: {"delta": "Based on the metrics "}

event: content_delta
data: {"delta": "from the last hour, I can see..."}

event: message_complete
data: {"tokens_used": 623, "latency_ms": 890}
```

#### List Personas

**Request:**
```http
GET /api/v1/personas
```

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "personas": [
    {
      "id": "default",
      "name": "Default Assistant",
      "description": "General-purpose AI assistant for platform operations",
      "capabilities": ["query_metrics", "search_traces", "list_alerts", "get_gpu_nodes"],
      "icon": "robot",
      "is_builtin": true
    },
    {
      "id": "platform-ops",
      "name": "Platform Operations Expert",
      "description": "Specialized in OpenShift platform operations, upgrades, and troubleshooting",
      "capabilities": ["query_metrics", "search_traces", "query_logs", "list_alerts"],
      "icon": "server",
      "is_builtin": true
    },
    {
      "id": "gpu-expert",
      "name": "GPU Infrastructure Expert",
      "description": "Specialized in GPU workloads, CUDA optimization, and vLLM performance",
      "capabilities": ["get_gpu_nodes", "get_gpu_processes", "query_metrics"],
      "icon": "gpu",
      "is_builtin": true
    },
    {
      "id": "network-cnf",
      "name": "Network & CNF Expert",
      "description": "Specialized in CNF workloads, 5G RAN, SR-IOV, and PTP",
      "capabilities": ["get_cnf_workloads", "get_ptp_status", "get_dpdk_stats", "query_metrics"],
      "icon": "network",
      "is_builtin": true
    },
    {
      "id": "telco-5g",
      "name": "Telco 5G Specialist",
      "description": "Deep expertise in 5G/6G architecture, O-RAN, and telco operations",
      "capabilities": ["get_cnf_workloads", "query_metrics", "search_traces"],
      "icon": "signal",
      "is_builtin": true
    }
  ]
}
```

#### Anomaly Detection

**Request:**
```http
POST /api/v1/analysis/anomaly
Content-Type: application/json

{
  "cluster_ids": ["550e8400-e29b-41d4-a716-446655440000"],
  "metric_query": "sum(rate(container_cpu_usage_seconds_total[5m])) by (namespace)",
  "time_range": {
    "start": "2024-12-24T00:00:00Z",
    "end": "2024-12-24T12:00:00Z"
  },
  "detection_method": "STATISTICAL",
  "sensitivity": "MEDIUM"
}
```

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "anomalies": [
    {
      "id": "aa0e8400-e29b-41d4-a716-446655440005",
      "cluster_id": "550e8400-e29b-41d4-a716-446655440000",
      "metric_name": "container_cpu_usage_seconds_total",
      "labels": {
        "namespace": "production"
      },
      "detection_type": "STATISTICAL",
      "severity": "MEDIUM",
      "confidence_score": 0.87,
      "anomaly_type": "SPIKE",
      "expected_value": 0.45,
      "actual_value": 0.92,
      "deviation_percent": 104.4,
      "explanation": "CPU usage spiked from expected 45% to 92% at 09:15 UTC. This represents a 104% increase from the baseline, exceeding 2.5 standard deviations.",
      "detected_at": "2024-12-24T09:15:00Z"
    }
  ],
  "summary": {
    "total_anomalies": 1,
    "by_severity": {
      "HIGH": 0,
      "MEDIUM": 1,
      "LOW": 0
    },
    "time_range_analyzed": "12h"
  }
}
```

---

## 5. Built-in Personas

### 5.1 Persona Definitions

```yaml
personas:
  - id: default
    name: Default Assistant
    description: General-purpose AI assistant for platform operations
    system_prompt: |
      You are an AI assistant specialized in OpenShift and Kubernetes platform operations.
      You have access to observability tools to query metrics, traces, logs, and alerts.

      Guidelines:
      - Always verify data before making conclusions
      - Provide specific, actionable recommendations
      - Use tables and formatting for clarity
      - Cite specific metric values and timestamps
      - When unsure, suggest additional queries to gather more data
    capabilities:
      - query_metrics
      - search_traces
      - query_logs
      - list_alerts
      - get_gpu_nodes
      - list_clusters

  - id: platform-ops
    name: Platform Operations Expert
    description: Specialized in OpenShift platform operations, upgrades, and troubleshooting
    system_prompt: |
      You are a senior Platform Operations engineer with 15+ years of experience in
      enterprise Kubernetes and OpenShift deployments.

      Your expertise includes:
      - OpenShift cluster lifecycle (installation, upgrades, maintenance)
      - Resource management and capacity planning
      - Performance troubleshooting and optimization
      - Security hardening and compliance
      - Disaster recovery and high availability

      When analyzing issues:
      1. First gather relevant metrics and logs
      2. Look for correlations across signals
      3. Consider recent changes or deployments
      4. Provide root cause analysis with confidence levels
      5. Suggest remediation steps with rollback plans
    capabilities:
      - query_metrics
      - search_traces
      - query_logs
      - list_alerts
      - list_clusters
      - get_cluster_status

  - id: gpu-expert
    name: GPU Infrastructure Expert
    description: Specialized in GPU workloads, CUDA optimization, and vLLM performance
    system_prompt: |
      You are a GPU infrastructure specialist with deep expertise in:
      - NVIDIA GPU architecture and optimization
      - CUDA programming and performance tuning
      - vLLM and LLM inference optimization
      - GPU memory management and multi-GPU scaling
      - DCGM metrics interpretation
      - Container GPU scheduling on Kubernetes

      When analyzing GPU performance:
      1. Check utilization, memory, temperature, and power metrics
      2. Identify bottlenecks (compute-bound vs memory-bound)
      3. Look for thermal throttling indicators
      4. Analyze process-level GPU consumption
      5. Recommend batch size and model parallelism optimizations
    capabilities:
      - get_gpu_nodes
      - get_gpu_processes
      - get_gpu_summary
      - query_metrics
      - list_clusters

  - id: network-cnf
    name: Network & CNF Expert
    description: Specialized in CNF workloads, 5G RAN, SR-IOV, and PTP
    system_prompt: |
      You are a Cloud-Native Network Functions (CNF) specialist with expertise in:
      - 5G RAN components (vDU, vCU, UPF)
      - SR-IOV and DPDK optimization
      - PTP (Precision Time Protocol) synchronization
      - Network performance and latency optimization
      - O-RAN architecture and interfaces

      When analyzing CNF performance:
      1. Check PTP sync status and accuracy
      2. Analyze SR-IOV VF allocation and usage
      3. Review DPDK statistics for packet processing
      4. Monitor latency-critical metrics
      5. Correlate with underlying infrastructure metrics
    capabilities:
      - get_cnf_workloads
      - get_ptp_status
      - get_dpdk_stats
      - get_sriov_status
      - query_metrics
      - search_traces

  - id: telco-5g
    name: Telco 5G Specialist
    description: Deep expertise in 5G/6G architecture, O-RAN, and telco operations
    system_prompt: |
      You are a telecommunications expert with 20+ years in network architecture:
      - 5G NR and core network architecture
      - O-RAN specifications and deployment
      - Network slicing and QoS management
      - Carrier-grade reliability requirements
      - 3GPP standards and compliance

      Approach problems from a telco operations perspective:
      1. Consider SLA and availability requirements
      2. Focus on latency-critical paths
      3. Analyze from both RAN and core perspectives
      4. Consider regulatory and compliance implications
      5. Provide capacity planning recommendations
    capabilities:
      - get_cnf_workloads
      - query_metrics
      - search_traces
      - query_logs
      - list_alerts
```

---

## 6. MCP Tool Definitions

### 6.1 Available Tools

```yaml
tools:
  # Cluster Tools
  - name: list_clusters
    description: List all managed clusters with their status
    parameters:
      type: object
      properties:
        environment:
          type: string
          enum: [PRODUCTION, STAGING, DEVELOPMENT, LAB]
        cluster_type:
          type: string
          enum: [HUB, SPOKE, EDGE, FAR_EDGE]
        state:
          type: string
          enum: [ONLINE, OFFLINE, DEGRADED]

  - name: get_cluster_status
    description: Get detailed status of a specific cluster
    parameters:
      type: object
      required: [cluster_id]
      properties:
        cluster_id:
          type: string
          format: uuid

  # Metrics Tools
  - name: query_metrics
    description: Execute PromQL query across clusters
    parameters:
      type: object
      required: [query]
      properties:
        query:
          type: string
          description: PromQL query
        cluster_ids:
          type: array
          items:
            type: string
            format: uuid
        start_time:
          type: string
          format: date-time
        end_time:
          type: string
          format: date-time
        step:
          type: string
          default: "1m"

  - name: get_metric_labels
    description: Get available label values for filtering
    parameters:
      type: object
      required: [label_name]
      properties:
        label_name:
          type: string
        cluster_ids:
          type: array
          items:
            type: string
            format: uuid

  # Trace Tools
  - name: search_traces
    description: Search for traces matching criteria
    parameters:
      type: object
      properties:
        service_name:
          type: string
        operation_name:
          type: string
        min_duration_ms:
          type: integer
        max_duration_ms:
          type: integer
        tags:
          type: object
        cluster_ids:
          type: array
          items:
            type: string
            format: uuid
        limit:
          type: integer
          default: 20

  - name: get_trace
    description: Get detailed trace by ID
    parameters:
      type: object
      required: [trace_id]
      properties:
        trace_id:
          type: string

  # Log Tools
  - name: query_logs
    description: Execute LogQL query across clusters
    parameters:
      type: object
      required: [query]
      properties:
        query:
          type: string
          description: LogQL query
        cluster_ids:
          type: array
          items:
            type: string
            format: uuid
        start_time:
          type: string
          format: date-time
        end_time:
          type: string
          format: date-time
        limit:
          type: integer
          default: 100

  # Alert Tools
  - name: list_alerts
    description: List active alerts across clusters
    parameters:
      type: object
      properties:
        cluster_ids:
          type: array
          items:
            type: string
            format: uuid
        state:
          type: string
          enum: [FIRING, RESOLVED, PENDING]
        severity:
          type: string
          enum: [CRITICAL, WARNING, INFO]

  # GPU Tools
  - name: get_gpu_nodes
    description: Get GPU nodes and their metrics
    parameters:
      type: object
      properties:
        cluster_ids:
          type: array
          items:
            type: string
            format: uuid

  - name: get_gpu_processes
    description: Get running GPU processes
    parameters:
      type: object
      properties:
        cluster_ids:
          type: array
          items:
            type: string
            format: uuid

  - name: get_gpu_summary
    description: Get fleet-wide GPU utilization summary
    parameters:
      type: object
      properties: {}

  # CNF Tools
  - name: get_cnf_workloads
    description: Get CNF workloads across clusters
    parameters:
      type: object
      properties:
        cluster_ids:
          type: array
          items:
            type: string
            format: uuid
        cnf_type:
          type: string
          enum: [VDU, VCU, UPF, AMF, SMF]

  - name: get_ptp_status
    description: Get PTP synchronization status
    parameters:
      type: object
      properties:
        cluster_ids:
          type: array
          items:
            type: string
            format: uuid

  - name: get_dpdk_stats
    description: Get DPDK statistics for a pod
    parameters:
      type: object
      required: [cluster_id, pod_name]
      properties:
        cluster_id:
          type: string
          format: uuid
        pod_name:
          type: string

  - name: get_sriov_status
    description: Get SR-IOV VF allocation status
    parameters:
      type: object
      properties:
        cluster_ids:
          type: array
          items:
            type: string
            format: uuid
```

---

## 7. LLM Router

### 7.1 Provider Selection

```python
class LLMRouter:
    """Routes requests to appropriate LLM provider."""

    PROVIDER_PATTERNS = {
        "anthropic": ["anthropic/", "claude"],
        "openai": ["openai/", "gpt-", "o1-"],
        "google": ["google/", "gemini"],
        "local": ["meta-llama/", "llama", "mistral", "qwen"]
    }

    def __init__(self, config: LLMConfig):
        self.providers = {
            "anthropic": AnthropicProvider(config.anthropic),
            "openai": OpenAIProvider(config.openai),
            "google": GoogleProvider(config.google),
            "local": LocalVLLMProvider(config.local_vllm)
        }
        self.default_provider = config.default_provider

    def get_provider(self, model_name: str) -> LLMProvider:
        """Determine provider from model name."""
        model_lower = model_name.lower()
        for provider, patterns in self.PROVIDER_PATTERNS.items():
            if any(p in model_lower for p in patterns):
                return self.providers[provider]
        return self.providers[self.default_provider]
```

### 7.2 Provider Interface

```python
class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def chat(
        self,
        messages: List[ChatMessage],
        tools: List[Tool] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> ChatResponse:
        """Send chat request."""

    @abstractmethod
    async def stream(
        self,
        messages: List[ChatMessage],
        tools: List[Tool] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> AsyncIterator[ChatChunk]:
        """Stream chat response."""
```

### 7.3 Fallback Strategy

```
Primary Provider (configured model)
         │
         ▼ (on failure)
Fallback Provider 1 (local vLLM)
         │
         ▼ (on failure)
Fallback Provider 2 (alternative model)
         │
         ▼ (on failure)
Error Response with graceful degradation
```

---

## 8. Anomaly Detection

### 8.1 Detection Methods

```python
class AnomalyDetector:
    """Multi-method anomaly detection."""

    async def detect(
        self,
        metrics: List[MetricSeries],
        method: DetectionMethod,
        sensitivity: Sensitivity
    ) -> List[AnomalyDetection]:
        """
        Detection methods:

        STATISTICAL:
        - Z-score analysis
        - Modified Z-score (MAD-based)
        - IQR-based outlier detection

        ML_BASED:
        - Isolation Forest
        - LSTM Autoencoder
        - Prophet forecasting

        LLM_ASSISTED:
        - Pattern description to LLM
        - LLM identifies unusual patterns
        - Higher accuracy, lower throughput
        """
```

### 8.2 Sensitivity Levels

| Level | Z-Score Threshold | Description |
|-------|-------------------|-------------|
| LOW | 3.0 | Only extreme outliers |
| MEDIUM | 2.5 | Balanced detection |
| HIGH | 2.0 | More sensitive, more alerts |
| EXTREME | 1.5 | Very sensitive, many alerts |

---

## 9. Root Cause Analysis

### 9.1 RCA Service

```python
class RCAService:
    """Root cause analysis using signal correlation."""

    async def analyze(
        self,
        trigger: Alert | AnomalyDetection,
        time_window: timedelta = timedelta(hours=1)
    ) -> RCAResult:
        """
        RCA Process:

        1. Collect related signals:
           - Metrics from same namespace/pod
           - Traces with errors in time window
           - Logs with error patterns
           - Other alerts in time window

        2. Build correlation graph:
           - Temporal correlation
           - Causal relationships
           - Service dependencies

        3. Identify probable causes:
           - Score by correlation strength
           - Consider known patterns
           - Rank by likelihood

        4. Generate explanation:
           - Use LLM to explain findings
           - Suggest remediation steps
        """

    async def correlate_signals(
        self,
        signals: List[Signal],
        method: CorrelationMethod
    ) -> CorrelationGraph:
        """Build correlation graph from signals."""
```

### 9.2 Integration with Korrel8r

```python
class Korrel8rIntegration:
    """Optional Korrel8r integration for enhanced correlation."""

    async def get_related_signals(
        self,
        start_signal: Signal
    ) -> List[RelatedSignal]:
        """Query Korrel8r for related signals."""

    async def get_signal_graph(
        self,
        signals: List[Signal]
    ) -> SignalGraph:
        """Build signal relationship graph via Korrel8r."""
```

---

## 10. Events Emitted

| Event Type | Trigger | Payload |
|------------|---------|---------|
| `CHAT_MESSAGE` | New message in session | `ChatMessage` |
| `ANOMALY_DETECTED` | Anomaly detection complete | `AnomalyDetection` |
| `RCA_COMPLETE` | RCA analysis complete | `RCAResult` |
| `REPORT_GENERATED` | Report generation complete | `Report` |

---

## 11. Dependencies

### 11.1 Internal Dependencies

| Dependency | Purpose | Interface |
|------------|---------|-----------|
| Observability Collector | Tool execution | REST API |
| Cluster Registry | Cluster context | REST API |
| Redis | Session cache, events | Redis client |
| PostgreSQL | Session persistence | SQLAlchemy |
| Object Store | Report storage | S3 API |

### 11.2 External Dependencies

| Dependency | Purpose | Optional |
|------------|---------|----------|
| vLLM Endpoint | Local LLM inference | No (default) |
| Anthropic API | Claude models | Yes |
| OpenAI API | GPT models | Yes |
| Google AI API | Gemini models | Yes |
| Korrel8r | Signal correlation | Yes |

---

## 12. Configuration

```yaml
intelligence_engine:
  # Service dependencies
  observability_collector_url: "http://observability-collector:8080"
  cluster_registry_url: "http://cluster-registry:8080"
  redis_url: "redis://redis:6379/0"
  database_url: "postgresql://user:pass@postgres:5432/aiops"
  object_store_url: "http://minio:9000"

  # LLM Configuration
  llm:
    default_provider: "local"
    default_model: "meta-llama/Llama-3.2-3B-Instruct"

    local_vllm:
      url: "http://vllm:8080/v1"
      timeout_seconds: 120

    anthropic:
      api_key_secret: "anthropic-api-key"
      default_model: "claude-3-5-sonnet-20241022"

    openai:
      api_key_secret: "openai-api-key"
      default_model: "gpt-4o"

    google:
      api_key_secret: "google-ai-key"
      default_model: "gemini-1.5-pro"

  # Chat settings
  chat:
    max_tokens: 4096
    temperature: 0.7
    session_ttl_hours: 24
    max_messages_per_session: 100
    stream_chunk_size: 50

  # Anomaly detection
  anomaly:
    default_method: "STATISTICAL"
    default_sensitivity: "MEDIUM"
    lookback_hours: 24
    min_data_points: 10

  # RCA settings
  rca:
    time_window_hours: 1
    max_related_signals: 50
    korrel8r_enabled: true
    korrel8r_url: "http://korrel8r:8080"

  # Report settings
  reports:
    storage_bucket: "aiops-reports"
    retention_days: 90
    formats: ["HTML", "PDF", "MARKDOWN"]
```

---

## 13. Error Handling

| Error Code | HTTP Status | Description |
|------------|-------------|-------------|
| `SESSION_NOT_FOUND` | 404 | Chat session not found |
| `SESSION_EXPIRED` | 410 | Chat session has expired |
| `PERSONA_NOT_FOUND` | 404 | Persona not found |
| `PERSONA_READONLY` | 403 | Cannot modify built-in persona |
| `MODEL_NOT_AVAILABLE` | 503 | LLM model not available |
| `TOOL_EXECUTION_FAILED` | 500 | Tool call failed |
| `RATE_LIMITED` | 429 | Too many requests |
| `CONTEXT_TOO_LARGE` | 400 | Message context exceeds limit |
| `ANOMALY_DETECTION_FAILED` | 500 | Anomaly detection failed |

---

## 14. Open Questions

1. **Model Selection UI**: Should users be able to switch models mid-session?
2. **Persona Inheritance**: Should custom personas extend built-in ones?
3. **Tool Permissions**: Should tool access be configurable per persona?
4. **Streaming vs Batch**: Default behavior for anomaly detection?
5. **Report Scheduling**: Support for scheduled report generation?

---

## Next: [05-realtime-streaming.md](./05-realtime-streaming.md)
