# 06 - API Gateway Service

## Document Info
| Field | Value |
|-------|-------|
| Version | 0.1.0 |
| Status | Draft |
| Last Updated | 2024-12-24 |

---

## 1. Purpose

The API Gateway serves as the single entry point for all external requests. It handles:

- Request routing to backend services
- Authentication via OpenShift OAuth
- Authorization and RBAC
- Rate limiting
- Request/response transformation
- API versioning
- OpenAPI documentation

---

## 2. Responsibilities

| Responsibility | Description |
|----------------|-------------|
| **Routing** | Route requests to appropriate backend services |
| **Authentication** | Validate JWT tokens from OpenShift OAuth |
| **Authorization** | Enforce RBAC policies |
| **Rate Limiting** | Protect services from overload |
| **Transformation** | Request/response transformation |
| **Documentation** | Serve OpenAPI specs |
| **Health Aggregation** | Aggregate health from all services |

---

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API GATEWAY                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                      Entry Points                                      │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │ │
│  │  │ REST API     │  │ WebSocket    │  │ MCP Protocol │                  │ │
│  │  │ /api/v1/*    │  │ /ws          │  │ /mcp         │                  │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                  │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                      │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                      Middleware Stack                                  │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │ │
│  │  │ Auth         │  │ Rate Limit   │  │ Request      │                  │ │
│  │  │ Middleware   │  │ Middleware   │  │ Validation   │                  │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                  │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │ │
│  │  │ CORS         │  │ Logging      │  │ Tracing      │                  │ │
│  │  │ Middleware   │  │ Middleware   │  │ Middleware   │                  │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                  │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                      │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         Router                                         │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐  │ │
│  │  │                    Route Table                                   │  │ │
│  │  │                                                                  │  │ │
│  │  │  /api/v1/clusters/*     → Cluster Registry                       │  │ │
│  │  │  /api/v1/metrics/*      → Observability Collector                │  │ │
│  │  │  /api/v1/traces/*       → Observability Collector                │  │ │
│  │  │  /api/v1/logs/*         → Observability Collector                │  │ │
│  │  │  /api/v1/alerts/*       → Observability Collector                │  │ │
│  │  │  /api/v1/gpu/*          → Observability Collector                │  │ │
│  │  │  /api/v1/chat/*         → Intelligence Engine                    │  │ │
│  │  │  /api/v1/personas/*     → Intelligence Engine                    │  │ │
│  │  │  /api/v1/analysis/*     → Intelligence Engine                    │  │ │
│  │  │  /api/v1/reports/*      → Intelligence Engine                    │  │ │
│  │  │  /mcp                   → Intelligence Engine                    │  │ │
│  │  │  /ws                    → Real-Time Streaming                    │  │ │
│  │  │                                                                  │  │ │
│  │  └──────────────────────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          ▼                           ▼                           ▼
  ┌───────────────┐          ┌───────────────┐          ┌───────────────┐
  │ Cluster       │          │ Observability │          │ Intelligence  │
  │ Registry      │          │ Collector     │          │ Engine        │
  └───────────────┘          └───────────────┘          └───────────────┘
                                                                  │
                                                                  ▼
                                                        ┌───────────────┐
                                                        │ Real-Time     │
                                                        │ Streaming     │
                                                        └───────────────┘
```

---

## 4. API Structure

### 4.1 Base URL

```
https://aiops.example.com/api/v1
```

### 4.2 Route Mapping

| Path Prefix | Backend Service | Description |
|-------------|-----------------|-------------|
| `/api/v1/clusters` | Cluster Registry | Cluster management |
| `/api/v1/fleet` | Cluster Registry | Fleet operations |
| `/api/v1/metrics` | Observability Collector | Prometheus queries |
| `/api/v1/traces` | Observability Collector | Tempo queries |
| `/api/v1/logs` | Observability Collector | Loki queries |
| `/api/v1/alerts` | Observability Collector | Alertmanager |
| `/api/v1/gpu` | Observability Collector | GPU telemetry |
| `/api/v1/cnf` | Observability Collector | CNF metrics |
| `/api/v1/chat` | Intelligence Engine | AI chat |
| `/api/v1/personas` | Intelligence Engine | Persona management |
| `/api/v1/analysis` | Intelligence Engine | Anomaly/RCA |
| `/api/v1/reports` | Intelligence Engine | Report generation |
| `/mcp` | Intelligence Engine | MCP protocol |
| `/ws` | Real-Time Streaming | WebSocket |
| `/api/v1/streaming` | Real-Time Streaming | Streaming admin/status |

### 4.3 Public Endpoints (No Auth)

| Path | Description |
|------|-------------|
| `/health` | Gateway health check |
| `/ready` | Gateway readiness |
| `/docs` | OpenAPI documentation |
| `/openapi.json` | OpenAPI spec |

### 4.4 Internal Endpoints

| Path | Description |
|------|-------------|
| `/auth/validate` | Token validation for internal services (e.g., WebSocket auth) |

---

## 5. Authentication

### 5.1 OpenShift OAuth Integration

```
┌─────────┐     ┌─────────────┐     ┌───────────────┐
│ Client  │────►│ API Gateway │────►│ OpenShift     │
│         │     │             │     │ OAuth Server  │
│         │◄────│             │◄────│               │
└─────────┘     └─────────────┘     └───────────────┘
     │                                      │
     │         OAuth Flow                   │
     │  1. Redirect to OAuth               │
     │  2. User authenticates              │
     │  3. Callback with code              │
     │  4. Exchange code for token         │
     │  5. JWT token issued                │
     └──────────────────────────────────────┘
```

### 5.2 Token Validation

```python
class OAuthMiddleware:
    async def validate_token(self, token: str) -> UserInfo:
        """
        Validate JWT token against OpenShift OAuth.

        1. Decode JWT (without verification for claims)
        2. Call OpenShift token review API
        3. Return user info if valid
        4. Raise 401 if invalid
        """
```

### 5.3 Service Account Authentication

```yaml
# For internal service-to-service calls
Authorization: Bearer <service-account-token>

# Token from mounted secret
/var/run/secrets/kubernetes.io/serviceaccount/token
```

---

## 6. Authorization

### 6.1 RBAC Model

```yaml
# Roles
roles:
  - name: admin
    description: Full access to all resources
    permissions:
      - "clusters:*"
      - "metrics:*"
      - "chat:*"
      - "reports:*"

  - name: operator
    description: Read/write access to observability, read-only clusters
    permissions:
      - "clusters:read"
      - "metrics:*"
      - "chat:*"
      - "reports:read"

  - name: viewer
    description: Read-only access
    permissions:
      - "clusters:read"
      - "metrics:read"
      - "chat:read"
      - "reports:read"

# Permission format: resource:action
# Actions: read, write, delete, * (all)
```

### 6.2 Cluster-Scoped Access

```python
class ClusterAccessMiddleware:
    async def filter_clusters(
        self,
        user: UserInfo,
        requested_clusters: List[UUID]
    ) -> List[UUID]:
        """
        Filter clusters based on user's namespace access.

        Uses OpenShift SubjectAccessReview to verify access.
        """
```

---

## 7. Rate Limiting

### 7.1 Configuration

```yaml
rate_limiting:
  enabled: true

  # Global limits
  global:
    requests_per_second: 1000
    burst: 100

  # Per-user limits
  per_user:
    requests_per_minute: 300
    burst: 50

  # Per-endpoint limits
  endpoints:
    "/api/v1/metrics/query":
      requests_per_minute: 60
      burst: 10
    "/api/v1/chat/sessions/*/messages":
      requests_per_minute: 30
      burst: 5
    "/api/v1/reports":
      requests_per_minute: 10
      burst: 2
