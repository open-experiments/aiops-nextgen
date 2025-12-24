# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AIOps NextGen is an AI-driven operations platform for OpenShift Container Platform (OCP) and Cloud-Native Network Functions (CNFs). It provides multi-cluster fleet management, AI-powered insights via domain expert personas, real-time GPU/CNF telemetry, and automated anomaly detection.

**Target Platform:** OpenShift Container Platform 4.16+ (x86_64, ARM64)

**Environment:** Air-gapped / Disconnected (no external cloud services or APIs)

## Current Status

This project is in the **Specification Phase**. All detailed specifications are complete in `specs/`. Source code implementation has not started.

## Specification-First Development

**Always read specs before implementing.** The specs define all APIs, data models, and integration contracts.

Read specs in order:
1. `specs/00-overview.md` - Architecture principles and system vision
2. `specs/01-data-models.md` - Shared schemas (Cluster, Status, Capabilities, etc.)
3. `specs/02-cluster-registry.md` - Cluster inventory service API
4. `specs/03-observability-collector.md` - Federated metrics/traces/logs collection
5. `specs/04-intelligence-engine.md` - LLM routing, personas, anomaly detection
6. `specs/05-realtime-streaming.md` - WebSocket hub and event subscriptions
7. `specs/06-api-gateway.md` - Unified API gateway and routing
8. `specs/07-frontend.md` - React UI structure and components
9. `specs/08-integration-matrix.md` - Inter-service contracts and event flows
10. `specs/09-deployment.md` - OpenShift deployment manifests and resources

## Architecture

**6 Microservices:**
- **Cluster Registry** - Cluster metadata, credentials, health monitoring
- **Observability Collector** - Federated Prometheus/Tempo/Loki queries, GPU telemetry
- **Intelligence Engine** - LLM orchestration, AI personas, RCA
- **Real-Time Streaming** - WebSocket connections, Redis pub/sub event routing
- **API Gateway** - Authentication, routing, rate limiting
- **Frontend** - React SPA with TypeScript

**Data Layer:**
- PostgreSQL 15 (metadata, sessions)
- Redis 7 (pub/sub, caching, rate limiting)
- MinIO/ODF (reports, attachments)

**Communication:**
- REST APIs between services
- Redis Pub/Sub for async events
- WebSocket for real-time client updates
- MCP protocol for AI tool invocation

## Planned Tech Stack

**Backend:** Python 3.11+, FastAPI, SQLAlchemy, OpenTelemetry
**Frontend:** TypeScript 5.x, React 18.x, Vite 5.x, Zustand, Tailwind CSS
**AI/LLM:** vLLM only (local inference, air-gapped - no external APIs)
**Deployment:** Helm charts + Kustomize overlays

## Key Design Principles

1. **Air-Gapped First** - No external cloud services or APIs; all components run on-premises
2. **OpenShift-Native** - Uses Routes, OAuth, built-in monitoring
3. **Multi-Cluster First** - Hub-spoke model, federated queries across cluster boundaries
4. **AI-Augmented, Not Dependent** - Core functionality works without LLM availability
5. **Real-Time by Default** - Sub-second latency for critical metrics
6. **Isolation & Modularity** - Each service independently deployable
