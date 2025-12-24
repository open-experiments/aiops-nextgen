# AIOps NextGen Platform

AI-driven Platform Operations for OpenShift Container Platform (OCP) and Cloud-Native Network Functions (CNFs).

## Overview

AIOps NextGen is a unified observability and intelligence platform that provides:
- Multi-cluster fleet management and monitoring
- AI-powered insights with domain expert personas
- Real-time GPU and CNF telemetry
- Automated anomaly detection and root cause analysis
- Natural language queries across metrics, traces, and logs

## Target Platform

**OpenShift Container Platform 4.16+** (x86_64, ARM64)

---

## Solution Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                   USERS                                              │
│                    Operators · SREs · Platform Engineers                             │
└─────────────────────────────────────┬───────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              PRESENTATION LAYER                                      │
│  ┌───────────────────────────────────────────────────────────────────────────────┐  │
│  │                         Frontend (React + TypeScript)                          │  │
│  │   Fleet Dashboard │ GPU Monitoring │ AI Chat │ Observability Explorer         │  │
│  └───────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────┬───────────────────────────────────────────────┘
                                      │ HTTPS / WSS
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                ACCESS LAYER                                          │
│  ┌───────────────────────────────────────────────────────────────────────────────┐  │
│  │                      API Gateway (FastAPI + OpenShift OAuth)                   │  │
│  │   REST API │ WebSocket Proxy │ MCP Protocol │ Rate Limiting │ RBAC            │  │
│  └───────────────────────────────────────────────────────────────────────────────┘  │
└───────────┬─────────────────┬─────────────────┬─────────────────┬───────────────────┘
            │                 │                 │                 │
            ▼                 ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                               SERVICE LAYER                                          │
│                                                                                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ Cluster         │  │ Observability   │  │ Intelligence    │  │ Real-Time       │ │
│  │ Registry        │  │ Collector       │  │ Engine          │  │ Streaming       │ │
│  │                 │  │                 │  │                 │  │                 │ │
│  │ • Fleet CRUD    │  │ • Prometheus    │  │ • LLM Router    │  │ • WebSocket Hub │ │
│  │ • Health Mon.   │  │ • Tempo Traces  │  │ • AI Personas   │  │ • Event Routing │ │
│  │ • Credentials   │  │ • Loki Logs     │  │ • Anomaly Det.  │  │ • Subscriptions │ │
│  │ • Capabilities  │  │ • GPU Telemetry │  │ • RCA Engine    │  │ • Backpressure  │ │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘ │
│           │                    │                    │                    │          │
└───────────┼────────────────────┼────────────────────┼────────────────────┼──────────┘
            │                    │                    │                    │
            ▼                    ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                 DATA LAYER                                           │
│                                                                                      │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────────────┐  │
│  │ PostgreSQL          │  │ Redis               │  │ Object Storage (MinIO/ODF) │  │
│  │                     │  │                     │  │                             │  │
│  │ • clusters schema   │  │ • DB 0: PubSub      │  │ • aiops-reports bucket      │  │
│  │ • intelligence      │  │ • DB 1: Rate Limit  │  │ • aiops-attachments bucket  │  │
│  │   schema            │  │ • DB 2: Cache       │  │                             │  │
│  │                     │  │ • DB 3: Sessions    │  │                             │  │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────────────┘  │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                            EXTERNAL INTEGRATIONS                                     │
│                                                                                      │
│  ┌─────────────────────────────────────┐  ┌─────────────────────────────────────┐   │
│  │         SPOKE CLUSTERS              │  │         LLM PROVIDERS               │   │
│  │                                     │  │                                     │   │
│  │  ┌─────────┐ ┌─────────┐ ┌───────┐  │  │  ┌─────────┐ ┌─────────┐ ┌───────┐  │   │
│  │  │Promethe.│ │ Tempo   │ │ Loki  │  │  │  │  vLLM   │ │Anthropic│ │OpenAI │  │   │
│  │  │ Metrics │ │ Traces  │ │ Logs  │  │  │  │ (Local) │ │ Claude  │ │  GPT  │  │   │
│  │  └─────────┘ └─────────┘ └───────┘  │  │  └─────────┘ └─────────┘ └───────┘  │   │
│  │                                     │  │                                     │   │
│  │  100+ OCP Clusters (Hub-Spoke)      │  │  Fallback Chain for Resilience      │   │
│  └─────────────────────────────────────┘  └─────────────────────────────────────┘   │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                              REQUEST FLOWS                                            │
└──────────────────────────────────────────────────────────────────────────────────────┘

1. USER QUERY FLOW (Metrics/Traces/Logs)
   ┌──────┐     ┌─────────┐     ┌───────────┐     ┌───────────────┐     ┌─────────┐
   │ User │────▶│ Frontend│────▶│API Gateway│────▶│ Observability │────▶│ Spoke   │
   │      │◀────│         │◀────│           │◀────│ Collector     │◀────│ Cluster │
   └──────┘     └─────────┘     └───────────┘     └───────────────┘     └─────────┘
                                                          │
                                                          ▼
                                                   ┌─────────────┐
                                                   │Cluster Reg. │ (get endpoints)
                                                   └─────────────┘