```

### 7.2 Rate Limit Headers

```http
HTTP/1.1 200 OK
X-RateLimit-Limit: 300
X-RateLimit-Remaining: 295
X-RateLimit-Reset: 1703412000

# When exceeded:
HTTP/1.1 429 Too Many Requests
Retry-After: 60
```

---

## 8. Request Validation

### 8.1 Schema Validation

```python
class RequestValidator:
    async def validate(
        self,
        request: Request,
        schema: JSONSchema
    ) -> ValidationResult:
        """
        Validate request body against JSON schema.

        Returns ValidationResult with errors if invalid.
        """
```

### 8.2 Query Parameter Validation

```python
# Example validation rules
class QueryParams:
    page: int = Field(ge=1, default=1)
    page_size: int = Field(ge=1, le=100, default=20)
    cluster_id: Optional[UUID] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @validator('end_time')
    def end_after_start(cls, v, values):
        if v and values.get('start_time') and v < values['start_time']:
            raise ValueError('end_time must be after start_time')
        return v
```

---

## 9. API Versioning

### 9.1 URL Versioning

```
/api/v1/clusters     # Current version
/api/v2/clusters     # Future version (when needed)
```

### 9.2 Version Header

```http
# Optional header for version negotiation
Accept: application/vnd.aiops.v1+json
```

### 9.3 Deprecation Headers

```http
# When v1 is deprecated
Deprecation: true
Sunset: Sat, 01 Jun 2025 00:00:00 GMT
Link: </api/v2/clusters>; rel="successor-version"
```

---

## 10. Error Responses

### 10.1 Standard Error Format

```json
{
  "error": {
    "code": "CLUSTER_NOT_FOUND",
    "message": "Cluster with ID 550e8400-e29b-41d4-a716-446655440000 not found",
    "details": {
      "cluster_id": "550e8400-e29b-41d4-a716-446655440000"
    },
    "trace_id": "abc123-def456-ghi789",
    "timestamp": "2024-12-24T10:00:00Z"
  }
}
```

### 10.2 HTTP Status Codes

| Code | Meaning | Usage |
|------|---------|-------|
| 200 | OK | Successful GET, PUT |
| 201 | Created | Successful POST |
| 204 | No Content | Successful DELETE |
| 400 | Bad Request | Invalid request body/params |
| 401 | Unauthorized | Missing/invalid token |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource not found |
| 409 | Conflict | Resource already exists |
| 422 | Unprocessable | Validation failed |
| 429 | Too Many Requests | Rate limited |
| 500 | Internal Error | Server error |
| 502 | Bad Gateway | Backend unavailable |
| 503 | Service Unavailable | Service overloaded |
| 504 | Gateway Timeout | Backend timeout |

---

## 11. Observability

### 11.1 Request Logging

```json
{
  "timestamp": "2024-12-24T10:00:00Z",
  "level": "info",
  "message": "request_completed",
  "method": "GET",
  "path": "/api/v1/clusters",
  "status": 200,
  "duration_ms": 45,
  "user_id": "user@example.com",
  "trace_id": "abc123-def456",
  "client_ip": "10.0.0.1",
  "user_agent": "Mozilla/5.0..."
}
```

### 11.2 Distributed Tracing

```python
class TracingMiddleware:
    async def process_request(self, request: Request):
        """
        Inject/extract trace context.

        - Extract trace-id from incoming request
        - Create span for gateway processing
        - Propagate to backend services
        """
