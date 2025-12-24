# AIOps NextGen MVP Development Plan

## Overview

This plan breaks implementation into 6 phases, each delivering working functionality that subsequent phases extend without rewriting. Each phase produces a deployable increment.

**Key Principles:**
- Each phase is independently deployable and testable
- Later phases add capabilities; they don't replace earlier work
- Shared infrastructure built once in Phase 1
- API contracts defined upfront, implementation evolves

---

## Specification Reference Matrix

| Spec File | Description | Used In Phases |
|-----------|-------------|----------------|
| [`specs/00-overview.md`](../specs/00-overview.md) | Architecture, design principles, component summary | All phases |
| [`specs/01-data-models.md`](../specs/01-data-models.md) | Pydantic/SQLAlchemy models, validation rules | Phase 1, 2, 3, 4 |
| [`specs/02-cluster-registry.md`](../specs/02-cluster-registry.md) | Cluster CRUD, credentials, health checks | Phase 2 |
| [`specs/03-observability-collector.md`](../specs/03-observability-collector.md) | Metrics, traces, logs, GPU, alerts | Phase 3 |
| [`specs/04-intelligence-engine.md`](../specs/04-intelligence-engine.md) | LLM, personas, chat, anomaly, RCA | Phase 4 |
| [`specs/05-realtime-streaming.md`](../specs/05-realtime-streaming.md) | WebSocket, events, subscriptions | Phase 5 |
| [`specs/06-api-gateway.md`](../specs/06-api-gateway.md) | Auth, routing, rate limiting | Phase 5 |
| [`specs/07-frontend.md`](../specs/07-frontend.md) | React UI, pages, components | Phase 6 |
| [`specs/08-integration-matrix.md`](../specs/08-integration-matrix.md) | Service contracts, event flows | All phases |
| [`specs/09-deployment.md`](../specs/09-deployment.md) | Helm, OpenShift, resources | Post-MVP |

---

## Phase 1: Foundation & Data Layer

**Goal:** Establish shared infrastructure, project structure, and a working skeleton

**Spec References:**
- [`specs/00-overview.md`](../specs/00-overview.md) - Section 9: Technology Stack Summary
- [`specs/01-data-models.md`](../specs/01-data-models.md) - All sections (canonical data models)
- [`specs/08-integration-matrix.md`](../specs/08-integration-matrix.md) - Section 6: Shared Data Stores

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

| Component | Spec Reference | Implementation | Used By |
|-----------|---------------|---------------|---------|
| Pydantic models | [`01-data-models.md`](../specs/01-data-models.md) Sections 2-8 | All domain models | All services |
| Database session | [`08-integration-matrix.md`](../specs/08-integration-matrix.md) Section 6.1 | SQLAlchemy async | cluster-registry, intelligence-engine |
| Redis client | [`08-integration-matrix.md`](../specs/08-integration-matrix.md) Section 6.2 | aioredis with connection pool | All services |
| Config loader | [`09-deployment.md`](../specs/09-deployment.md) Section 8 | pydantic-settings + env vars | All services |
| Logging | [`00-overview.md`](../specs/00-overview.md) Section 9 | structlog JSON format | All services |
| Tracing | [`00-overview.md`](../specs/00-overview.md) Section 9 | OpenTelemetry SDK | All services |
| Health endpoints | [`08-integration-matrix.md`](../specs/08-integration-matrix.md) Section 8 | `/health`, `/ready` pattern | All services |

### 1.3 Database Setup

**Spec Reference:** [`08-integration-matrix.md`](../specs/08-integration-matrix.md) Section 6.1

```sql
-- Single database, multiple schemas
CREATE DATABASE aiops;

-- Cluster Registry owns this schema (spec 02, Section 7)
CREATE SCHEMA clusters;

-- Intelligence Engine owns this schema (spec 04, implied from session storage)
CREATE SCHEMA intelligence;
```

### 1.4 Redis Configuration

