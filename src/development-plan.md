# AIOps NextGen MVP Development Plan

## Overview

This plan breaks implementation into 6 phases, each delivering working functionality that subsequent phases extend without rewriting. Each phase produces a deployable increment.

**Key Principles:**
- Each phase is independently deployable and testable
- Later phases add capabilities; they don't replace earlier work
- Shared infrastructure built once in Phase 1
- API contracts defined upfront, implementation evolves

---

## Phase 1: Foundation & Data Layer

**Goal:** Establish shared infrastructure, project structure, and a working skeleton

**Deliverables:**
- Project scaffolding for all services
- PostgreSQL with schemas for clusters and intelligence
- Redis configured with all 4 databases
- Docker Compose for local development
- Basic CI pipeline (lint, test, build)
- Health check endpoints for all services

### 1.1 Project Structure
```
src/
├── shared/                      # Shared Python package
│   ├── models/                  # Pydantic models from spec 01
│   ├── database/                # SQLAlchemy base, session management
│   ├── redis_client/            # Redis connection, pub/sub helpers
│   ├── config/                  # Settings management (pydantic-settings)
│   └── observability/           # OpenTelemetry setup, logging
├── cluster-registry/
├── observability-collector/
├── intelligence-engine/
├── realtime-streaming/
├── api-gateway/
└── frontend/
```

### 1.2 Shared Components (Build Once)
| Component | Implementation | Used By |
|-----------|---------------|---------|
| Pydantic models | From `specs/01-data-models.md` | All services |
| Database session | SQLAlchemy async | cluster-registry, intelligence-engine |
| Redis client | aioredis with connection pool | All services |
| Config loader | pydantic-settings + env vars | All services |
| Logging | structlog JSON format | All services |
| Tracing | OpenTelemetry SDK | All services |
| Health endpoints | `/health`, `/ready` pattern | All services |

### 1.3 Database Setup
```sql
-- Single database, multiple schemas
CREATE DATABASE aiops;

-- Cluster Registry owns this schema
CREATE SCHEMA clusters;

-- Intelligence Engine owns this schema
CREATE SCHEMA intelligence;
```

### 1.4 Local Development Stack
```yaml
# docker-compose.yml
services:
  postgresql:
    image: postgres:15
    environment:
      POSTGRES_DB: aiops
      POSTGRES_USER: aiops
    ports: ["5432:5432"]
    volumes: ["./init.sql:/docker-entrypoint-initdb.d/init.sql"]

  redis:
    image: redis:7
    ports: ["6379:6379"]

  # Each service added as implemented
```

### 1.5 Tasks
- [ ] Create monorepo structure with shared package
- [ ] Define all Pydantic models from spec 01
- [ ] Create SQLAlchemy models for clusters schema
- [ ] Create SQLAlchemy models for intelligence schema
- [ ] Implement Redis client wrapper with pub/sub support
- [ ] Implement config management with validation
- [ ] Set up structured logging
- [ ] Create docker-compose.yml with PostgreSQL + Redis
- [ ] Create database migration scripts (Alembic)
- [ ] Set up pytest infrastructure
- [ ] Create GitHub Actions CI pipeline

**Exit Criteria:** `docker-compose up` starts PostgreSQL and Redis; shared package importable by all services; all models validate.

---

## Phase 2: Cluster Registry (Core CRUD)

**Goal:** Working cluster management API - the foundation other services depend on

**Deliverables:**
- Full CRUD for clusters
- Credential storage in Kubernetes Secrets (mocked locally)
- Basic health check polling
- Event publishing to Redis
- OpenAPI documentation

### 2.1 API Endpoints
| Priority | Endpoint | Description |
|----------|----------|-------------|
| P0 | `POST /api/v1/clusters` | Register cluster |
| P0 | `GET /api/v1/clusters` | List clusters with filtering |
| P0 | `GET /api/v1/clusters/{id}` | Get single cluster |
| P0 | `PUT /api/v1/clusters/{id}` | Update cluster |
| P0 | `DELETE /api/v1/clusters/{id}` | Delete cluster |
| P1 | `GET /api/v1/clusters/{id}/status` | Get cluster status |
| P1 | `POST /api/v1/clusters/{id}/credentials` | Upload credentials |
| P1 | `GET /api/v1/fleet/summary` | Fleet summary stats |
| P2 | `POST /api/v1/clusters/{id}/refresh` | Force refresh |