```

### 11.3 Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `gateway_requests_total` | Counter | Total requests (by path, method, status) |
| `gateway_request_duration_seconds` | Histogram | Request latency |
| `gateway_active_requests` | Gauge | Current in-flight requests |
| `gateway_rate_limit_hits_total` | Counter | Rate limit rejections |
| `gateway_auth_failures_total` | Counter | Authentication failures |
| `gateway_backend_errors_total` | Counter | Backend service errors |

---

## 12. Health Checks

### 12.1 Gateway Health

```http
GET /health

{
  "status": "healthy",
  "version": "1.0.0",
  "uptime_seconds": 86400
}
```

### 12.2 Aggregated Health

```http
GET /health/detailed

{
  "status": "healthy",
  "components": {
    "cluster_registry": {
      "status": "healthy",
      "latency_ms": 5
    },
    "observability_collector": {
      "status": "healthy",
      "latency_ms": 8
    },
    "intelligence_engine": {
      "status": "healthy",
      "latency_ms": 12
    },
    "realtime_streaming": {
      "status": "healthy",
      "latency_ms": 3
    },
    "redis": {
      "status": "healthy",
      "latency_ms": 1
    },
    "postgresql": {
      "status": "healthy",
      "latency_ms": 2
    }
  }
}
```

---

## 13. Configuration

```yaml
api_gateway:
  # Server
  host: "0.0.0.0"
  port: 8080

  # TLS (terminated at OpenShift Route typically)
  tls:
    enabled: false

  # Authentication
  auth:
    oauth_issuer: "https://oauth-openshift.apps.example.com"
    oauth_client_id: "aiops-gateway"
    oauth_client_secret_ref: "oauth-client-secret"
    token_validation_cache_seconds: 60

  # Rate limiting
  rate_limiting:
    enabled: true
    redis_url: "redis://redis:6379/1"
    global_rps: 1000
    per_user_rpm: 300

  # Backend services
  backends:
    cluster_registry:
      url: "http://cluster-registry:8080"
      timeout_seconds: 30
    observability_collector:
      url: "http://observability-collector:8080"
      timeout_seconds: 60
    intelligence_engine:
      url: "http://intelligence-engine:8080"
      timeout_seconds: 120
    realtime_streaming:
      url: "http://realtime-streaming:8080"
      timeout_seconds: 30

  # CORS
  cors:
    enabled: true
    origins: ["https://console.example.com"]
    methods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    headers: ["Authorization", "Content-Type"]

  # Request limits
  limits:
    max_request_body_bytes: 10485760  # 10MB
    request_timeout_seconds: 120
```

---

## 14. OpenAPI Documentation

### 14.1 Aggregated Spec

The gateway aggregates OpenAPI specs from all backend services:

```python
class OpenAPIAggregator:
    async def aggregate_specs(self) -> dict:
        """
        Fetch and merge OpenAPI specs from all backends.

        - Prefix paths with backend route
        - Merge schemas
        - Add gateway-level info
        """
```

### 14.2 Documentation UI

```
/docs       → Swagger UI
/redoc      → ReDoc
/openapi.json → Raw spec
```

---

## 15. Dependencies

### 15.1 Internal Dependencies

| Dependency | Purpose |
|------------|---------|
| All backend services | Request routing |
| Redis | Rate limiting, caching |

### 15.2 External Dependencies

| Dependency | Purpose |
|------------|---------|
| OpenShift OAuth | Authentication |

---

## 16. Open Questions

1. **API Keys**: Support API keys for non-interactive clients?
2. **GraphQL**: Add GraphQL endpoint for flexible queries?
3. **Request Coalescing**: Deduplicate identical concurrent requests?
4. **Circuit Breaker**: Implement circuit breaker for failing backends?
5. **Response Caching**: Cache GET responses at gateway level?

---

## Next: [07-frontend.md](./07-frontend.md)