**Spec Reference:** [`08-integration-matrix.md`](../specs/08-integration-matrix.md) Section 6.2

| Database | Purpose | Key Patterns |
|----------|---------|--------------|
| `0` | PubSub, Events | `aiops:events:*` |
| `1` | Rate Limiting | `ratelimit:user:{user_id}:*` |
| `2` | Caching | `cache:{service}:{key}` |
| `3` | Sessions | `session:{session_id}` |

### 1.5 Local Development Stack
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

### 1.6 Tasks

| Task | Spec Reference | Status |
|------|---------------|--------|
| Create monorepo structure with shared package | [`00-overview.md`](../specs/00-overview.md) Section 4 | [ ] |
| Define Pydantic models: Cluster domain | [`01-data-models.md`](../specs/01-data-models.md) Section 2 | [ ] |
| Define Pydantic models: Observability domain | [`01-data-models.md`](../specs/01-data-models.md) Section 3 | [ ] |
| Define Pydantic models: GPU domain | [`01-data-models.md`](../specs/01-data-models.md) Section 4 | [ ] |
| Define Pydantic models: Intelligence domain | [`01-data-models.md`](../specs/01-data-models.md) Section 5 | [ ] |
| Define Pydantic models: Event models | [`01-data-models.md`](../specs/01-data-models.md) Section 6 | [ ] |
| Define Pydantic models: Report models | [`01-data-models.md`](../specs/01-data-models.md) Section 7 | [ ] |
| Define Pydantic models: Common types | [`01-data-models.md`](../specs/01-data-models.md) Section 8 | [ ] |
| Create SQLAlchemy models for clusters schema | [`02-cluster-registry.md`](../specs/02-cluster-registry.md) Section 7 | [ ] |
| Create SQLAlchemy models for intelligence schema | [`04-intelligence-engine.md`](../specs/04-intelligence-engine.md) Section 4.6 | [ ] |
| Implement Redis client wrapper with pub/sub | [`08-integration-matrix.md`](../specs/08-integration-matrix.md) Section 5 | [ ] |
| Implement config management with validation | [`09-deployment.md`](../specs/09-deployment.md) Section 8 | [ ] |
| Set up structured logging | [`00-overview.md`](../specs/00-overview.md) Section 9 | [ ] |
| Create docker-compose.yml | [`09-deployment.md`](../specs/09-deployment.md) Section 4 | [ ] |
| Create database migration scripts (Alembic) | [`02-cluster-registry.md`](../specs/02-cluster-registry.md) Section 7 | [ ] |
| Set up pytest infrastructure | - | [ ] |
| Create GitHub Actions CI pipeline | - | [ ] |

**Exit Criteria:** `docker-compose up` starts PostgreSQL and Redis; shared package importable by all services; all models validate.

---

## Phase 2: Cluster Registry (Core CRUD)

**Goal:** Working cluster management API - the foundation other services depend on

**Spec References:**
- [`specs/02-cluster-registry.md`](../specs/02-cluster-registry.md) - Primary specification (all sections)
- [`specs/01-data-models.md`](../specs/01-data-models.md) - Section 2: Cluster Domain Models
- [`specs/08-integration-matrix.md`](../specs/08-integration-matrix.md) - Section 4.1: Cluster Registry API Contract

**Deliverables:**
- Full CRUD for clusters
- Credential storage in Kubernetes Secrets (mocked locally)
- Basic health check polling
- Event publishing to Redis
- OpenAPI documentation

### 2.1 API Endpoints

**Spec Reference:** [`02-cluster-registry.md`](../specs/02-cluster-registry.md) Section 4.1