### 2.2 Services to Implement
```python
# Core services
ClusterService        # CRUD operations
CredentialService     # Store/retrieve credentials (K8s Secrets or local mock)
HealthService         # Background health checker
EventService          # Publish to Redis

# Background tasks
health_check_task     # Periodic polling of registered clusters
```

### 2.3 Event Publishing
```python
# Events emitted (consumed by Phase 5)
CLUSTER_REGISTERED
CLUSTER_UPDATED
CLUSTER_DELETED
CLUSTER_STATUS_CHANGED
```

### 2.4 Tasks
- [ ] Create FastAPI application scaffold
- [ ] Implement ClusterService with CRUD
- [ ] Implement database repository pattern
- [ ] Add query filtering (environment, cluster_type, has_gpu, labels)
- [ ] Add pagination support
- [ ] Implement CredentialService (local file mock for dev)
- [ ] Implement basic HealthService (ping API server)
- [ ] Implement EventService publishing to Redis
- [ ] Add OpenAPI documentation
- [ ] Write unit tests (>80% coverage)
- [ ] Write integration tests with test database
- [ ] Add to docker-compose

**Exit Criteria:** Can register, list, update, delete clusters via API; health status updates in background; events published to Redis.

---

## Phase 3: Observability Collector (Metrics Focus)

**Goal:** Federated Prometheus queries across registered clusters

**Deliverables:**
- PromQL query execution across multiple clusters
- Result aggregation and caching
- GPU telemetry collection (nvidia-smi)
- Alert webhook receiver

### 3.1 API Endpoints
| Priority | Endpoint | Description |
|----------|----------|-------------|
| P0 | `POST /api/v1/metrics/query` | Instant PromQL query |
| P0 | `POST /api/v1/metrics/query_range` | Range PromQL query |
| P1 | `GET /api/v1/metrics/labels` | Get label names |
| P1 | `GET /api/v1/alerts` | List active alerts |
| P1 | `POST /api/v1/alerts/webhook` | Alertmanager webhook |
| P1 | `GET /api/v1/gpu/nodes` | List GPU nodes |
| P2 | `GET /api/v1/gpu/summary` | Fleet GPU summary |

### 3.2 Collectors to Implement
```python
PrometheusCollector   # Query Prometheus/Thanos endpoints
AlertmanagerCollector # Receive webhook, poll alerts
GPUCollector          # Execute nvidia-smi via kubectl exec

# Support classes
ResultAggregator      # Merge results from multiple clusters
QueryCache            # Redis-based caching
```

### 3.3 Integration with Cluster Registry
```python
# Get cluster info and credentials
cluster = await cluster_registry_client.get_cluster(cluster_id)
credentials = await cluster_registry_client.get_credentials(cluster_id)

# Use credentials to query Prometheus
prometheus_url = cluster.endpoints.prometheus_url
token = credentials.prometheus_token
```

### 3.4 Tasks
- [ ] Create FastAPI application scaffold
- [ ] Implement Cluster Registry client
- [ ] Implement PrometheusCollector with parallel queries
- [ ] Implement ResultAggregator for multi-cluster results
- [ ] Implement QueryCache with Redis
- [ ] Implement AlertmanagerCollector (webhook receiver)
- [ ] Implement GPUCollector (kubectl exec nvidia-smi)
- [ ] Publish ALERT_FIRED, ALERT_RESOLVED, GPU_UPDATE events
- [ ] Write mock Prometheus for testing
- [ ] Write unit and integration tests
- [ ] Add to docker-compose

**Exit Criteria:** Can execute PromQL across registered clusters; GPU metrics collected; alerts received via webhook.

---

## Phase 4: Intelligence Engine (Chat MVP)

**Goal:** Working AI chat with tool calling and one persona

**Deliverables:**
- Chat session management
- Local vLLM integration
- MCP tool execution (metrics, alerts, GPU)
- Default persona working
- Streaming responses

