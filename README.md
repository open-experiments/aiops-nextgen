# AIOps NextGen Platform

AI-driven Platform Operations for OpenShift Container Platform (OCP) and Cloud-Native Functions (CNFs).

## Overview

AIOps NextGen is a unified observability and intelligence platform that provides:
- Multi-cluster fleet management and monitoring
- AI-powered insights with domain expert personas
- Real-time GPU and CNF telemetry
- Automated anomaly detection and root cause analysis
- Natural language queries across metrics, traces, and logs

## Target Platform

**OpenShift Container Platform 4.14+**

## Project Structure

```
aiops-nextgen/
├── README.md                    # This file
├── specs/                       # Component specifications (review before coding)
│   ├── 00-overview.md          # Architecture overview and principles
│   ├── 01-data-models.md       # Shared data models and schemas
│   ├── 02-cluster-registry.md  # Cluster Registry Service spec
│   ├── 03-observability-collector.md  # Observability Collector spec
│   ├── 04-intelligence-engine.md      # AI/LLM Intelligence Engine spec
│   ├── 05-realtime-streaming.md       # Real-time Streaming Service spec
│   ├── 06-api-gateway.md              # API Gateway spec
│   ├── 07-frontend.md                 # Frontend Application spec
│   ├── 08-integration-matrix.md       # Integration points and contracts
│   └── 09-deployment.md               # OpenShift deployment spec
├── docs/                        # Additional documentation
├── deploy/                      # Deployment manifests
│   ├── helm/                   # Helm charts
│   └── kustomize/              # Kustomize overlays
└── src/                        # Source code (after spec approval)
    ├── cluster-registry/       # Cluster Registry Service
    ├── observability-collector/# Observability Collector
    ├── intelligence-engine/    # AI/LLM Engine
    ├── realtime-streaming/     # WebSocket/Streaming Service
    ├── api-gateway/            # Unified API Gateway
    └── frontend/               # React Frontend
```

## Development Phases

| Phase | Focus | Status |
|-------|-------|--------|
| 1 | Specification Review | **In Progress** |
| 2 | Core Infrastructure (Registry, Collector) | Pending |
| 3 | Intelligence Layer (LLM, Personas) | Pending |
| 4 | Real-time & Frontend | Pending |
| 5 | AIOps Features (Anomaly, RCA) | Pending |
| 6 | CNF/Telco Specialization | Pending |

## Specification Review Process

1. Read specs in order (00 → 09)
2. Each spec defines: Purpose, Interfaces, Data Models, Dependencies
3. Integration points are defined in `08-integration-matrix.md`
4. Provide feedback before coding begins

## License

Apache 2.0