| Priority | Endpoint | Spec Section | Description |
|----------|----------|--------------|-------------|
| P0 | `POST /api/v1/clusters` | 4.1, 4.2 | Register cluster |
| P0 | `GET /api/v1/clusters` | 4.1, 4.3 | List clusters with filtering |
| P0 | `GET /api/v1/clusters/{id}` | 4.1 | Get single cluster |
| P0 | `PUT /api/v1/clusters/{id}` | 4.1 | Update cluster |
| P0 | `DELETE /api/v1/clusters/{id}` | 4.1 | Delete cluster |
| P1 | `GET /api/v1/clusters/{id}/status` | 4.1 | Get cluster status |
| P1 | `POST /api/v1/clusters/{id}/credentials` | 4.1, 4.2 | Upload credentials |
| P1 | `GET /api/v1/fleet/summary` | 4.1, 4.2 | Fleet summary stats |
| P2 | `POST /api/v1/clusters/{id}/refresh` | 4.1 | Force refresh |

### 2.2 Services to Implement

**Spec Reference:** [`02-cluster-registry.md`](../specs/02-cluster-registry.md) Section 5

```python
# Core services (spec section 5.1-5.5)
ClusterService        # CRUD operations (5.1)
CredentialService     # Store/retrieve credentials (5.2)
DiscoveryService      # Capability detection (5.3)
HealthService         # Background health checker (5.4)
EventService          # Publish to Redis (5.5)

# Background tasks
health_check_task     # Periodic polling (spec section 8)
```

### 2.3 Event Publishing

**Spec Reference:** [`02-cluster-registry.md`](../specs/02-cluster-registry.md) Section 6

```python
# Events emitted (consumed by Phase 5)
CLUSTER_REGISTERED
CLUSTER_UPDATED
CLUSTER_DELETED
CLUSTER_STATUS_CHANGED
CLUSTER_CREDENTIALS_UPDATED
CLUSTER_CAPABILITIES_CHANGED
```

### 2.4 Health Check Logic

**Spec Reference:** [`02-cluster-registry.md`](../specs/02-cluster-registry.md) Section 8

| Cluster Type | Interval | Timeout |
|--------------|----------|---------|
| HUB | 15 seconds | 5 seconds |
| SPOKE | 30 seconds | 10 seconds |
| EDGE | 60 seconds | 15 seconds |
| FAR_EDGE | 120 seconds | 30 seconds |

### 2.5 Tasks

| Task | Spec Reference | Status |
|------|---------------|--------|
| Create FastAPI application scaffold | [`02-cluster-registry.md`](../specs/02-cluster-registry.md) Section 3 | [ ] |
| Implement ClusterService with CRUD | [`02-cluster-registry.md`](../specs/02-cluster-registry.md) Section 5.1 | [ ] |
| Implement database repository pattern | [`02-cluster-registry.md`](../specs/02-cluster-registry.md) Section 7 | [ ] |
| Add query filtering | [`02-cluster-registry.md`](../specs/02-cluster-registry.md) Section 4.3 | [ ] |
| Add pagination support | [`01-data-models.md`](../specs/01-data-models.md) Section 8.1 | [ ] |
| Implement CredentialService | [`02-cluster-registry.md`](../specs/02-cluster-registry.md) Section 5.2, 7.2 | [ ] |
| Implement HealthService | [`02-cluster-registry.md`](../specs/02-cluster-registry.md) Section 5.4, 8 | [ ] |
| Implement EventService | [`02-cluster-registry.md`](../specs/02-cluster-registry.md) Section 5.5, 6 | [ ] |
| Add OpenAPI documentation | [`02-cluster-registry.md`](../specs/02-cluster-registry.md) Section 4 | [ ] |
| Write unit tests (>80% coverage) | - | [ ] |
| Write integration tests | - | [ ] |
| Add to docker-compose | [`09-deployment.md`](../specs/09-deployment.md) | [ ] |

**Exit Criteria:** Can register, list, update, delete clusters via API; health status updates in background; events published to Redis.

---

## Phase 3: Observability Collector (Metrics Focus)

**Goal:** Federated Prometheus queries across registered clusters

