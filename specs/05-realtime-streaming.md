# 05 - Real-Time Streaming Service

## Document Info
| Field | Value |
|-------|-------|
| Version | 0.1.0 |
| Status | Draft |
| Last Updated | 2024-12-24 |

---

## 1. Purpose

The Real-Time Streaming Service provides live data delivery to clients via WebSocket connections. It handles:

- WebSocket connection management
- Event subscription and filtering
- Real-time metric streaming
- Alert notifications
- GPU telemetry updates
- Chat message streaming relay

---

## 2. Responsibilities

| Responsibility | Description |
|----------------|-------------|
| **Connection Management** | Handle WebSocket lifecycle (connect, disconnect, reconnect) |
| **Subscription Management** | Manage client subscriptions to event types |
| **Event Routing** | Route events from Redis to subscribed clients |
| **Metric Streaming** | Stream real-time metrics to dashboards |
| **Alert Broadcasting** | Broadcast alerts to subscribed clients |
| **Backpressure Handling** | Handle slow clients without blocking |

---

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       REAL-TIME STREAMING SERVICE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                        WebSocket Layer                                  │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │ │
│  │  │                    WebSocket Hub                                  │ │ │
│  │  │                                                                   │ │ │
│  │  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐            │ │ │
│  │  │  │Client 1 │  │Client 2 │  │Client 3 │  │Client N │            │ │ │
│  │  │  │ (WS)    │  │ (WS)    │  │ (WS)    │  │ (WS)    │            │ │ │
│  │  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘            │ │ │
│  │  │                                                                   │ │ │
│  │  │  Connection Pool │ Heartbeat Manager │ Backpressure Control     │ │ │
│  │  └──────────────────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                     Subscription Manager                                │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │ │
│  │  │                    Subscription Registry                          │ │ │
│  │  │                                                                   │ │ │
│  │  │  Client → [event_types, cluster_filter, namespace_filter]        │ │ │
│  │  │                                                                   │ │ │
│  │  │  Event Types:                                                     │ │ │
│  │  │  • CLUSTER_STATUS_CHANGED                                        │ │ │
│  │  │  • METRIC_UPDATE                                                  │ │ │
│  │  │  • ALERT_FIRED / ALERT_RESOLVED                                  │ │ │
│  │  │  • GPU_UPDATE                                                     │ │ │
│  │  │  • TRACE_RECEIVED                                                 │ │ │
│  │  │  • ANOMALY_DETECTED                                              │ │ │
│  │  │  • CHAT_MESSAGE                                                   │ │ │
│  │  └──────────────────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                       Event Router                                      │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │ │
│  │  │                                                                   │ │ │
│  │  │   Redis PubSub ──► Filter ──► Match Subscriptions ──► Dispatch   │ │ │
│  │  │                                                                   │ │ │
│  │  └──────────────────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                       Event Sources (Redis PubSub)                      │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐              │ │
│  │  │ Cluster  │  │ Observ.  │  │ Intel.   │  │ GPU      │              │ │
│  │  │ Registry │  │ Collector│  │ Engine   │  │ Collector│              │ │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘              │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. WebSocket Protocol

### 4.1 Connection Endpoint

```
ws://streaming-service:8080/ws
wss://streaming-service:8080/ws  (with TLS)
```

### 4.2 Authentication

```json
// On connection, client sends auth message
{
  "type": "auth",
  "token": "eyJhbGciOiJSUzI1NiIs..."
}

// Server responds
{
  "type": "auth_response",
  "status": "authenticated",
  "client_id": "c1234567-89ab-cdef-0123-456789abcdef"
}
```

### 4.3 Message Types

#### Client → Server

```json
// Subscribe to events
{
  "type": "subscribe",
  "subscription": {
    "event_types": ["ALERT_FIRED", "ALERT_RESOLVED", "GPU_UPDATE"],
    "cluster_filter": ["550e8400-e29b-41d4-a716-446655440000"],
    "namespace_filter": ["production", "staging"]
  }
}

// Unsubscribe
{
  "type": "unsubscribe",
  "event_types": ["GPU_UPDATE"]
}

// Ping (keepalive)
{
  "type": "ping",
  "timestamp": "2024-12-24T10:00:00Z"
}
```

#### Server → Client

