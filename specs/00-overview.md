# 00 - Architecture Overview

## Document Info
| Field | Value |
|-------|-------|
| Version | 0.1.0 |
| Status | Draft |
| Last Updated | 2024-12-24 |

---

## 1. Vision

AIOps NextGen is a cloud-native platform that unifies observability data from multiple OpenShift clusters and provides AI-powered operational intelligence. It transforms raw metrics, traces, and logs into actionable insights through natural language interactions with domain-expert AI personas.

---

## 2. Design Principles

### 2.1 Isolation & Modularity
- Each component is independently deployable
- No shared state except through defined APIs
- Components can be scaled independently

### 2.2 OpenShift-Native
- All components run as OpenShift workloads
- Uses OpenShift's built-in capabilities (Routes, OAuth, monitoring)
- Integrates with OpenShift's observability stack (Prometheus, Tempo, Loki)

### 2.3 Multi-Cluster First
- Designed for fleet management from day one
- Hub-spoke model with centralized control plane
- Federated queries across cluster boundaries

### 2.4 AI-Augmented, Not AI-Dependent
- Core functionality works without LLM availability
- AI enhances insights but doesn't block operations
- Graceful degradation when AI services are unavailable

### 2.5 Real-Time by Default
- WebSocket-based streaming for live updates
- Sub-second latency for critical metrics
- Polling only as fallback mechanism

---

## 3. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              AIOPS NEXTGEN PLATFORM                             │
│                           (Deployed on Hub Cluster)                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │                         PRESENTATION LAYER                                 │ │
│  │  ┌─────────────────────────────────────────────────────────────────────┐   │ │
│  │  │                     Frontend Application                            │   │ │
│  │  │  • React SPA with TypeScript                                        │   │ │
│  │  │  • WebSocket client for real-time updates                           │   │ │
│  │  │  • MCP client for AI tool invocation                                │   │ │
│  │  └─────────────────────────────────────────────────────────────────────┘   │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                       │                                         │
│                                       ▼                                         │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │                           ACCESS LAYER                                     │ │
│  │  ┌─────────────────────────────────────────────────────────────────────┐   │ │
│  │  │                       API Gateway                                   │   │ │
│  │  │  • REST API (OpenAPI 3.0)                                           │   │ │
│  │  │  • WebSocket endpoints                                              │   │ │
│  │  │  • MCP protocol endpoints (SSE/Streamable HTTP)                     │   │ │
│  │  │  • Authentication via OpenShift OAuth                               │   │ │
│  │  └─────────────────────────────────────────────────────────────────────┘   │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                       │                                         │
│           ┌───────────────────────────┼───────────────────────────┐             │
│           ▼                           ▼                           ▼             │
│  ┌─────────────────┐      ┌─────────────────────┐      ┌─────────────────────┐  │
│  │   Real-Time     │      │    Intelligence     │      │   Observability     │  │
│  │   Streaming     │      │      Engine         │      │     Collector       │  │
│  │   Service       │◄────►│                     │◄────►│                     │  │
│  │                 │      │  • LLM Router       │      │  • Metrics          │  │
│  │  • WebSocket    │      │  • Domain Personas  │      │  • Traces           │  │
│  │  • Event Bus    │      │  • Anomaly Detect   │      │  • Logs             │  │
│  │  • Subscriptions│      │  • RCA Engine       │      │  • Alerts           │  │
│  └────────┬────────┘      └──────────┬──────────┘      └──────────┬──────────┘  │
│           │                          │                            │             │
│           └──────────────────────────┼────────────────────────────┘             │
│                                      ▼                                          │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │                         DATA LAYER                                         │ │
│  │  ┌─────────────────────────────────────────────────────────────────────┐   │ │
│  │  │                    Cluster Registry                                 │   │ │
│  │  │  • Cluster metadata and credentials                                 │   │ │
│  │  │  • Health status and connectivity                                   │   │ │
│  │  │  • Capability discovery                                             │   │ │
│  │  └─────────────────────────────────────────────────────────────────────┘   │ │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐                   │ │
│  │  │ PostgreSQL    │  │ Redis         │  │ Object Store  │                   │ │
│  │  │ (Metadata)    │  │ (Cache/PubSub)│  │ (Reports/Logs)│                   │ │
│  │  └───────────────┘  └───────────────┘  └───────────────┘                   │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    ▼                  ▼                  ▼
            ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
            │  Cluster A  │    │  Cluster B  │    │  Cluster N  │
            │  (Spoke)    │    │  (Spoke)    │    │  (Edge)     │
            │             │    │             │    │             │
            │ Prometheus  │    │ Prometheus  │    │ Prometheus  │
            │ Tempo       │    │ Tempo       │    │ (Metrics)   │
            │ Loki        │    │ Loki        │    │             │
            │ GPU Nodes   │    │ CNF Pods    │    │ vDU/vCU     │
            └─────────────┘    └─────────────┘    └─────────────┘