**Spec References:**
- [`specs/03-observability-collector.md`](../specs/03-observability-collector.md) - Primary specification (all sections)
- [`specs/01-data-models.md`](../specs/01-data-models.md) - Section 3: Observability Domain Models, Section 4: GPU Domain Models
- [`specs/08-integration-matrix.md`](../specs/08-integration-matrix.md) - Section 4.2, 4.3: API Contracts

**Deliverables:**
- PromQL query execution across multiple clusters
- Result aggregation and caching
- GPU telemetry collection (nvidia-smi)
- Alert webhook receiver

### 3.1 API Endpoints

**Spec Reference:** [`03-observability-collector.md`](../specs/03-observability-collector.md) Section 4

| Priority | Endpoint | Spec Section | Description |
|----------|----------|--------------|-------------|
| P0 | `POST /api/v1/metrics/query` | 4.1 | Instant PromQL query |
| P0 | `POST /api/v1/metrics/query_range` | 4.1, 4.7 | Range PromQL query |
| P1 | `GET /api/v1/metrics/labels` | 4.1 | Get label names |
| P1 | `GET /api/v1/alerts` | 4.4, 4.7 | List active alerts |
| P1 | `POST /api/v1/alerts/webhook` | 4.4 | Alertmanager webhook |
| P1 | `GET /api/v1/gpu/nodes` | 4.5, 4.7 | List GPU nodes |
| P2 | `GET /api/v1/gpu/summary` | 4.5 | Fleet GPU summary |

### 3.2 Collectors to Implement

**Spec Reference:** [`03-observability-collector.md`](../specs/03-observability-collector.md) Section 6

```python
PrometheusCollector   # Query Prometheus/Thanos endpoints (6.1)
AlertmanagerCollector # Receive webhook, poll alerts (6.3)
GPUCollector          # Execute nvidia-smi via kubectl exec (6.2)

# Support classes
ResultAggregator      # Merge results from multiple clusters (Section 7.2)
QueryCache            # Redis-based caching (Section 7.3)
```

### 3.3 Federation Strategy

**Spec Reference:** [`03-observability-collector.md`](../specs/03-observability-collector.md) Section 7

### 3.4 Caching Strategy

**Spec Reference:** [`03-observability-collector.md`](../specs/03-observability-collector.md) Section 7.3

| Query Type | Cache TTL | Cache Key Pattern |
|------------|-----------|-------------------|
| Instant query | 30 seconds | `metrics:instant:{hash(query)}:{cluster_id}` |
| Range query (< 1h) | 60 seconds | `metrics:range:{hash(query)}:{cluster_id}:{start}:{end}` |
| Range query (> 1h) | 5 minutes | Same as above |
| GPU telemetry | 5 seconds | `gpu:{cluster_id}:{node_name}` |
| Active alerts | 10 seconds | `alerts:active:{cluster_id}` |

### 3.5 Tasks

| Task | Spec Reference | Status |
|------|---------------|--------|
| Create FastAPI application scaffold | [`03-observability-collector.md`](../specs/03-observability-collector.md) Section 3 | [ ] |
| Implement Cluster Registry client | [`08-integration-matrix.md`](../specs/08-integration-matrix.md) Section 4.2 | [ ] |
| Implement PrometheusCollector | [`03-observability-collector.md`](../specs/03-observability-collector.md) Section 6.1 | [ ] |
| Implement ResultAggregator | [`03-observability-collector.md`](../specs/03-observability-collector.md) Section 7.2 | [ ] |
| Implement QueryCache | [`03-observability-collector.md`](../specs/03-observability-collector.md) Section 7.3 | [ ] |
| Implement AlertmanagerCollector | [`03-observability-collector.md`](../specs/03-observability-collector.md) Section 6.3 | [ ] |
| Implement GPUCollector | [`03-observability-collector.md`](../specs/03-observability-collector.md) Section 6.2 | [ ] |
| Publish events to Redis | [`03-observability-collector.md`](../specs/03-observability-collector.md) Section 8 | [ ] |
| Write mock Prometheus for testing | - | [ ] |
| Write unit and integration tests | - | [ ] |
| Add to docker-compose | [`09-deployment.md`](../specs/09-deployment.md) | [ ] |

