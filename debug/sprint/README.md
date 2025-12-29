# AIOps NextGen Sprint Definitions

This folder contains detailed sprint definitions for fixing all 23 issues identified in the code audit. Each sprint file is self-contained with complete implementation details, code snippets, tests, and acceptance criteria.

## Sprint Execution Order

| Sprint | Priority | Focus Area | Issues | Dependencies |
|--------|----------|------------|--------|--------------|
| [Sprint 1](sprint-01-security-foundation.md) | P0-BLOCKING | Security Foundation | ISSUE-010, 011, 015 | None |
| [Sprint 2](sprint-02-kubernetes-integration.md) | P0-BLOCKING | Kubernetes Integration | ISSUE-002, 003, 004 | Sprint 1 |
| [Sprint 3](sprint-03-prometheus-auth.md) | P1 | Prometheus Authentication | ISSUE-012 | Sprint 1, 2 |
| [Sprint 4](sprint-04-logs-traces.md) | P1 | Logs & Traces | ISSUE-005, 006 | Sprint 1, 2, 3 |
| [Sprint 5](sprint-05-gpu-telemetry.md) | P0 | GPU Telemetry | ISSUE-001 | Sprint 1, 2, 3 |
| [Sprint 6](sprint-06-cnf-monitoring.md) | P1 | CNF Monitoring | ISSUE-013 | Sprint 1, 2, 3 |
| [Sprint 7](sprint-07-websocket-hardening.md) | P1 | WebSocket Hardening | ISSUE-016, 017, 020 | Sprint 1 |
| [Sprint 8](sprint-08-anomaly-rca.md) | P1 | Anomaly Detection & RCA | ISSUE-007, 008 | Sprint 1, 3, 4 |
| [Sprint 9](sprint-09-reports-mcp.md) | P2 | Reports & MCP Tools | ISSUE-009, 014 | Sprint 1-8 |
| [Sprint 10](sprint-10-api-gateway-polish.md) | P2 | API Gateway Polish | ISSUE-018, 019, 021, 022 | All |

## Issue Mapping

### CRITICAL Issues (P0)
- **ISSUE-001**: Fake GPU collector → Sprint 5
- **ISSUE-002**: In-memory credentials → Sprint 2
- **ISSUE-010**: Missing OAuth → Sprint 1
- **ISSUE-011**: Missing RBAC → Sprint 1

### HIGH Issues (P1)
- **ISSUE-003**: Mocked credential validation → Sprint 2
- **ISSUE-004**: Missing DiscoveryService → Sprint 2
- **ISSUE-005**: Missing Loki collector → Sprint 4
- **ISSUE-006**: Missing Tempo collector → Sprint 4
- **ISSUE-007**: Missing Anomaly Detection → Sprint 8
- **ISSUE-008**: Missing RCA Service → Sprint 8
- **ISSUE-012**: Prometheus missing auth → Sprint 3
- **ISSUE-013**: Missing CNF collectors → Sprint 6
- **ISSUE-015**: WebSocket auth bypassed → Sprint 1
- **ISSUE-016**: No heartbeat manager → Sprint 7
- **ISSUE-017**: No backpressure handler → Sprint 7

### MEDIUM Issues (P2)
- **ISSUE-009**: Missing Report Service → Sprint 9
- **ISSUE-014**: Only 6/15+ MCP tools → Sprint 9
- **ISSUE-018**: Chat not persisted → Sprint 10
- **ISSUE-019**: Health aggregation missing → Sprint 10
- **ISSUE-020**: No WebSocket proxy → Sprint 7

### LOW Issues (P3)
- **ISSUE-021**: No request validation → Sprint 10
- **ISSUE-022**: No distributed tracing → Sprint 10

## Files Per Sprint

Each sprint creates/modifies specific files. Total unique files across all sprints:

```
src/api-gateway/
├── middleware/
│   ├── oauth.py              (Sprint 1)
│   ├── validation.py         (Sprint 10)
│   └── ws_proxy.py           (Sprint 7)
├── services/
│   ├── rbac.py               (Sprint 1)
│   └── health_aggregator.py  (Sprint 10)
└── main.py                   (Sprint 1, 10)

src/cluster-registry/
├── services/
│   ├── credential_store.py   (Sprint 2)
│   ├── credential_validator.py (Sprint 2)
│   └── discovery.py          (Sprint 2)
└── tests/

src/observability-collector/
├── clients/
│   ├── prometheus.py         (Sprint 3)
│   ├── loki.py               (Sprint 4)
│   └── tempo.py              (Sprint 4)
├── collectors/
│   ├── gpu.py                (Sprint 5)
│   ├── ptp.py                (Sprint 6)
│   └── sriov.py              (Sprint 6)
├── services/
│   ├── query_cache.py        (Sprint 3)
│   ├── metrics_collector.py  (Sprint 3)
│   ├── logs_collector.py     (Sprint 4)
│   └── traces_collector.py   (Sprint 4)
└── api/v1/
    ├── metrics.py            (Sprint 3)
    ├── logs.py               (Sprint 4)
    ├── traces.py             (Sprint 4)
    ├── gpu.py                (Sprint 5)
    └── cnf.py                (Sprint 6)

src/realtime-streaming/
├── middleware/
│   └── ws_auth.py            (Sprint 1)
├── services/
│   ├── heartbeat.py          (Sprint 7)
│   ├── backpressure.py       (Sprint 7)
│   └── subscription.py       (Sprint 7)
└── api/v1/
    └── websocket.py          (Sprint 1, 7)

src/intelligence-engine/
├── services/
│   ├── anomaly_detection.py  (Sprint 8)
│   ├── rca.py                (Sprint 8)
│   ├── reports.py            (Sprint 9)
│   └── chat_persistence.py   (Sprint 10)
├── mcp/
│   └── tools.py              (Sprint 9)
└── api/v1/
    ├── anomaly.py            (Sprint 8)
    ├── reports.py            (Sprint 9)
    └── mcp.py                (Sprint 9)

src/shared/
└── observability/
    └── tracing.py            (Sprint 10)

migrations/
└── versions/
    └── 002_chat_tables.py    (Sprint 10)

deploy/
└── rbac/
    └── cluster-registry-rbac.yaml (Sprint 2)
```

## Execution Guide

### Before Starting
1. Create feature branch: `git checkout -b feature/bugfix-sprint-XX`
2. Read the sprint file completely
3. Ensure dependencies from prior sprints are complete

### During Sprint
1. Implement files in order listed
2. Write tests alongside implementation
3. Run linting: `ruff check src/`
4. Run tests: `pytest src/<service>/tests/`

### After Sprint
1. Verify all acceptance criteria
2. Run integration tests
3. Update API documentation
4. Create PR for review

## Dependencies Summary

```
Sprint 1 ─┬─► Sprint 2 ─┬─► Sprint 3 ─┬─► Sprint 4 ─┬─► Sprint 5
          │             │             │             │
          │             │             │             └─► Sprint 6
          │             │             │
          │             │             └─► Sprint 8
          │             │
          └─► Sprint 7

Sprint 1-8 ─► Sprint 9 ─► Sprint 10
```

## Success Metrics

After completing all sprints:
- 0 critical/high issues remaining
- All 23 issues resolved
- >80% test coverage per service
- All acceptance criteria verified
- E2E integration tests passing
- Security audit passed
