# Sprint 10: API Gateway Polish

**Status:** COMPLETED
**Theme:** Production hardening and observability
**Priority:** P3 - Medium

## Overview

Sprint 10 focuses on production-readiness features for the API Gateway:
- Chat session persistence to PostgreSQL
- Aggregated health checks with component latencies
- Request validation middleware
- Distributed tracing integration

## Deliverables

### 1. Chat Persistence Service

**File:** `src/intelligence-engine/app/services/chat_persistence.py`

Implements write-through caching strategy:
- PostgreSQL as source of truth
- Redis as cache layer
- Async SQLAlchemy integration

```python
class ChatPersistenceService:
    """Service for persisting chat sessions to PostgreSQL."""

    async def save_session(session: ChatSession) -> ChatSession
    async def get_session(session_id: UUID) -> ChatSession | None
    async def list_sessions(user_id: str, limit: int = 50) -> list[ChatSession]
    async def delete_session(session_id: UUID) -> bool
    async def save_message(message: ChatMessage) -> ChatMessage
    async def get_messages(session_id: UUID, limit: int = 100) -> list[ChatMessage]
```

### 2. Aggregated Health Check

**File:** `src/api-gateway/app/api/health.py`

Enhanced `/health/detailed` endpoint that checks:
- All backend services (cluster-registry, observability-collector, intelligence-engine, realtime-streaming)
- Redis connectivity and latency
- PostgreSQL connectivity (via intelligence-engine)

Response format:
```json
{
    "status": "healthy | degraded",
    "components": {
        "cluster-registry": {"status": "healthy", "latency_ms": 5},
        "observability-collector": {"status": "healthy", "latency_ms": 8},
        "intelligence-engine": {"status": "healthy", "latency_ms": 12},
        "realtime-streaming": {"status": "healthy", "latency_ms": 6},
        "redis": {"status": "healthy", "latency_ms": 2},
        "postgresql": {"status": "healthy", "latency_ms": 15}
    },
    "uptime_seconds": 3600
}
```

### 3. Request Validation Middleware

**File:** `src/api-gateway/app/middleware/validation.py`

Features:
- Content-Type validation for POST/PUT/PATCH
- Request body size limits per endpoint pattern
- Required field validation per endpoint
- Field type validators
- Detailed 422 error responses

Size limits:
- `/api/v1/chat/`: 64KB
- `/api/v1/reports/`: 16KB
- `/api/v1/clusters/`: 128KB
- Default: 1MB

Error response format:
```json
{
    "detail": "Validation Error",
    "errors": [
        {"field": "name", "message": "Field 'name' is required"},
        {"field": "cluster_id", "message": "Invalid value for field 'cluster_id'", "value": "..."}
    ]
}
```

### 4. Distributed Tracing Middleware

**File:** `src/api-gateway/app/middleware/tracing.py`

Features:
- W3C Trace Context support (traceparent, tracestate)
- B3 headers support (Zipkin compatibility)
- Automatic span creation for all requests
- Context propagation to downstream services
- Request ID header support

Headers:
- `traceparent`: W3C trace context
- `tracestate`: W3C trace state
- `x-request-id`: Request correlation ID
- `x-b3-traceid`, `x-b3-spanid`, `x-b3-sampled`: B3 compatibility

Usage for downstream calls:
```python
from app.middleware.tracing import inject_trace_headers

# Add trace headers to outgoing requests
headers = inject_trace_headers(existing_headers)
response = await http_client.get(url, headers=headers)
```

## Files Created/Modified

| File | Action | Description |
|------|--------|-------------|
| `src/intelligence-engine/app/services/chat_persistence.py` | Created | PostgreSQL persistence layer |
| `src/api-gateway/app/middleware/validation.py` | Created | Request validation middleware |
| `src/api-gateway/app/middleware/tracing.py` | Created | Distributed tracing middleware |
| `src/api-gateway/app/api/health.py` | Modified | Added PostgreSQL health check |
| `src/api-gateway/app/middleware/__init__.py` | Modified | Export new middleware |
| `src/api-gateway/app/main.py` | Modified | Register new middleware |
| `src/intelligence-engine/app/api/health.py` | Modified | Added `/health/db` endpoint |
| `src/intelligence-engine/app/services/__init__.py` | Modified | Export persistence service |

## Acceptance Criteria

- [x] Chat sessions persist across restarts (via PostgreSQL)
- [x] `/health/detailed` shows all component status with latencies
- [x] Invalid requests rejected with 422 and detailed errors
- [x] Traces propagated through gateway to backends
- [x] Trace context extracted from incoming requests
- [x] Request size limits enforced per endpoint

## Middleware Order

Middleware is applied in reverse order (last added = first to process):

1. **TracingMiddleware** (outermost) - Creates trace context
2. **RequestValidationMiddleware** - Validates request bodies
3. **RateLimitMiddleware** - Enforces rate limits
4. **AuthenticationMiddleware** - Validates OAuth tokens
5. **CORSMiddleware** (innermost) - Handles CORS headers

## Database Schema

Uses existing models from `src/shared/database/models.py`:
- `ChatSessionModel` - Chat session metadata
- `ChatMessageModel` - Individual messages with tool calls/results

## Configuration

No new configuration required. Uses existing:
- `POSTGRES_*` environment variables for database
- `REDIS_*` environment variables for caching
- `SERVICE_*` URLs for backend health checks

## Testing

```bash
# Test health endpoint
curl http://localhost:8080/health/detailed

# Test validation (should return 422)
curl -X POST http://localhost:8080/api/v1/clusters \
  -H "Content-Type: application/json" \
  -d '{}'

# Test tracing headers
curl -v http://localhost:8080/api/v1/clusters \
  -H "traceparent: 00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
```