**Exit Criteria:** Can execute PromQL across registered clusters; GPU metrics collected; alerts received via webhook.

---

## Phase 4: Intelligence Engine (Chat MVP)

**Goal:** Working AI chat with tool calling and one persona

**Spec References:**
- [`specs/04-intelligence-engine.md`](../specs/04-intelligence-engine.md) - Primary specification (all sections)
- [`specs/01-data-models.md`](../specs/01-data-models.md) - Section 5: Intelligence Domain Models
- [`specs/08-integration-matrix.md`](../specs/08-integration-matrix.md) - Section 4.3, 4.4: API Contracts

**Deliverables:**
- Chat session management
- Local vLLM integration
- MCP tool execution (metrics, alerts, GPU)
- Default persona working
- Streaming responses

### 4.1 API Endpoints

**Spec Reference:** [`04-intelligence-engine.md`](../specs/04-intelligence-engine.md) Section 4

| Priority | Endpoint | Spec Section | Description |
|----------|----------|--------------|-------------|
| P0 | `POST /api/v1/chat/sessions` | 4.1, 4.6 | Create session |
| P0 | `GET /api/v1/chat/sessions/{id}` | 4.1 | Get session |
| P0 | `POST /api/v1/chat/sessions/{id}/messages` | 4.1, 4.6 | Send message |
| P0 | `POST /api/v1/chat/sessions/{id}/stream` | 4.1, 4.6 | Stream response (SSE) |
| P1 | `GET /api/v1/personas` | 4.3, 4.6 | List personas |
| P2 | `POST /api/v1/analysis/anomaly` | 4.4, 4.6 | Anomaly detection |

### 4.2 Core Components

**Spec Reference:** [`04-intelligence-engine.md`](../specs/04-intelligence-engine.md) Sections 5-7

```python
ChatService           # Session management (implied)
LLMRouter             # Route to vLLM (Section 7)
ToolService           # MCP tool registry (Section 6)
PersonaService        # Load and apply personas (Section 5)

# MCP Tools (Section 6.1)
query_metrics         # Execute PromQL
list_alerts           # Get active alerts
get_gpu_nodes         # Get GPU info
list_clusters         # Get clusters from registry
```

### 4.3 Personas (MVP: Default Only)

**Spec Reference:** [`04-intelligence-engine.md`](../specs/04-intelligence-engine.md) Section 5.1

```yaml
# Default persona for MVP
- id: default
  name: Default Assistant
  capabilities:
    - query_metrics
    - search_traces
    - query_logs
    - list_alerts
    - get_gpu_nodes
    - list_clusters
```

### 4.4 vLLM Integration

**Spec Reference:** [`04-intelligence-engine.md`](../specs/04-intelligence-engine.md) Section 7

```python
class LocalVLLMProvider:
    """OpenAI-compatible client for local vLLM (air-gapped)."""
    # See spec section 7.1-7.3
```

### 4.5 Tasks

| Task | Spec Reference | Status |
|------|---------------|--------|
| Create FastAPI application scaffold | [`04-intelligence-engine.md`](../specs/04-intelligence-engine.md) Section 3 | [ ] |
| Implement ChatSession database models | [`01-data-models.md`](../specs/01-data-models.md) Section 5.5 | [ ] |
| Implement ChatService | [`04-intelligence-engine.md`](../specs/04-intelligence-engine.md) implied | [ ] |
| Implement LLMRouter for vLLM | [`04-intelligence-engine.md`](../specs/04-intelligence-engine.md) Section 7 | [ ] |
| Implement ToolService | [`04-intelligence-engine.md`](../specs/04-intelligence-engine.md) Section 6 | [ ] |
| Implement MCP tools | [`04-intelligence-engine.md`](../specs/04-intelligence-engine.md) Section 6.1 | [ ] |
| Implement SSE streaming | [`04-intelligence-engine.md`](../specs/04-intelligence-engine.md) Section 4.6 | [ ] |
| Add default persona | [`04-intelligence-engine.md`](../specs/04-intelligence-engine.md) Section 5.1 | [ ] |
| Create vLLM mock for testing | - | [ ] |
| Write unit and integration tests | - | [ ] |
| Add to docker-compose | [`09-deployment.md`](../specs/09-deployment.md) | [ ] |

