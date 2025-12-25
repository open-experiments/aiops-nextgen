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

## Design Principles

- **Air-Gapped Ready**: Designed to work in environments without external internet access
- **On-Premises First**: All core components run on-premises within OpenShift
- **Local LLM Preferred**: Primary AI via vLLM with locally-hosted models (Llama, Mistral, Qwen); external AI APIs (Gemini, Claude, ChatGPT) supported as optional alternative
- **Self-Contained Storage**: MinIO or OpenShift Data Foundation for object storage

---

## Solution Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                   USERS                                             │
│                    Operators · SREs · Platform Engineers                            │
└─────────────────────────────────────┬───────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              PRESENTATION LAYER                                     │
│  ┌───────────────────────────────────────────────────────────────────────────────┐  │
│  │                         Frontend (React + TypeScript)                         │  │
│  │   Fleet Dashboard │ GPU Monitoring │ AI Chat │ Observability Explorer         │  │
│  └───────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────┬───────────────────────────────────────────────┘
                                      │ HTTPS / WSS
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                ACCESS LAYER                                         │
│  ┌───────────────────────────────────────────────────────────────────────────────┐  │
│  │                      API Gateway (FastAPI + OpenShift OAuth)                  │  │
│  │   REST API │ WebSocket Proxy │ MCP Protocol │ Rate Limiting │ RBAC            │  │
│  └───────────────────────────────────────────────────────────────────────────────┘  │
└───────────┬─────────────────┬─────────────────┬─────────────────┬───────────────────┘
            │                 │                 │                 │
            ▼                 ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                               SERVICE LAYER                                         │
│                                                                                     │
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
│                                 DATA LAYER                                          │
│                                                                                     │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────────────┐  │
│  │ PostgreSQL          │  │ Redis               │  │ Object Storage (MinIO/ODF)  │  │
│  │                     │  │                     │  │                             │  │
│  │ • clusters schema   │  │ • DB 0: PubSub      │  │ • aiops-reports bucket      │  │
│  │ • intelligence      │  │ • DB 1: Rate Limit  │  │ • aiops-attachments bucket  │  │
│  │   schema            │  │ • DB 2: Cache       │  │                             │  │
│  │                     │  │ • DB 3: Sessions    │  │                             │  │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────────────┘  │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                          ON-PREMISES INTEGRATIONS                                   │
│                                                                                     │
│  ┌──────────────────────────────────────┐  ┌─────────────────────────────────────┐  │
│  │         SPOKE CLUSTERS               │  │      LLM INFERENCE                  │  │
│  │                                      │  │                                     │  │
│  │  ┌──────────┐ ┌─────────┐ ┌───────┐  │  │  ┌─────────────────────────────────┐│  │
│  │  │Prometheus│ │ Tempo   │ │ Loki  │  │  │  │           vLLM Server           ││  │
│  │  │ Metrics  │ │ Traces  │ │ Logs  │  │  │  │  • Llama 3.x / Mistral / Qwen   ││  │
│  │  └──────────┘ └─────────┘ └───────┘  │  │  │  • GPU Accelerated (A100/H100)  ││  │
│  │                                      │  │  │  • OpenAI-Compatible API        ││  │
│  │  100+ OCP Clusters (Hub-Spoke)       │  │  └─────────────────────────────────┘│  │
│  └──────────────────────────────────────┘  └─────────────────────────────────────┘  │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                              REQUEST FLOWS                                           │
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
                    │                              │(vLLM/ExtAPI)│
                    │                              └──────┬──────┘
                    │                                     │
                    │           Tool Calls                ▼
                    │    ┌────────────────────────────────────────────┐
                    │    │                                            │
                    │    ▼                                            ▼
                    │ ┌───────────────┐                    ┌─────────────────┐
                    └─│ Observability │ (query_metrics,    │ Cluster Registry│
                      │ Collector     │  search_traces)    │ (list_clusters) │
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
| **AI/LLM** | vLLM (preferred); Gemini/Claude/ChatGPT (optional) | LLM inference |
| **Data** | PostgreSQL 15, Redis 7, MinIO | Persistence, cache, objects |
| **Observability** | OpenTelemetry, Prometheus, Tempo, Loki | Telemetry |
| **Deployment** | Helm, Kustomize, OpenShift 4.16+ | Container orchestration |

---

## Project Structure

```
aiops-nextgen/
├── README.md                    # This file
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
│   ├── helm/                   # Helm charts (future)
│   └── openshift/              # Kustomize overlays for OpenShift
└── src/                        # Source code
    ├── shared/                 # Shared Python package (models, db, redis, config)
    ├── cluster-registry/       # Fleet management service
    ├── observability-collector/# Metrics federation service
    ├── intelligence-engine/    # AI/LLM service
    ├── realtime-streaming/     # WebSocket service
    ├── api-gateway/            # Entry point service
    ├── frontend/               # React SPA (pending)
    ├── docker-compose.yml      # Local development stack
    └── development-plan.md     # Implementation roadmap
```

---

## Development Phases

| Phase | Focus | Status |
|-------|-------|--------|
| 1 | Foundation & Data Layer (shared models, PostgreSQL, Redis) | ✅ Complete |
| 2 | Cluster Registry (fleet CRUD, health monitoring, events) | ✅ Complete |
| 3 | Observability Collector (metrics, alerts, GPU telemetry) | ✅ Complete |
| 4 | Intelligence Engine (LLM, personas, chat, tool calling) | ✅ Complete |
| 5 | Real-time Streaming & API Gateway | ✅ Complete |
| 6 | Frontend (React SPA) | Pending |

See [`src/development-plan.md`](src/development-plan.md) for detailed task tracking.

---

## Resource Requirements

| Environment | CPU | Memory | Storage |
|-------------|-----|--------|---------|
| Development | 2.6 cores | 4.4 Gi | 11 Gi |
| Production (HA) | 8.2 cores | 14.5 Gi | 55 Gi |
| + Local LLM (3B) | +4 cores | +16 Gi | +50 Gi |

---

## Quick Start

### Local Development

```bash
# Clone repository
git clone https://github.com/open-experiments/aiops-nextgen.git
cd aiops-nextgen

# Start infrastructure (PostgreSQL + Redis)
cd src && docker-compose up -d postgresql redis

# Start services (each in a separate terminal)
cd src/cluster-registry && uvicorn app.main:app --reload --port 8001
cd src/observability-collector && uvicorn app.main:app --reload --port 8002
cd src/intelligence-engine && uvicorn app.main:app --reload --port 8003
cd src/realtime-streaming && uvicorn app.main:app --reload --port 8004
cd src/api-gateway && uvicorn app.main:app --reload --port 8000
```

### OpenShift Deployment

```bash
# Login to OpenShift
oc login --token=<token> --server=<api-server>

# Create namespace and deploy
oc new-project aiops-nextgen
oc apply -k deploy/openshift/

# Verify deployment
oc get pods -n aiops-nextgen
```

### API Endpoints

| Service | Port | Health Check |
|---------|------|--------------|
| API Gateway | 8000 | `GET /health`, `GET /ready` |
| Cluster Registry | 8001 | `GET /health`, `GET /ready` |
| Observability Collector | 8002 | `GET /health`, `GET /ready` |
| Intelligence Engine | 8003 | `GET /health`, `GET /ready` |
| Real-Time Streaming | 8004 | `GET /health`, `GET /ready` |

---