```json
// Event delivery
{
  "type": "event",
  "event_id": "evt_001",
  "event_type": "ALERT_FIRED",
  "cluster_id": "550e8400-e29b-41d4-a716-446655440000",
  "cluster_name": "prod-east-1",
  "timestamp": "2024-12-24T10:00:05Z",
  "payload": {
    "fingerprint": "abc123",
    "alertname": "HighCPUUsage",
    "severity": "WARNING",
    "namespace": "production"
  }
}

// Subscription confirmation
{
  "type": "subscribed",
  "event_types": ["ALERT_FIRED", "ALERT_RESOLVED", "GPU_UPDATE"],
  "cluster_filter": ["550e8400-e29b-41d4-a716-446655440000"]
}

// Pong (keepalive response)
{
  "type": "pong",
  "timestamp": "2024-12-24T10:00:00Z",
  "server_time": "2024-12-24T10:00:00.005Z"
}

// Error
{
  "type": "error",
  "code": "INVALID_SUBSCRIPTION",
  "message": "Unknown event type: INVALID_TYPE"
}
```

---

## 5. Event Types

### 5.1 Cluster Events

```json
// CLUSTER_STATUS_CHANGED
{
  "type": "event",
  "event_type": "CLUSTER_STATUS_CHANGED",
  "cluster_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-12-24T10:00:00Z",
  "payload": {
    "old_state": "ONLINE",
    "new_state": "DEGRADED",
    "health_score": 65,
    "reason": "Prometheus endpoint unreachable"
  }
}
```

### 5.2 Alert Events

```json
// ALERT_FIRED
{
  "type": "event",
  "event_type": "ALERT_FIRED",
  "cluster_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-12-24T10:00:00Z",
  "payload": {
    "fingerprint": "abc123fingerprint",
    "alertname": "HighMemoryUsage",
    "severity": "CRITICAL",
    "labels": {
      "namespace": "production",
      "pod": "api-server-abc123"
    },
    "annotations": {
      "summary": "Memory usage above 95%"
    }
  }
}

// ALERT_RESOLVED
{
  "type": "event",
  "event_type": "ALERT_RESOLVED",
  "cluster_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-12-24T10:15:00Z",
  "payload": {
    "fingerprint": "abc123fingerprint",
    "alertname": "HighMemoryUsage",
    "duration_seconds": 900
  }
}
```

### 5.3 GPU Events

```json
// GPU_UPDATE
{
  "type": "event",
  "event_type": "GPU_UPDATE",
  "cluster_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-12-24T10:00:05Z",
  "payload": {
    "node_name": "worker-gpu-01",
    "gpus": [
      {
        "index": 0,
        "utilization_gpu_percent": 78,
        "utilization_memory_percent": 55,
        "temperature_celsius": 62,
        "power_draw_watts": 285.5
      }
    ]
  }
}
```

### 5.4 Metric Events

```json
// METRIC_UPDATE (threshold breach or significant change)
{
  "type": "event",
  "event_type": "METRIC_UPDATE",
  "cluster_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-12-24T10:00:00Z",
  "payload": {
    "metric_name": "container_cpu_usage_seconds_total",
    "labels": {
      "namespace": "production",
      "pod": "api-server-abc123"
    },
    "value": 0.92,
    "previous_value": 0.45,
    "change_percent": 104.4,
    "threshold_breached": true
  }
}
```

### 5.5 Anomaly Events

```json
// ANOMALY_DETECTED
{
  "type": "event",
  "event_type": "ANOMALY_DETECTED",
  "cluster_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-12-24T10:00:00Z",
  "payload": {
    "anomaly_id": "aa0e8400-e29b-41d4-a716-446655440005",
    "metric_name": "container_cpu_usage_seconds_total",
    "severity": "MEDIUM",
    "anomaly_type": "SPIKE",
    "confidence_score": 0.87,
    "explanation": "Unexpected 104% increase in CPU usage"
  }
}
```

### 5.6 Chat Events

```json
// CHAT_MESSAGE (for multi-user session sharing)
{
  "type": "event",
  "event_type": "CHAT_MESSAGE",
  "timestamp": "2024-12-24T10:00:00Z",
  "payload": {
    "session_id": "880e8400-e29b-41d4-a716-446655440003",
    "message_id": "990e8400-e29b-41d4-a716-446655440004",
    "role": "ASSISTANT",
    "preview": "Based on the current GPU metrics..."
  }
}
```