**Exit Criteria:** Can create chat session, send messages, receive AI responses with tool calls executed against Observability Collector.

---

## Phase 5: Real-Time Streaming & API Gateway

**Goal:** Unified API entry point and WebSocket-based live updates

**Spec References:**
- [`specs/05-realtime-streaming.md`](../specs/05-realtime-streaming.md) - WebSocket, events, subscriptions
- [`specs/06-api-gateway.md`](../specs/06-api-gateway.md) - Auth, routing, rate limiting
- [`specs/08-integration-matrix.md`](../specs/08-integration-matrix.md) - Section 5: Event Contracts, Section 7: Auth Flow

**Deliverables:**
- API Gateway with routing to all services
- OpenShift OAuth integration (mockable)
- Rate limiting
- WebSocket hub with subscriptions
- Event routing from Redis to clients

### 5.1 API Gateway Routes

**Spec Reference:** [`06-api-gateway.md`](../specs/06-api-gateway.md) Section 4.2

```python
/api/v1/clusters/*    → cluster-registry:8080
/api/v1/fleet/*       → cluster-registry:8080
/api/v1/metrics/*     → observability-collector:8080
/api/v1/alerts/*      → observability-collector:8080
/api/v1/gpu/*         → observability-collector:8080
/api/v1/chat/*        → intelligence-engine:8080
/api/v1/personas/*    → intelligence-engine:8080
/api/v1/analysis/*    → intelligence-engine:8080
/mcp                  → intelligence-engine:8080
/ws                   → realtime-streaming:8080
```

### 5.2 Authentication

**Spec Reference:** [`06-api-gateway.md`](../specs/06-api-gateway.md) Section 5, [`08-integration-matrix.md`](../specs/08-integration-matrix.md) Section 7

### 5.3 Rate Limiting

**Spec Reference:** [`06-api-gateway.md`](../specs/06-api-gateway.md) Section 7

### 5.4 Real-Time Streaming

**Spec Reference:** [`05-realtime-streaming.md`](../specs/05-realtime-streaming.md)

```python
WebSocketHub          # Manage connections (Section 7.1)
SubscriptionManager   # Track client subscriptions (Section 7.2)
EventRouter           # Redis PubSub → WebSocket (Section 7.3)
```

### 5.5 Event Types

**Spec Reference:** [`05-realtime-streaming.md`](../specs/05-realtime-streaming.md) Section 5

| Event Type | Source | Spec Section |
|------------|--------|--------------|
| `CLUSTER_STATUS_CHANGED` | Cluster Registry | 5.1 |
| `ALERT_FIRED` | Observability Collector | 5.2 |
| `ALERT_RESOLVED` | Observability Collector | 5.2 |
| `GPU_UPDATE` | Observability Collector | 5.3 |
| `ANOMALY_DETECTED` | Intelligence Engine | 5.5 |

### 5.6 Tasks