```

---

## 4. Component Summary

| Component | Responsibility | Technology | Spec Document |
|-----------|---------------|------------|---------------|
| **Cluster Registry** | Manage cluster inventory, credentials, health | Python/FastAPI + PostgreSQL | `02-cluster-registry.md` |
| **Observability Collector** | Federated queries to Prometheus/Tempo/Loki | Python/FastAPI | `03-observability-collector.md` |
| **Intelligence Engine** | LLM routing, personas, anomaly detection | Python/FastAPI + vLLM | `04-intelligence-engine.md` |
| **Real-Time Streaming** | WebSocket hub, event streaming | Python/FastAPI + Redis | `05-realtime-streaming.md` |
| **API Gateway** | Unified API, auth, rate limiting | Python/FastAPI | `06-api-gateway.md` |
| **Frontend** | User interface, dashboards, chat | React/TypeScript | `07-frontend.md` |

---

## 5. Communication Patterns

### 5.1 Synchronous (Request-Response)
- REST APIs between components
- Used for: CRUD operations, queries, configuration

### 5.2 Asynchronous (Event-Driven)
- Redis Pub/Sub for inter-component events
- Used for: Alerts, metric updates, state changes

### 5.3 Streaming
- WebSocket for client real-time updates
- Server-Sent Events (SSE) for MCP protocol
- Used for: Live dashboards, AI chat streaming

---

## 6. Authentication & Authorization

### 6.1 External (User-facing)
- OpenShift OAuth integration
- JWT tokens for API authentication
- Role-based access control (RBAC)

### 6.2 Internal (Service-to-Service)
- Kubernetes ServiceAccount tokens
- mTLS via OpenShift Service Mesh (optional)
- Network policies for isolation

### 6.3 Cluster Access
- Per-cluster ServiceAccount with scoped permissions
- Kubeconfig stored encrypted in Kubernetes Secrets
- Token rotation via CronJob

---

## 7. Data Flow Summary

```
User Request Flow:
──────────────────
User → Frontend → API Gateway → [Service] → Response

Real-Time Update Flow:
──────────────────────
[Spoke Cluster] → Observability Collector → Redis PubSub → Streaming Service → WebSocket → Frontend

AI Query Flow:
──────────────
User Question → API Gateway → Intelligence Engine → Observability Collector → [Data] → LLM → Response

Alert Flow:
───────────
[Spoke Alertmanager] → Observability Collector → Intelligence Engine (RCA) → Streaming Service → Frontend
```

---

## 8. Deployment Model

### 8.1 Hub Cluster
All AIOps NextGen components run on the hub cluster:
- Single namespace: `aiops-nextgen`
- Managed via Helm chart or Kustomize
- Requires: 8 CPU cores, 16GB RAM minimum

### 8.2 Spoke Clusters
No additional components required on spoke clusters:
- Uses existing Prometheus/Thanos
- Uses existing Tempo (if available)
- Uses existing Loki (if available)
- Requires: ServiceAccount with read permissions

### 8.3 Edge/Far-Edge Clusters
Lightweight mode for resource-constrained environments:
- Metrics-only collection (no traces/logs)
- Reduced polling frequency
- Local buffering for intermittent connectivity

---

## 9. Technology Stack Summary

| Layer | Technology | Rationale |
|-------|------------|-----------|
| Language | Python 3.11+ | Ecosystem maturity, AI/ML libraries |
| Web Framework | FastAPI | Async support, OpenAPI, performance |
| Frontend | React 18 + TypeScript | Industry standard, real-time capable |
| Database | PostgreSQL 15 | Reliable, JSON support, OpenShift certified |
| Cache/PubSub | Redis 7 | Low latency, pub/sub, OpenShift certified |
| Object Storage | MinIO / ODF | S3-compatible, OpenShift native |
| Observability | OpenTelemetry | Vendor neutral, comprehensive |
| Container Runtime | Podman/CRI-O | OpenShift native |
| Orchestration | OpenShift 4.14+ | Target platform |

---

## 10. Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Availability | 99.9% (hub components) |
| Latency (API) | p95 < 200ms |
| Latency (Real-time) | p95 < 500ms |
| Clusters Supported | 100+ |
| Concurrent Users | 50+ |
| Data Retention | 90 days (configurable) |
| Recovery Time Objective | < 15 minutes |
| Recovery Point Objective | < 5 minutes |

---

## 11. Spec Dependencies

```
┌─────────────────┐
│ 01-data-models  │◄──────────────────────────────────────────┐
└────────┬────────┘                                           │
         │ (used by all)                                      │
         ▼                                                    │
┌─────────────────┐                                           │
│ 02-cluster-     │                                           │
│    registry     │◄─────────────────────────────────┐        │
└────────┬────────┘                                  │        │
         │                                           │        │
         ▼                                           │        │
┌─────────────────┐      ┌─────────────────┐         │        │
│ 03-observability│◄────►│ 04-intelligence │         │        │
│    collector    │      │     engine      │         │        │
└────────┬────────┘      └────────┬────────┘         │        │
         │                        │                  │        │
         └────────────┬───────────┘                  │        │
                      ▼                              │        │
              ┌─────────────────┐                    │        │
              │ 05-realtime-    │                    │        │
              │    streaming    │                    │        │
              └────────┬────────┘                    │        │
                       │                             │        │
                       ▼                             │        │
              ┌─────────────────┐                    │        │
              │ 06-api-gateway  │────────────────────┤        │
              └────────┬────────┘                    │        │
                       │                             │        │
                       ▼                             │        │
              ┌─────────────────┐                    │        │
              │ 07-frontend     │────────────────────┴────────┘
              └─────────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ 08-integration- │
              │     matrix      │
              └─────────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ 09-deployment   │
              └─────────────────┘
```

---

## 12. Open Questions for Review

1. **Hub Cluster Selection**: Should the platform support running on any cluster or require a dedicated hub?
2. **Multi-tenancy**: Should we support multiple tenants (teams/orgs) with data isolation?
3. **Offline Mode**: How should edge clusters behave when disconnected from hub?
4. **LLM Provider Priority**: Default to local vLLM or allow external providers (OpenAI, Anthropic)?
5. **GPU Metrics Source**: Use DCGM exporter (Prometheus) or direct nvidia-smi queries?

---

## Next: [01-data-models.md](./01-data-models.md)