---

## 6. API Specification

### 6.1 REST Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/streaming/status` | Get streaming service status |
| `GET` | `/api/v1/streaming/clients` | List connected clients (admin) |
| `GET` | `/api/v1/streaming/subscriptions` | Get subscription statistics |
| `POST` | `/api/v1/streaming/broadcast` | Broadcast event (internal) |

### 6.2 WebSocket Endpoint

| Path | Description |
|------|-------------|
| `/ws` | Main WebSocket endpoint |

---

## 7. Internal Service Interfaces

### 7.1 WebSocketHub

```python
class WebSocketHub:
    """Manages WebSocket connections."""

    async def connect(
        self,
        websocket: WebSocket,
        client_id: str
    ) -> None:
        """Handle new connection."""

    async def disconnect(
        self,
        client_id: str
    ) -> None:
        """Handle disconnection."""

    async def send_to_client(
        self,
        client_id: str,
        message: dict
    ) -> bool:
        """Send message to specific client."""

    async def broadcast(
        self,
        event: Event,
        filter_func: Callable[[Subscription], bool] = None
    ) -> int:
        """Broadcast event to matching subscriptions. Returns count."""

    def get_client_count(self) -> int:
        """Get number of connected clients."""
```

### 7.2 SubscriptionManager

```python
class SubscriptionManager:
    """Manages client subscriptions."""

    async def subscribe(
        self,
        client_id: str,
        subscription: Subscription
    ) -> None:
        """Add subscription for client."""

    async def unsubscribe(
        self,
        client_id: str,
        event_types: List[str] = None
    ) -> None:
        """Remove subscriptions. If event_types is None, remove all."""

    async def get_subscriptions(
        self,
        client_id: str
    ) -> List[Subscription]:
        """Get client's subscriptions."""

    async def match_event(
        self,
        event: Event
    ) -> List[str]:
        """Get client IDs that should receive event."""
```

### 7.3 EventRouter

```python
class EventRouter:
    """Routes events from Redis to WebSocket clients."""

    async def start(self) -> None:
        """Start listening to Redis PubSub."""

    async def stop(self) -> None:
        """Stop listening."""

    async def route_event(
        self,
        event: Event
    ) -> None:
        """Route event to matching subscriptions."""
```

---

## 8. Connection Management

### 8.1 Heartbeat

```python
HEARTBEAT_INTERVAL = 30  # seconds
HEARTBEAT_TIMEOUT = 10   # seconds

async def heartbeat_loop(client_id: str):
    """Send periodic heartbeats to detect dead connections."""
    while client_connected(client_id):
        await send_ping(client_id)
        try:
            await wait_for_pong(client_id, timeout=HEARTBEAT_TIMEOUT)
        except TimeoutError:
            await disconnect(client_id, reason="heartbeat_timeout")
            break
        await asyncio.sleep(HEARTBEAT_INTERVAL)
```

### 8.2 Reconnection Handling

```json
// Server sends on graceful disconnect
{
  "type": "disconnect",
  "reason": "server_shutdown",
  "reconnect_after_ms": 5000
}

// Client should implement exponential backoff:
// 1s → 2s → 4s → 8s → 16s → 30s (max)
```

### 8.3 Backpressure

```python
class BackpressureHandler:
    """Handle slow clients."""

    MAX_QUEUE_SIZE = 100
    DROP_OLDEST = True

    async def queue_message(
        self,
        client_id: str,
        message: dict
    ) -> bool:
        """
        Queue message for client.

        If queue is full:
        - If DROP_OLDEST: drop oldest message
        - Else: drop new message

        Returns True if message was queued.
        """

    async def send_queued(
        self,
        client_id: str
    ) -> None:
        """Send queued messages when client is ready."""
```

---

## 9. Horizontal Scaling

### 9.1 Multi-Instance Architecture

```
                    ┌─────────────────┐
                    │  Load Balancer  │
                    │  (Sticky WS)    │
                    └────────┬────────┘
           ┌─────────────────┼─────────────────┐
           ▼                 ▼                 ▼
   ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
   │  Streaming    │ │  Streaming    │ │  Streaming    │
   │  Instance 1   │ │  Instance 2   │ │  Instance 3   │
   │               │ │               │ │               │
   │  Clients:     │ │  Clients:     │ │  Clients:     │
   │  A, D, G      │ │  B, E, H      │ │  C, F, I      │
   └───────┬───────┘ └───────┬───────┘ └───────┬───────┘
           │                 │                 │
           └─────────────────┴─────────────────┘
                             │
                    ┌────────▼────────┐
                    │     Redis       │
                    │   PubSub Hub    │
                    └─────────────────┘
```