| Task | Spec Reference | Status |
|------|---------------|--------|
| Create API Gateway scaffold | [`06-api-gateway.md`](../specs/06-api-gateway.md) Section 3 | [ ] |
| Implement request routing | [`06-api-gateway.md`](../specs/06-api-gateway.md) Section 4.2 | [ ] |
| Implement OAuth middleware | [`06-api-gateway.md`](../specs/06-api-gateway.md) Section 5 | [ ] |
| Implement rate limiting | [`06-api-gateway.md`](../specs/06-api-gateway.md) Section 7 | [ ] |
| Implement CORS middleware | [`06-api-gateway.md`](../specs/06-api-gateway.md) Section 13 | [ ] |
| Aggregate OpenAPI specs | [`06-api-gateway.md`](../specs/06-api-gateway.md) Section 14 | [ ] |
| Create Real-Time Streaming scaffold | [`05-realtime-streaming.md`](../specs/05-realtime-streaming.md) Section 3 | [ ] |
| Implement WebSocketHub | [`05-realtime-streaming.md`](../specs/05-realtime-streaming.md) Section 7.1 | [ ] |
| Implement SubscriptionManager | [`05-realtime-streaming.md`](../specs/05-realtime-streaming.md) Section 7.2 | [ ] |
| Implement EventRouter | [`05-realtime-streaming.md`](../specs/05-realtime-streaming.md) Section 7.3 | [ ] |
| WebSocket authentication | [`05-realtime-streaming.md`](../specs/05-realtime-streaming.md) Section 4.2 | [ ] |
| Implement heartbeat | [`05-realtime-streaming.md`](../specs/05-realtime-streaming.md) Section 8.1 | [ ] |
| Write unit and integration tests | - | [ ] |
| Update docker-compose | [`09-deployment.md`](../specs/09-deployment.md) | [ ] |

**Exit Criteria:** All API requests route through gateway; WebSocket clients receive real-time events; rate limiting works.

---

## Phase 6: Frontend MVP

**Goal:** Functional web UI for core workflows

**Spec References:**
- [`specs/07-frontend.md`](../specs/07-frontend.md) - Primary specification (all sections)
- [`specs/08-integration-matrix.md`](../specs/08-integration-matrix.md) - API contracts for client calls

**Deliverables:**
- Fleet dashboard with cluster status
- GPU monitoring page
- AI chat interface
- Basic alerts view

### 6.1 Pages (Priority Order)

**Spec Reference:** [`07-frontend.md`](../specs/07-frontend.md) Section 4

| Priority | Page | Spec Section | Features |
|----------|------|--------------|----------|
| P0 | Dashboard | 4.1 | Fleet summary, cluster status grid, recent alerts |
| P0 | Chat | 4.6 | Session management, message input, streaming responses |
| P1 | GPU | 4.3 | Node list, GPU cards with metrics, real-time updates |
| P1 | Clusters | 4.2 | List, add, edit, delete clusters |
| P2 | Alerts | 4.5 | Active alerts list with filtering |
| P2 | Settings | 4.8 | Theme toggle |

### 6.2 Technical Stack

**Spec Reference:** [`07-frontend.md`](../specs/07-frontend.md) Section 2

```
React 18 + TypeScript 5
Vite 5 (build)
Tailwind CSS 3 (styling)
Zustand 4 (state)
Axios (HTTP)
reconnecting-websocket (WebSocket)
```

### 6.3 State Management

**Spec Reference:** [`07-frontend.md`](../specs/07-frontend.md) Section 5

```typescript
// Zustand stores (spec section 5.1)
useAuth()           // Authentication state
useClusters()       // Cluster data + real-time updates
useAlerts()         // Alerts + real-time updates
useGPU()            // GPU metrics + real-time updates
useChat()           // Chat sessions + streaming
```

### 6.4 WebSocket Integration

**Spec Reference:** [`07-frontend.md`](../specs/07-frontend.md) Section 7

### 6.5 Tasks

