# AIOps NextGen - DevOps Instructions

> **This document is the authoritative guide for all development work on the AIOps NextGen platform. Follow these instructions precisely for consistent, high-quality development, integration and test process.**

---

## Table of Contents

1. [Project Context](#1-project-context)
2. [Document Hierarchy](#2-document-hierarchy)
3. [Development Principles](#3-development-principles)
4. [OpenShift Sandbox Environment](#4-openshift-sandbox-environment)
5. [Sprint Execution Protocol](#5-sprint-execution-protocol)
6. [Code Implementation Standards](#6-code-implementation-standards)
7. [Testing Requirements](#7-testing-requirements)
8. [Git Workflow](#8-git-workflow)
9. [Quality Gates](#9-quality-gates)
10. [Troubleshooting](#10-troubleshooting)
11. [Reference Quick Links](#11-reference-quick-links)

---

## 1. Project Context

### What is AIOps NextGen?

AIOps NextGen is an AI-driven observability platform for managing multiple OpenShift/Kubernetes clusters with specialized support for:
- **GPU workloads** (AI/ML training and inference)
- **Telecom CNF** (PTP synchronization, SR-IOV networking)
- **Federated observability** (Prometheus, Loki, Tempo)
- **Intelligent analysis** (anomaly detection, root cause analysis)

### Current State

The platform has 5 microservices implemented as scaffolds with mock data. A code audit identified **23 issues** (6 CRITICAL, 10 HIGH, 5 MEDIUM, 2 LOW) that must be resolved before production deployment.

### Goal

Transform the scaffold implementation into production-ready code by executing 10 sprints that address all identified issues while maintaining strict adherence to the specification documents.

---

## 2. Document Hierarchy

### Holy Grail Foundations (NEVER DEVIATE)

These documents define the truth. All implementation MUST conform to these specifications:

| Document | Purpose | Location |
|----------|---------|----------|
| `README.md` | Project overview and quick start | `/README.md` |
| `specs/00-overview.md` | Architecture vision, design principles | `/specs/00-overview.md` |
| `specs/01-data-models.md` | Pydantic model definitions | `/specs/01-data-models.md` |
| `specs/02-cluster-registry.md` | Cluster management service spec | `/specs/02-cluster-registry.md` |
| `specs/03-observability-collector.md` | Metrics/logs/traces collection spec | `/specs/03-observability-collector.md` |
| `specs/04-intelligence-engine.md` | AI/ML analysis service spec | `/specs/04-intelligence-engine.md` |
| `specs/05-realtime-streaming.md` | WebSocket streaming spec | `/specs/05-realtime-streaming.md` |
| `specs/06-api-gateway.md` | Gateway, auth, routing spec | `/specs/06-api-gateway.md` |
| `specs/07-frontend.md` | React UI specification | `/specs/07-frontend.md` |
| `specs/08-integration-matrix.md` | Service communication patterns | `/specs/08-integration-matrix.md` |
| `specs/09-deployment.md` | Kubernetes/Helm deployment | `/specs/09-deployment.md` |

### Debug Documents (Problem Definition)

| Document | Purpose | Location |
|----------|---------|----------|
| `debug/issues.md` | 23 identified issues with severity | `/debug/issues.md` |
| `debug/bugfix-sprint-plan.md` | High-level sprint overview | `/debug/bugfix-sprint-plan.md` |

### Sprint Definitions (Implementation Guide)

| Document | Focus Area | Location |
|----------|------------|----------|
| `debug/sprint/README.md` | Sprint index and execution guide | `/debug/sprint/README.md` |
| `debug/sprint/sprint-01-*.md` | Security Foundation | `/debug/sprint/sprint-01-security-foundation.md` |
| `debug/sprint/sprint-02-*.md` | Kubernetes Integration | `/debug/sprint/sprint-02-kubernetes-integration.md` |
| `debug/sprint/sprint-03-*.md` | Prometheus Authentication | `/debug/sprint/sprint-03-prometheus-auth.md` |
| `debug/sprint/sprint-04-*.md` | Logs & Traces | `/debug/sprint/sprint-04-logs-traces.md` |
| `debug/sprint/sprint-05-*.md` | GPU Telemetry | `/debug/sprint/sprint-05-gpu-telemetry.md` |
| `debug/sprint/sprint-06-*.md` | CNF Monitoring | `/debug/sprint/sprint-06-cnf-monitoring.md` |
| `debug/sprint/sprint-07-*.md` | WebSocket Hardening | `/debug/sprint/sprint-07-websocket-hardening.md` |
| `debug/sprint/sprint-08-*.md` | Anomaly Detection & RCA | `/debug/sprint/sprint-08-anomaly-rca.md` |
| `debug/sprint/sprint-09-*.md` | Reports & MCP Tools | `/debug/sprint/sprint-09-reports-mcp.md` |
| `debug/sprint/sprint-10-*.md` | API Gateway Polish | `/debug/sprint/sprint-10-api-gateway-polish.md` |

### Development Guide

| Document | Purpose | Location |
|----------|---------|----------|
| `CLAUDE.md` | AI assistant context and commands | `/CLAUDE.md` |

---

## 3. Development Principles

### 3.1 Specification Compliance

```
RULE: The specs/ folder is the source of truth.
      If code contradicts spec, the code is wrong.
```

Before implementing any feature:
1. Read the relevant spec section
2. Understand the data models from `specs/01-data-models.md`
3. Check integration patterns in `specs/08-integration-matrix.md`
4. Verify deployment requirements in `specs/09-deployment.md`

### 3.2 Air-Gapped Ready Design

```
RULE: All features MUST work in air-gapped environments.
      Local vLLM is preferred over external APIs.
```

- Never hardcode external API dependencies
- Always provide local alternatives
- Use environment variables for all external URLs
- Container images must be pullable from private registries

### 3.3 Security First

```
RULE: Security is not optional. Every endpoint MUST be authenticated.
      Every operation MUST be authorized.
```

- OAuth 2.0 via OpenShift for authentication
- RBAC with admin/operator/viewer roles
- Credentials stored in Kubernetes Secrets only
- No secrets in environment variables or config files

### 3.4 No Mock Data in Production Code

```
RULE: Remove ALL mock data patterns.
      Every function must interact with real systems.
```

Search for and eliminate:
- `# For sandbox testing`
- `# Mock data`
- `return []  # TODO`
- Hardcoded metric values
- Fake GPU data

### 3.5 Observability Built-In

```
RULE: Every service must emit logs, metrics, and traces.
```

- Structured JSON logging via structlog
- Prometheus metrics on `/metrics`
- OpenTelemetry traces to OTLP collector
- Health endpoints on `/health` and `/ready`

---

## 4. OpenShift Sandbox Environment

### 4.1 Mandatory Sandbox Testing

```
RULE: ALL code changes MUST be tested on the OpenShift sandbox environment
      before being considered complete. Local-only testing is NOT sufficient.
```

The AIOps NextGen platform runs on OpenShift. Every sprint task must be validated against the live sandbox cluster to ensure:
- Kubernetes API interactions work correctly
- Service-to-service communication functions
- Database and Redis connections are stable
- OAuth/RBAC integrations are operational

### 4.2 Agent Sandbox Credential Protocol

**IMPORTANT FOR AI AGENTS:**

Before starting any development or testing work, the agent MUST:

1. **Ask the user for sandbox environment details:**
   ```
   "To proceed with development and testing, I need access to the OpenShift sandbox.
   Please provide:
   1. Path to your kubeconfig file (e.g., /Users/fenar/projects/clusters/sandbox01/kubeconfig)
   2. OpenShift API URL (e.g., https://api.sandbox01.narlabs.io:6443)
   3. Project/namespace name (e.g., aiops-nextgen)

   Once provided, I will verify cluster connectivity and pod status."
   ```

2. **Store and use the credentials throughout the session**

3. **Never hardcode or persist credentials beyond the session**

### 4.3 Sandbox Environment Setup

Once credentials are provided, set up the environment:

```bash
# Set the KUBECONFIG environment variable
export KUBECONFIG=/path/to/kubeconfig

# Verify cluster connectivity
oc whoami
oc project aiops-nextgen

# Check current pod status
oc get pods

# Expected services (all should be Running):
# - api-gateway-*
# - cluster-registry-*
# - intelligence-engine-*
# - observability-collector-*
# - realtime-streaming-*
# - postgresql-*
# - redis-*
```

### 4.4 Service Health Verification

Before starting a new development phase/sprint, verify all existing ocp artificacts are cleaned up and  aiops-nextgen ns is a clean slate :

```bash
# Check pod status
oc get deployments
oc get pods -o wide

# Check service endpoints
oc get svc

# Verify routes are accessible
oc get routes


```

### 4.5 Common Pod Issues and Resolution

| Status | Meaning | Resolution |
|--------|---------|------------|
| `Running` | Healthy | No action needed |
| `CreateContainerConfigError` | Missing ConfigMap/Secret | Check `oc describe pod <name>` for missing refs |
| `CrashLoopBackOff` | Application crash | Check `oc logs <pod>` for errors |
| `ImagePullBackOff` | Cannot pull image | Verify image exists and registry credentials |
| `Pending` | Waiting for resources | Check node resources or PVC status |

**Example: Fix CreateContainerConfigError**
```bash
# Identify the issue
oc describe pod intelligence-engine-67f84c6675-fw2fn | grep -A5 "Events:"

# Common fix: Create missing secret
oc create secret generic llm-credentials \
  --from-literal=LLM_PROVIDER=local \
  --from-literal=LLM_LOCAL_URL=http://vllm:8080/v1

# Restart the deployment
oc rollout restart deployment/intelligence-engine
```

### 4.6 Deploying Code Changes to Sandbox

After implementing and locally testing code changes:

```bash
# 1. Build the new container image
cd src/<service>
docker build -t quay.io/aiops-nextgen/<service>:dev .

# 2. Push to registry (if using external registry)
docker push quay.io/aiops-nextgen/<service>:dev

# 3. Update the deployment image
oc set image deployment/<service> <service>=quay.io/aiops-nextgen/<service>:dev

# 4. Watch the rollout
oc rollout status deployment/<service>

# 5. Verify the new pod is running
oc get pods -l app=<service>

# 6. Check logs for startup errors
oc logs -l app=<service> --tail=100 -f
```

### 4.7 Integration Testing on Sandbox

After deploying changes, run integration tests:

```bash
# Get the route URL for the API gateway
export API_URL=$(oc get route api-gateway -o jsonpath='{.spec.host}')

# Test health endpoints
curl -s https://$API_URL/health | jq
curl -s https://$API_URL/ready | jq

# Test API endpoints (with auth token if required)
curl -s https://$API_URL/api/v1/clusters | jq

# Port-forward for direct service testing
oc port-forward svc/cluster-registry 8080:8080 &
curl -s http://localhost:8080/health | jq

# Run pytest against sandbox (with sandbox URL configured)
SANDBOX_API_URL=https://$API_URL pytest tests/integration/ -v
```

### 4.8 Debugging on Sandbox

```bash
# Stream logs from a specific pod
oc logs -f deployment/<service>

# Get shell access to a pod
oc exec -it deployment/<service> -- /bin/sh

# Check environment variables
oc exec deployment/<service> -- env | sort

# Check mounted secrets/configmaps
oc exec deployment/<service> -- ls -la /etc/secrets/

# Debug networking
oc exec deployment/<service> -- curl -s http://cluster-registry:8080/health

# Check database connectivity
oc exec deployment/postgresql -- psql -U aiops -d aiops -c "SELECT 1;"

# Check Redis connectivity
oc exec deployment/redis -- redis-cli ping
```

### 4.9 Sandbox Environment Variables

Services require these environment variables (configured via ConfigMaps/Secrets):

| Variable | Description | Example |
|----------|-------------|---------|
| `POSTGRES_HOST` | PostgreSQL hostname | `postgresql` |
| `POSTGRES_PORT` | PostgreSQL port | `5432` |
| `POSTGRES_USER` | Database user | `aiops` |
| `POSTGRES_PASSWORD` | Database password | (from secret) |
| `POSTGRES_DATABASE` | Database name | `aiops` |
| `REDIS_HOST` | Redis hostname | `redis` |
| `REDIS_PORT` | Redis port | `6379` |
| `OAUTH_ISSUER` | OpenShift OAuth URL | `https://oauth-openshift.apps...` |
| `LLM_PROVIDER` | LLM provider type | `local` |
| `LLM_LOCAL_URL` | vLLM server URL | `http://vllm:8080/v1` |

### 4.10 Sprint Task Completion Checklist (Sandbox)

For each sprint task, verify on sandbox:

- [ ] Code deployed to sandbox cluster
- [ ] Pod running without errors
- [ ] Health endpoint returning healthy
- [ ] API endpoints responding correctly
- [ ] Integration with other services working
- [ ] Logs show expected behavior
- [ ] No error events in pod events

---

## 5. Sprint Execution Protocol

### 5.1 Pre-Sprint Checklist

Before starting any sprint:

- [ ] Read the sprint document completely
- [ ] Verify all dependency sprints are completed
- [ ] Read relevant spec sections referenced in the sprint
- [ ] Understand the issues being addressed (check `debug/issues.md`)
- [ ] Create feature branch from `main`
- [ ] Set up local development environment

### 5.2 Sprint Execution Order

**CRITICAL: Execute sprints in this exact order. Do not skip or reorder.**

```
Phase 1: Security Foundation (BLOCKING)
├── Sprint 1: OAuth + RBAC + WebSocket Auth
└── Sprint 2: K8s Secrets + Credential Validation + Discovery

Phase 2: Observability Stack
├── Sprint 3: Prometheus Authentication
├── Sprint 4: Loki + Tempo Collectors
├── Sprint 5: Real GPU Telemetry
└── Sprint 6: CNF Monitoring (PTP, SR-IOV)

Phase 3: Real-Time & Intelligence
├── Sprint 7: WebSocket Hardening
└── Sprint 8: Anomaly Detection + RCA

Phase 4: Completion
├── Sprint 9: Reports + MCP Tools
└── Sprint 10: Chat Persistence + Tracing
```

### 5.3 Task Execution Within Sprint

For each task in a sprint:

1. **Read the Task Section**
   - Understand the file to create/modify
   - Note the spec references

2. **Implement the Code**
   - Copy the code from the sprint document
   - Adapt only if necessary (explain why in commit)
   - Add any missing imports

3. **Write Tests**
   - Implement the test file provided
   - Add edge cases not covered
   - Ensure >80% coverage for the file

4. **Verify Locally**
   ```bash
   # Lint the code
   ruff check src/<service>/

   # Run tests
   pytest src/<service>/tests/test_<module>.py -v

   # Type check (optional but recommended)
   mypy src/<service>/<module>.py
   ```

5. **Mark Task Complete**
   - Update sprint progress tracking
   - Note any deviations or issues

### 5.4 Post-Sprint Verification

After completing all tasks in a sprint:

- [ ] All acceptance criteria checked and passing
- [ ] All tests passing with >80% coverage
- [ ] No linting errors
- [ ] API documentation updated if endpoints changed
- [ ] Integration test with dependent services
- [ ] PR created and reviewed

---

## 6. Code Implementation Standards

### 6.1 File Structure

```
src/<service>/
├── __init__.py           # Package init with version
├── main.py               # FastAPI application entry
├── api/
│   ├── __init__.py
│   └── v1/
│       ├── __init__.py
│       └── <resource>.py # API endpoints
├── services/
│   ├── __init__.py
│   └── <service>.py      # Business logic
├── clients/
│   ├── __init__.py
│   └── <client>.py       # External service clients
├── middleware/
│   ├── __init__.py
│   └── <middleware>.py   # Request/response middleware
├── models/
│   ├── __init__.py
│   └── <models>.py       # Service-specific models
└── tests/
    ├── __init__.py
    ├── conftest.py       # Pytest fixtures
    └── test_<module>.py  # Test files
```

### 6.2 Import Order

```python
# Standard library
from datetime import datetime
from typing import Optional

# Third-party
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Shared package
from shared.models import Cluster
from shared.config import get_settings
from shared.observability import get_logger

# Local
from services.my_service import my_function
```

### 6.3 Logging Standards

```python
from shared.observability import get_logger

logger = get_logger(__name__)

# Use structured logging
logger.info(
    "Operation completed",
    operation="create_cluster",
    cluster_id=cluster_id,
    duration_ms=duration,
)

# Log levels:
# - DEBUG: Detailed debugging (not in production)
# - INFO: Normal operations
# - WARNING: Unexpected but handled situations
# - ERROR: Failures requiring attention
```

### 6.4 Error Handling

```python
from fastapi import HTTPException, status

# Always use appropriate HTTP status codes
raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail=f"Cluster {cluster_id} not found",
)

# Standard error responses
# 400 - Bad Request (invalid input)
# 401 - Unauthorized (missing/invalid auth)
# 403 - Forbidden (insufficient permissions)
# 404 - Not Found (resource doesn't exist)
# 500 - Internal Server Error (unexpected failure)
```

### 6.5 Async Patterns

```python
# Always use async for I/O operations
async def get_cluster(cluster_id: str) -> Cluster:
    async with get_async_session() as db:
        result = await db.execute(
            select(ClusterORM).where(ClusterORM.id == cluster_id)
        )
        return result.scalar_one_or_none()

# Use asyncio.gather for concurrent operations
results = await asyncio.gather(
    get_metrics(cluster_id),
    get_logs(cluster_id),
    get_traces(cluster_id),
)
```

### 6.6 Configuration Access

```python
from shared.config import get_settings

# Always use get_settings() - it's cached
settings = get_settings()

# Access nested settings
db_url = settings.database.async_url
redis_url = settings.redis.url
llm_provider = settings.llm.provider
```

---

## 7. Testing Requirements

### 7.1 Test Structure

```python
"""Tests for <module>."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from <module> import <Class>, <function>


@pytest.fixture
def sample_data():
    """Provide sample test data."""
    return {...}


class TestClassName:
    """Tests for ClassName."""

    async def test_method_success(self, sample_data):
        """Test successful method execution."""
        # Arrange
        ...
        # Act
        result = await method(sample_data)
        # Assert
        assert result.status == "success"

    async def test_method_failure(self):
        """Test method failure handling."""
        with pytest.raises(HTTPException) as exc_info:
            await method(invalid_data)
        assert exc_info.value.status_code == 400
```

### 7.2 Coverage Requirements

| Category | Minimum Coverage |
|----------|-----------------|
| Services | 80% |
| API Endpoints | 80% |
| Middleware | 90% |
| Clients | 70% |
| Models | 100% |

### 7.3 Running Tests

```bash
# Run all tests for a service
pytest src/<service>/tests/ -v

# Run with coverage
pytest src/<service>/tests/ --cov=src/<service> --cov-report=html

# Run specific test file
pytest src/<service>/tests/test_<module>.py -v

# Run tests matching pattern
pytest -k "test_auth" -v
```

---

## 8. Git Workflow

### 8.1 Branch Naming

```
feature/sprint-XX-brief-description
bugfix/issue-XXX-brief-description
hotfix/critical-issue-description
```

### 8.2 Commit Messages

```
<type>(<scope>): <description>

[optional body]

[optional footer]

Types: feat, fix, docs, style, refactor, test, chore
Scope: service name or component
```

Examples:
```
feat(api-gateway): implement OAuth middleware

- Add OAuth 2.0 token validation
- Integrate with OpenShift OAuth provider
- Cache JWKS with 1-hour TTL

Resolves: ISSUE-010
```

### 8.3 Pull Request Template

```markdown
## Summary
Brief description of changes

## Issues Addressed
- ISSUE-XXX: Description
- ISSUE-YYY: Description

## Sprint Reference
Sprint X: [Sprint Name](debug/sprint/sprint-XX-name.md)

## Changes
- [ ] File 1: Description
- [ ] File 2: Description

## Testing
- [ ] Unit tests passing
- [ ] Integration tests passing
- [ ] Manual testing completed

## Acceptance Criteria
- [ ] Criteria 1 from sprint doc
- [ ] Criteria 2 from sprint doc

## Rollback Plan
Steps to rollback if issues arise
```

---

## 9. Quality Gates

### 9.1 Pre-Commit Checks

Every commit must pass:
```bash
# Linting
ruff check src/

# Formatting
black --check src/

# Type checking (if configured)
mypy src/

# Tests
pytest src/<service>/tests/
```

### 9.2 PR Merge Requirements

- [ ] All CI checks passing
- [ ] Code review approved (1+ approver)
- [ ] No merge conflicts
- [ ] Branch up to date with main
- [ ] All acceptance criteria verified
- [ ] Documentation updated if needed

### 9.3 Sprint Completion Gate

Before marking a sprint complete:
- [ ] All tasks implemented
- [ ] All tests passing (>80% coverage)
- [ ] All acceptance criteria checked
- [ ] Integration tested with dependent services
- [ ] No regression in existing functionality
- [ ] PR merged to main

---

## 10. Troubleshooting

### 10.1 Common Issues

**Import Errors**
```bash
# Ensure shared package is installed
pip install -e src/shared/
```

**Database Connection Failed**
```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Verify connection string
echo $POSTGRES_HOST $POSTGRES_PORT $POSTGRES_DATABASE
```

**Redis Connection Failed**
```bash
# Check Redis is running
docker-compose ps redis

# Test connection
redis-cli -h localhost ping
```

**OAuth Validation Failed**
```bash
# Verify OAuth issuer is accessible
curl -s $OAUTH_ISSUER/.well-known/oauth-authorization-server | jq
```

### 10.2 Debug Mode

```bash
# Run with debug logging
LOG_LEVEL=DEBUG python -m uvicorn main:app --reload

# Enable SQL query logging
SQLALCHEMY_ECHO=true python -m uvicorn main:app
```

### 10.3 Getting Help

1. Check the relevant spec document
2. Review the sprint document for implementation details
3. Search existing issues in `debug/issues.md`
4. Check `CLAUDE.md` for AI assistant context

---

## 11. Reference Quick Links

### Specifications
- [Architecture Overview](specs/00-overview.md)
- [Data Models](specs/01-data-models.md)
- [Cluster Registry](specs/02-cluster-registry.md)
- [Observability Collector](specs/03-observability-collector.md)
- [Intelligence Engine](specs/04-intelligence-engine.md)
- [Realtime Streaming](specs/05-realtime-streaming.md)
- [API Gateway](specs/06-api-gateway.md)
- [Integration Matrix](specs/08-integration-matrix.md)
- [Deployment](specs/09-deployment.md)

### Debug & Sprint
- [Issues List](debug/issues.md)
- [Sprint Plan Overview](debug/bugfix-sprint-plan.md)
- [Sprint Index](debug/sprint/README.md)

### Development
- [Claude AI Context](CLAUDE.md)
- [Main README](README.md)

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2024-12-29 | Claude | Initial version |

---

**Remember: The specs/ folder is sacred. When in doubt, read the spec.**