### 4.1 API Endpoints
| Priority | Endpoint | Description |
|----------|----------|-------------|
| P0 | `POST /api/v1/chat/sessions` | Create session |
| P0 | `GET /api/v1/chat/sessions/{id}` | Get session |
| P0 | `POST /api/v1/chat/sessions/{id}/messages` | Send message |
| P0 | `POST /api/v1/chat/sessions/{id}/stream` | Stream response (SSE) |
| P1 | `GET /api/v1/personas` | List personas |
| P2 | `POST /api/v1/analysis/anomaly` | Anomaly detection |

### 4.2 Core Components
```python
ChatService           # Session management, message handling
LLMRouter             # Route to vLLM (single provider for air-gapped)
ToolService           # MCP tool registry and execution
PersonaService        # Load and apply personas

# MCP Tools (call Observability Collector)
query_metrics         # Execute PromQL
list_alerts           # Get active alerts
get_gpu_nodes         # Get GPU info
list_clusters         # Get clusters from registry
```

### 4.3 vLLM Integration
```python
class LocalVLLMProvider:
    """OpenAI-compatible client for local vLLM."""

    async def chat(self, messages, tools=None):
        # POST to vLLM /v1/chat/completions
        # Handle tool_calls in response
        # Execute tools via ToolService
        # Return final response
```

### 4.4 Tasks
- [ ] Create FastAPI application scaffold
- [ ] Implement ChatSession database models
- [ ] Implement ChatService with session management
- [ ] Implement LLMRouter for vLLM
- [ ] Implement ToolService with tool registry
- [ ] Implement MCP tools (query_metrics, list_alerts, get_gpu_nodes, list_clusters)
- [ ] Implement SSE streaming endpoint
- [ ] Add default persona with system prompt
- [ ] Create vLLM mock for testing
- [ ] Write unit and integration tests
- [ ] Add to docker-compose (with vLLM optional)

**Exit Criteria:** Can create chat session, send messages, receive AI responses with tool calls executed against Observability Collector.

---

## Phase 5: Real-Time Streaming & API Gateway

**Goal:** Unified API entry point and WebSocket-based live updates

**Deliverables:**
- API Gateway with routing to all services
- OpenShift OAuth integration (mockable)
- Rate limiting
- WebSocket hub with subscriptions
- Event routing from Redis to clients

### 5.1 API Gateway
```python
# Route table
/api/v1/clusters/*    → cluster-registry:8080
/api/v1/metrics/*     → observability-collector:8080
/api/v1/alerts/*      → observability-collector:8080
/api/v1/gpu/*         → observability-collector:8080
/api/v1/chat/*        → intelligence-engine:8080
/api/v1/personas/*    → intelligence-engine:8080
/ws                   → realtime-streaming:8080
```

### 5.2 Real-Time Streaming
```python
WebSocketHub          # Manage connections
SubscriptionManager   # Track client subscriptions
EventRouter           # Redis PubSub → WebSocket

# Supported subscriptions
CLUSTER_STATUS_CHANGED
ALERT_FIRED, ALERT_RESOLVED
GPU_UPDATE
ANOMALY_DETECTED
```

### 5.3 Tasks
- [ ] Create API Gateway FastAPI scaffold
- [ ] Implement request routing/proxying
- [ ] Implement OAuth middleware (with bypass for dev)
- [ ] Implement rate limiting with Redis
- [ ] Implement CORS middleware
- [ ] Aggregate OpenAPI specs from backends
- [ ] Create Real-Time Streaming FastAPI scaffold
- [ ] Implement WebSocketHub with connection management
- [ ] Implement SubscriptionManager
- [ ] Implement EventRouter (Redis → WebSocket)
- [ ] Handle authentication for WebSocket
- [ ] Implement heartbeat/keepalive
- [ ] Write unit and integration tests
- [ ] Update docker-compose

**Exit Criteria:** All API requests route through gateway; WebSocket clients receive real-time events; rate limiting works.

---

## Phase 6: Frontend MVP

**Goal:** Functional web UI for core workflows

**Deliverables:**
- Fleet dashboard with cluster status
- GPU monitoring page
- AI chat interface
- Basic alerts view