| Task | Spec Reference | Status |
|------|---------------|--------|
| Create Vite + React + TypeScript scaffold | [`07-frontend.md`](../specs/07-frontend.md) Section 3 | [ ] |
| Set up Tailwind CSS | [`07-frontend.md`](../specs/07-frontend.md) Section 8 | [ ] |
| Create API client with Axios | [`07-frontend.md`](../specs/07-frontend.md) Section 6 | [ ] |
| Implement Zustand stores | [`07-frontend.md`](../specs/07-frontend.md) Section 5 | [ ] |
| Implement useWebSocket hook | [`07-frontend.md`](../specs/07-frontend.md) Section 7 | [ ] |
| Create layout components | [`07-frontend.md`](../specs/07-frontend.md) Section 3 | [ ] |
| Create Dashboard page | [`07-frontend.md`](../specs/07-frontend.md) Section 4.1 | [ ] |
| Create Chat page | [`07-frontend.md`](../specs/07-frontend.md) Section 4.6 | [ ] |
| Create GPU monitoring page | [`07-frontend.md`](../specs/07-frontend.md) Section 4.3 | [ ] |
| Create Clusters page | [`07-frontend.md`](../specs/07-frontend.md) Section 4.2 | [ ] |
| Create Alerts page | [`07-frontend.md`](../specs/07-frontend.md) Section 4.5 | [ ] |
| Add dark mode support | [`07-frontend.md`](../specs/07-frontend.md) Section 8 | [ ] |
| Write component tests | [`07-frontend.md`](../specs/07-frontend.md) Section 10 | [ ] |
| Add Dockerfile with nginx | [`07-frontend.md`](../specs/07-frontend.md) Section 9 | [ ] |
| Update docker-compose | [`09-deployment.md`](../specs/09-deployment.md) | [ ] |

**Exit Criteria:** Can view fleet status, manage clusters, chat with AI, monitor GPUs, see alerts - all via web UI.

---

## Phase Summary

| Phase | Specs Used | Duration | Dependencies | Key Deliverable |
|-------|------------|----------|--------------|-----------------|
| 1. Foundation | 00, 01, 08, 09 | 1 week | None | Shared infra, models, dev environment |
| 2. Cluster Registry | 01, 02, 08 | 1 week | Phase 1 | Working cluster management API |
| 3. Observability | 01, 03, 08 | 1.5 weeks | Phase 1, 2 | Federated metrics, GPU telemetry |
| 4. Intelligence | 01, 04, 08 | 2 weeks | Phase 1, 2, 3 | AI chat with tool calling |
| 5. Gateway + Streaming | 05, 06, 08 | 1 week | Phase 1-4 | Unified API, real-time updates |
| 6. Frontend | 07, 08 | 2 weeks | Phase 1-5 | Web UI for all features |

**Total MVP:** ~8.5 weeks

---

## Post-MVP Enhancements

| Phase | Specs Used | Features |
|-------|------------|----------|
| 7. Additional Personas | 04 Section 5 | Add platform-ops, gpu-expert, network-cnf, telco-5g personas |
| 8. Advanced Observability | 03 Sections 4.2-4.6 | Tempo traces, Loki logs, CNF metrics |
| 9. AIOps Features | 04 Sections 8-9 | Anomaly detection, RCA, Korrel8r, reports |
| 10. Production Hardening | 09 | Helm charts, HA, backup/restore |

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
cd src/cluster-registry && uvicorn app.main:app --reload --port 8001
cd src/observability-collector && uvicorn app.main:app --reload --port 8002
cd src/intelligence-engine && uvicorn app.main:app --reload --port 8003
cd src/realtime-streaming && uvicorn app.main:app --reload --port 8004
cd src/api-gateway && uvicorn app.main:app --reload --port 8000

# Start frontend
cd src/frontend && npm run dev
```

---

## Validation Checklist

Before marking any phase complete, verify:

- [ ] All tasks reference their spec section
- [ ] Implementation matches spec API contracts
- [ ] Data models match [`01-data-models.md`](../specs/01-data-models.md) definitions
- [ ] Events match [`08-integration-matrix.md`](../specs/08-integration-matrix.md) Section 5
- [ ] Error codes match spec error handling sections
- [ ] Configuration follows [`09-deployment.md`](../specs/09-deployment.md) patterns