### 9.2 Redis PubSub Channels

```
Channels:
├── aiops:events:all              # All events (for routing)
├── aiops:events:cluster:{id}     # Per-cluster events
├── aiops:events:alerts           # All alerts
├── aiops:events:gpu              # GPU updates
└── aiops:control:streaming       # Control messages (shutdown, etc.)
```

### 9.3 Sticky Sessions

WebSocket connections require sticky sessions. Configure load balancer:

```yaml
# HAProxy example
backend streaming_backend
    balance source
    cookie SERVERID insert indirect nocache
    server streaming1 streaming-1:8080 check cookie s1
    server streaming2 streaming-2:8080 check cookie s2
    server streaming3 streaming-3:8080 check cookie s3
```

---

## 10. Events Consumed

| Source | Event Types |
|--------|-------------|
| Cluster Registry | `CLUSTER_STATUS_CHANGED`, `CLUSTER_REGISTERED`, `CLUSTER_DELETED` |
| Observability Collector | `ALERT_FIRED`, `ALERT_RESOLVED`, `METRIC_UPDATE`, `GPU_UPDATE` |
| Intelligence Engine | `ANOMALY_DETECTED`, `CHAT_MESSAGE`, `RCA_COMPLETE` |

---

## 11. Dependencies

### 11.1 Internal Dependencies

| Dependency | Purpose |
|------------|---------|
| Redis | PubSub for event distribution |

### 11.2 External Dependencies

None - this service only consumes from Redis and serves WebSocket clients.

---

## 12. Configuration

```yaml
realtime_streaming:
  # Server settings
  host: "0.0.0.0"
  port: 8080

  # Redis
  redis_url: "redis://redis:6379/0"
  redis_channel_prefix: "aiops:events"

  # WebSocket settings
  websocket:
    heartbeat_interval_seconds: 30
    heartbeat_timeout_seconds: 10
    max_message_size_bytes: 65536
    max_connections: 1000

  # Backpressure
  backpressure:
    max_queue_size: 100
    drop_oldest: true
    slow_client_threshold_ms: 1000

  # Authentication
  auth:
    enabled: true
    token_validation_url: "http://api-gateway:8080/auth/validate"

  # Horizontal scaling
  scaling:
    sticky_session_cookie: "AIOPS_WS_SESSION"
```

---

## 13. Error Handling

| Error Code | Description | Action |
|------------|-------------|--------|
| `AUTH_FAILED` | Authentication failed | Close connection |
| `AUTH_EXPIRED` | Token expired | Request re-auth |
| `INVALID_MESSAGE` | Malformed message | Send error, continue |
| `INVALID_SUBSCRIPTION` | Bad subscription request | Send error, continue |
| `RATE_LIMITED` | Too many messages | Send warning, throttle |
| `QUEUE_FULL` | Backpressure triggered | Drop messages |
| `INTERNAL_ERROR` | Server error | Send error, continue |

---

## 14. Metrics Exposed

| Metric | Type | Description |
|--------|------|-------------|
| `ws_connections_total` | Counter | Total connections established |
| `ws_connections_active` | Gauge | Current active connections |
| `ws_messages_sent_total` | Counter | Total messages sent |
| `ws_messages_received_total` | Counter | Total messages received |
| `ws_events_routed_total` | Counter | Events routed (by type) |
| `ws_events_dropped_total` | Counter | Events dropped (backpressure) |
| `ws_subscription_count` | Gauge | Active subscriptions |
| `ws_message_latency_seconds` | Histogram | Message delivery latency |

---

## 15. Open Questions

1. **Binary Protocol**: Should we support binary (MessagePack) for efficiency?
2. **Event Replay**: Support replaying missed events on reconnect?
3. **Compression**: Enable WebSocket compression (permessage-deflate)?
4. **Rate Limiting**: Per-client message rate limits?
5. **Multi-Region**: Support for geo-distributed WebSocket endpoints?

---

## Next: [06-api-gateway.md](./06-api-gateway.md)