2. AI CHAT FLOW (Natural Language → Tool Calls → Response)
   ┌──────┐     ┌─────────┐     ┌───────────┐     ┌───────────────┐
   │ User │────▶│ Frontend│────▶│API Gateway│────▶│ Intelligence  │
   │      │     │         │     │           │     │ Engine        │
   └──────┘     └─────────┘     └───────────┘     └───────┬───────┘
                    ▲                                     │
                    │ SSE Stream                          ▼
                    │                              ┌─────────────┐
                    │                              │ LLM Provider│
                    │                              │ (vLLM/Cloud)│
                    │                              └──────┬──────┘
                    │                                     │
                    │           Tool Calls                ▼
                    │    ┌────────────────────────────────────────────┐
                    │    │                                            │
                    │    ▼                                            ▼
                    │ ┌───────────────┐                    ┌─────────────────┐
                    └─│ Observability │ (query_metrics,   │ Cluster Registry│
                      │ Collector     │  search_traces)   │ (list_clusters) │
                      └───────────────┘                    └─────────────────┘

3. REAL-TIME EVENT FLOW (Push Updates)
   ┌─────────────────┐     ┌───────────┐     ┌──────────────┐     ┌─────────┐
   │ Cluster Registry│────▶│   Redis   │────▶│ Real-Time    │────▶│ Frontend│
   │ Obs. Collector  │     │  PubSub   │     │ Streaming    │ WS  │         │
   │ Intel. Engine   │     │           │     │              │────▶│         │
   └─────────────────┘     └───────────┘     └──────────────┘     └─────────┘
        (Publishers)                              (Router)         (Subscriber)

   Events: CLUSTER_STATUS_CHANGED, ALERT_FIRED, GPU_UPDATE, ANOMALY_DETECTED, etc.

4. ANOMALY DETECTION & RCA FLOW
   ┌───────────────┐     ┌───────────────┐     ┌───────────┐     ┌──────────────┐
   │ Observability │────▶│ Intelligence  │────▶│   Redis   │────▶│ Real-Time    │
   │ Collector     │     │ Engine        │     │  PubSub   │     │ Streaming    │
   │ (metrics)     │     │ (detect+RCA)  │     │           │     │              │
   └───────────────┘     └───────────────┘     └───────────┘     └──────┬───────┘
                                │                                       │
                                ▼                                       ▼
                         ┌─────────────┐                         ┌─────────────┐
                         │ LLM Provider│                         │  Frontend   │
                         │ (explain)   │                         │ (alert UI)  │
                         └─────────────┘                         └─────────────┘
```

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | React 18, TypeScript, Vite, Tailwind | Modern SPA |
| **Gateway** | FastAPI, OpenShift OAuth | Auth, routing, rate limiting |
| **Services** | Python 3.11+, FastAPI, SQLAlchemy | Microservices |
| **AI/LLM** | vLLM, Anthropic, OpenAI, Google | LLM inference |
| **Data** | PostgreSQL 15, Redis 7, MinIO | Persistence, cache, objects |
| **Observability** | OpenTelemetry, Prometheus, Tempo, Loki | Telemetry |
| **Deployment** | Helm, Kustomize, OpenShift 4.16+ | Container orchestration |

---

## Project Structure

```
aiops-nextgen/
├── README.md                    # This file
├── CLAUDE.md                    # AI assistant guidance
├── LICENSE                      # MIT License
├── specs/                       # Component specifications
│   ├── 00-overview.md          # Architecture overview
│   ├── 01-data-models.md       # Shared data models
│   ├── 02-cluster-registry.md  # Cluster Registry Service
│   ├── 03-observability-collector.md  # Observability Collector
│   ├── 04-intelligence-engine.md      # AI/LLM Engine
│   ├── 05-realtime-streaming.md       # Real-time Streaming
│   ├── 06-api-gateway.md              # API Gateway
│   ├── 07-frontend.md                 # Frontend Application
│   ├── 08-integration-matrix.md       # Integration contracts
│   └── 09-deployment.md               # OpenShift deployment
├── deploy/                      # Deployment manifests
│   ├── helm/                   # Helm charts
│   └── kustomize/              # Kustomize overlays
└── src/                        # Source code
    ├── cluster-registry/
    ├── observability-collector/
    ├── intelligence-engine/
    ├── realtime-streaming/
    ├── api-gateway/
    └── frontend/
```

---

## Development Phases

| Phase | Focus | Status |
|-------|-------|--------|
| 1 | Specification Review | **Complete** |
| 2 | Core Infrastructure (Registry, Collector) | Pending |
| 3 | Intelligence Layer (LLM, Personas) | Pending |
| 4 | Real-time & Frontend | Pending |
| 5 | AIOps Features (Anomaly, RCA) | Pending |
| 6 | CNF/Telco Specialization | Pending |

---

## Resource Requirements

| Environment | CPU | Memory | Storage |
|-------------|-----|--------|---------|
| Development | 2.6 cores | 4.5 Gi | 11 Gi |
| Production (HA) | 8.2 cores | 14.5 Gi | 55 Gi |
| + Local LLM (3B) | +4 cores | +16 Gi | +50 Gi |

---

## Quick Start

```bash
# Clone repository
git clone https://github.com/open-experiments/aiops-nextgen.git
cd aiops-nextgen

# Review specifications
ls specs/

# Deploy to OpenShift (after implementation)
helm install aiops-nextgen ./deploy/helm/aiops-nextgen \
  --namespace aiops-nextgen \
  --create-namespace
```

---

## License

MIT License - see [LICENSE](LICENSE) for details.