### 6.1 Pages (Priority Order)
| Priority | Page | Features |
|----------|------|----------|
| P0 | Dashboard | Fleet summary, cluster status grid, recent alerts |
| P0 | Chat | Session management, message input, streaming responses |
| P1 | GPU | Node list, GPU cards with metrics, real-time updates |
| P1 | Clusters | List, add, edit, delete clusters |
| P2 | Alerts | Active alerts list with filtering |
| P2 | Settings | Theme toggle |

### 6.2 Technical Stack
```
React 18 + TypeScript 5
Vite 5 (build)
Tailwind CSS 3 (styling)
Zustand 4 (state)
Axios (HTTP)
reconnecting-websocket (WebSocket)
```

### 6.3 Core Hooks
```typescript
useAuth()           // Authentication state
useWebSocket()      // WebSocket connection + subscriptions
useClusters()       // Cluster data + real-time updates
useGPU()            // GPU metrics + real-time updates
useAlerts()         // Alerts + real-time updates
useChat()           // Chat sessions + streaming
```

### 6.4 Tasks
- [ ] Create Vite + React + TypeScript scaffold
- [ ] Set up Tailwind CSS
- [ ] Create API client with Axios
- [ ] Implement Zustand stores (auth, clusters, alerts, gpu, chat)
- [ ] Implement useWebSocket hook
- [ ] Create layout components (Header, Sidebar, MainLayout)
- [ ] Create Dashboard page
- [ ] Create Chat page with streaming
- [ ] Create GPU monitoring page
- [ ] Create Clusters management page
- [ ] Create Alerts page
- [ ] Add dark mode support
- [ ] Write component tests
- [ ] Add Dockerfile with nginx
- [ ] Update docker-compose

**Exit Criteria:** Can view fleet status, manage clusters, chat with AI, monitor GPUs, see alerts - all via web UI.

---

## Phase Summary

| Phase | Duration | Dependencies | Key Deliverable |
|-------|----------|--------------|-----------------|
| 1. Foundation | 1 week | None | Shared infra, models, dev environment |
| 2. Cluster Registry | 1 week | Phase 1 | Working cluster management API |
| 3. Observability | 1.5 weeks | Phase 1, 2 | Federated metrics, GPU telemetry |
| 4. Intelligence | 2 weeks | Phase 1, 2, 3 | AI chat with tool calling |
| 5. Gateway + Streaming | 1 week | Phase 1-4 | Unified API, real-time updates |
| 6. Frontend | 2 weeks | Phase 1-5 | Web UI for all features |

**Total MVP:** ~8.5 weeks

---

## Post-MVP Enhancements

After MVP, these can be added incrementally:

**Phase 7: Additional Personas**
- Add remaining 4 personas (platform-ops, gpu-expert, network-cnf, telco-5g)
- Custom persona creation

**Phase 8: Advanced Observability**
- Tempo trace integration
- Loki log queries
- CNF-specific metrics (DPDK, PTP, SR-IOV)

**Phase 9: AIOps Features**
- Anomaly detection (statistical, ML-based)
- Root cause analysis
- Korrel8r integration
- Report generation

**Phase 10: Production Hardening**
- Helm charts
- OpenShift deployment manifests
- HA configurations
- Backup/restore procedures

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| vLLM not available locally | Mock LLM responses for development |
| No real clusters to test | Create mock Prometheus/K8s APIs |
| GPU nodes not available | Mock nvidia-smi responses |
| OAuth complexity | Implement bypass mode for development |

---

## Development Environment Quick Start

After Phase 1 completion:
```bash
# Start infrastructure
docker-compose up -d postgresql redis

# Run migrations
cd src/shared && alembic upgrade head

# Start services (each in separate terminal)
cd src/cluster-registry && uvicorn main:app --reload --port 8001
cd src/observability-collector && uvicorn main:app --reload --port 8002
cd src/intelligence-engine && uvicorn main:app --reload --port 8003
cd src/realtime-streaming && uvicorn main:app --reload --port 8004
cd src/api-gateway && uvicorn main:app --reload --port 8000

# Start frontend
cd src/frontend && npm run dev
```
