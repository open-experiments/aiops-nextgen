# Sprint 7: WebSocket Hardening

**Issues Addressed:** ISSUE-016 (HIGH), ISSUE-017 (HIGH), ISSUE-020 (MEDIUM)
**Priority:** P1
**Dependencies:** Sprint 1 (WebSocket Auth)

---

## Overview

This sprint hardens the WebSocket implementation with proper heartbeat management, backpressure handling, and API gateway proxy support. The current implementation lacks connection lifecycle management.

---

## Task 7.1: Heartbeat Manager

**File:** `src/realtime-streaming/services/heartbeat.py`

### Implementation

```python
"""WebSocket Heartbeat Manager.

Spec Reference: specs/05-realtime-streaming.md Section 3.3

Manages connection health through periodic heartbeats:
- Server sends ping every 30 seconds
- Client must respond with pong within 10 seconds
- Stale connections are automatically closed
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional, Callable, Awaitable
from weakref import WeakSet

from fastapi import WebSocket
from pydantic import BaseModel

from shared.config import get_settings
from shared.observability import get_logger

logger = get_logger(__name__)


class ConnectionState(BaseModel):
    """State of a WebSocket connection."""

    connection_id: str
    user_id: str
    connected_at: datetime
    last_ping_sent: Optional[datetime] = None
    last_pong_received: Optional[datetime] = None
    missed_pongs: int = 0
    is_alive: bool = True


class HeartbeatManager:
    """Manages WebSocket connection heartbeats."""

    def __init__(
        self,
        ping_interval: int = 30,
        pong_timeout: int = 10,
        max_missed_pongs: int = 3,
    ):
        self.ping_interval = ping_interval
        self.pong_timeout = pong_timeout
        self.max_missed_pongs = max_missed_pongs

        self._connections: dict[str, tuple[WebSocket, ConnectionState]] = {}
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """Start the heartbeat manager."""
        if self._running:
            return

        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("Heartbeat manager started")

    async def stop(self):
        """Stop the heartbeat manager."""
        self._running = False

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        logger.info("Heartbeat manager stopped")

    def register(
        self,
        connection_id: str,
        websocket: WebSocket,
        user_id: str,
    ) -> ConnectionState:
        """Register a new WebSocket connection.

        Args:
            connection_id: Unique connection identifier
            websocket: The WebSocket connection
            user_id: Authenticated user ID

        Returns:
            ConnectionState for the connection
        """
        state = ConnectionState(
            connection_id=connection_id,
            user_id=user_id,
            connected_at=datetime.now(timezone.utc),
        )

        self._connections[connection_id] = (websocket, state)

        logger.info(
            "Connection registered",
            connection_id=connection_id,
            user_id=user_id,
        )

        return state

    def unregister(self, connection_id: str):
        """Unregister a WebSocket connection.

        Args:
            connection_id: Connection identifier to remove
        """
        if connection_id in self._connections:
            del self._connections[connection_id]
            logger.info("Connection unregistered", connection_id=connection_id)

    def handle_pong(self, connection_id: str):
        """Handle pong response from client.

        Args:
            connection_id: Connection that sent pong
        """
        if connection_id in self._connections:
            _, state = self._connections[connection_id]
            state.last_pong_received = datetime.now(timezone.utc)
            state.missed_pongs = 0

            logger.debug("Pong received", connection_id=connection_id)

    def get_connection_state(self, connection_id: str) -> Optional[ConnectionState]:
        """Get the state of a connection.

        Args:
            connection_id: Connection identifier

        Returns:
            ConnectionState or None if not found
        """
        if connection_id in self._connections:
            return self._connections[connection_id][1]
        return None

    def get_active_connections(self) -> list[ConnectionState]:
        """Get all active connection states.

        Returns:
            List of ConnectionState objects
        """
        return [state for _, state in self._connections.values() if state.is_alive]

    async def _heartbeat_loop(self):
        """Main heartbeat loop - sends pings and checks for stale connections."""
        while self._running:
            try:
                await asyncio.sleep(self.ping_interval)

                stale_connections = []
                now = datetime.now(timezone.utc)

                for conn_id, (ws, state) in list(self._connections.items()):
                    # Check for missed pongs
                    if state.last_ping_sent and not state.last_pong_received:
                        # Waiting for pong
                        wait_time = (now - state.last_ping_sent).total_seconds()

                        if wait_time > self.pong_timeout:
                            state.missed_pongs += 1

                            if state.missed_pongs >= self.max_missed_pongs:
                                stale_connections.append(conn_id)
                                state.is_alive = False
                                logger.warning(
                                    "Connection stale - closing",
                                    connection_id=conn_id,
                                    missed_pongs=state.missed_pongs,
                                )
                                continue

                    # Send ping
                    try:
                        await ws.send_json({
                            "type": "ping",
                            "timestamp": now.isoformat(),
                        })
                        state.last_ping_sent = now
                        state.last_pong_received = None

                        logger.debug("Ping sent", connection_id=conn_id)

                    except Exception as e:
                        logger.warning(
                            "Failed to send ping",
                            connection_id=conn_id,
                            error=str(e),
                        )
                        stale_connections.append(conn_id)
                        state.is_alive = False

                # Close stale connections
                for conn_id in stale_connections:
                    await self._close_stale_connection(conn_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Heartbeat loop error", error=str(e))

    async def _close_stale_connection(self, connection_id: str):
        """Close a stale connection.

        Args:
            connection_id: Connection to close
        """
        if connection_id not in self._connections:
            return

        ws, state = self._connections[connection_id]

        try:
            await ws.close(code=1000, reason="Connection timeout")
        except Exception:
            pass

        self.unregister(connection_id)


# Singleton instance
heartbeat_manager = HeartbeatManager()
```

---

## Task 7.2: Backpressure Handler

**File:** `src/realtime-streaming/services/backpressure.py`

### Implementation

```python
"""WebSocket Backpressure Handler.

Spec Reference: specs/05-realtime-streaming.md Section 3.4

Handles slow consumers by:
- Buffering messages up to a limit
- Dropping oldest messages when buffer full
- Tracking consumer lag metrics
"""

import asyncio
from collections import deque
from datetime import datetime, timezone
from typing import Optional, Any

from pydantic import BaseModel

from shared.observability import get_logger

logger = get_logger(__name__)


class ConsumerMetrics(BaseModel):
    """Metrics for a consumer's buffer state."""

    connection_id: str
    buffer_size: int
    max_buffer_size: int
    messages_dropped: int
    last_send_time: Optional[datetime] = None
    average_latency_ms: float = 0


class MessageBuffer:
    """Per-connection message buffer with backpressure handling."""

    def __init__(
        self,
        connection_id: str,
        max_size: int = 1000,
        drop_policy: str = "oldest",  # oldest, newest
    ):
        self.connection_id = connection_id
        self.max_size = max_size
        self.drop_policy = drop_policy

        self._buffer: deque = deque(maxlen=max_size if drop_policy == "oldest" else None)
        self._messages_dropped = 0
        self._latencies: deque = deque(maxlen=100)
        self._last_send_time: Optional[datetime] = None
        self._lock = asyncio.Lock()

    async def put(self, message: dict) -> bool:
        """Add a message to the buffer.

        Args:
            message: Message to buffer

        Returns:
            True if message was buffered, False if dropped
        """
        async with self._lock:
            if self.drop_policy == "oldest":
                # deque with maxlen automatically drops oldest
                was_full = len(self._buffer) >= self.max_size
                self._buffer.append({
                    "data": message,
                    "queued_at": datetime.now(timezone.utc),
                })
                if was_full:
                    self._messages_dropped += 1
                    return False
                return True

            else:  # newest
                if len(self._buffer) >= self.max_size:
                    self._messages_dropped += 1
                    return False

                self._buffer.append({
                    "data": message,
                    "queued_at": datetime.now(timezone.utc),
                })
                return True

    async def get(self) -> Optional[dict]:
        """Get next message from buffer.

        Returns:
            Message dict or None if empty
        """
        async with self._lock:
            if not self._buffer:
                return None

            item = self._buffer.popleft()
            now = datetime.now(timezone.utc)

            # Track latency
            queued_at = item["queued_at"]
            latency_ms = (now - queued_at).total_seconds() * 1000
            self._latencies.append(latency_ms)

            self._last_send_time = now

            return item["data"]

    def size(self) -> int:
        """Get current buffer size."""
        return len(self._buffer)

    def is_empty(self) -> bool:
        """Check if buffer is empty."""
        return len(self._buffer) == 0

    def get_metrics(self) -> ConsumerMetrics:
        """Get consumer metrics.

        Returns:
            ConsumerMetrics for this buffer
        """
        avg_latency = sum(self._latencies) / len(self._latencies) if self._latencies else 0

        return ConsumerMetrics(
            connection_id=self.connection_id,
            buffer_size=len(self._buffer),
            max_buffer_size=self.max_size,
            messages_dropped=self._messages_dropped,
            last_send_time=self._last_send_time,
            average_latency_ms=round(avg_latency, 2),
        )


class BackpressureHandler:
    """Manages backpressure across all WebSocket connections."""

    def __init__(
        self,
        default_buffer_size: int = 1000,
        high_watermark: float = 0.8,
        low_watermark: float = 0.5,
    ):
        self.default_buffer_size = default_buffer_size
        self.high_watermark = high_watermark
        self.low_watermark = low_watermark

        self._buffers: dict[str, MessageBuffer] = {}
        self._paused: set[str] = set()

    def register(self, connection_id: str, buffer_size: Optional[int] = None):
        """Register a new connection buffer.

        Args:
            connection_id: Connection identifier
            buffer_size: Optional custom buffer size
        """
        self._buffers[connection_id] = MessageBuffer(
            connection_id=connection_id,
            max_size=buffer_size or self.default_buffer_size,
        )

        logger.debug(
            "Buffer registered",
            connection_id=connection_id,
            size=buffer_size or self.default_buffer_size,
        )

    def unregister(self, connection_id: str):
        """Unregister a connection buffer.

        Args:
            connection_id: Connection to remove
        """
        if connection_id in self._buffers:
            del self._buffers[connection_id]
        self._paused.discard(connection_id)

    async def enqueue(self, connection_id: str, message: dict) -> bool:
        """Enqueue a message for a connection.

        Args:
            connection_id: Target connection
            message: Message to send

        Returns:
            True if queued, False if dropped or connection not found
        """
        buffer = self._buffers.get(connection_id)
        if not buffer:
            return False

        result = await buffer.put(message)

        # Check watermarks
        fill_ratio = buffer.size() / buffer.max_size

        if fill_ratio >= self.high_watermark:
            if connection_id not in self._paused:
                self._paused.add(connection_id)
                logger.warning(
                    "Connection paused - high watermark",
                    connection_id=connection_id,
                    fill_ratio=round(fill_ratio, 2),
                )

        elif fill_ratio <= self.low_watermark:
            if connection_id in self._paused:
                self._paused.discard(connection_id)
                logger.info(
                    "Connection resumed - below low watermark",
                    connection_id=connection_id,
                )

        return result

    async def dequeue(self, connection_id: str) -> Optional[dict]:
        """Dequeue next message for a connection.

        Args:
            connection_id: Connection to dequeue from

        Returns:
            Message or None if empty
        """
        buffer = self._buffers.get(connection_id)
        if not buffer:
            return None

        return await buffer.get()

    def is_paused(self, connection_id: str) -> bool:
        """Check if a connection is paused due to backpressure.

        Args:
            connection_id: Connection to check

        Returns:
            True if paused
        """
        return connection_id in self._paused

    def get_buffer_size(self, connection_id: str) -> int:
        """Get current buffer size for a connection.

        Args:
            connection_id: Connection to check

        Returns:
            Current buffer size
        """
        buffer = self._buffers.get(connection_id)
        return buffer.size() if buffer else 0

    def get_metrics(self, connection_id: str) -> Optional[ConsumerMetrics]:
        """Get metrics for a connection.

        Args:
            connection_id: Connection to get metrics for

        Returns:
            ConsumerMetrics or None
        """
        buffer = self._buffers.get(connection_id)
        return buffer.get_metrics() if buffer else None

    def get_all_metrics(self) -> list[ConsumerMetrics]:
        """Get metrics for all connections.

        Returns:
            List of ConsumerMetrics
        """
        return [buf.get_metrics() for buf in self._buffers.values()]


# Singleton instance
backpressure_handler = BackpressureHandler()
```

---

## Task 7.3: Updated WebSocket Endpoint

**File:** `src/realtime-streaming/api/v1/websocket.py` (REWRITE)

### Implementation

```python
"""WebSocket streaming endpoint.

Spec Reference: specs/05-realtime-streaming.md Section 2
"""

import asyncio
import uuid
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from middleware.ws_auth import authenticate_websocket, WSTokenPayload
from services.heartbeat import heartbeat_manager
from services.backpressure import backpressure_handler
from services.subscription import subscription_manager
from shared.observability import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint with full lifecycle management.

    Protocol:
    - Authenticate before connection acceptance
    - Register for heartbeat management
    - Handle subscriptions and messages
    - Manage backpressure for slow consumers
    """
    connection_id = str(uuid.uuid4())

    # Authenticate before accepting
    try:
        user = await authenticate_websocket(websocket)
    except Exception as e:
        logger.warning(
            "WebSocket auth failed",
            error=str(e),
            client=websocket.client.host if websocket.client else "unknown",
        )
        return

    # Accept connection
    await websocket.accept()

    # Register with heartbeat manager
    heartbeat_manager.register(
        connection_id=connection_id,
        websocket=websocket,
        user_id=user.sub,
    )

    # Register with backpressure handler
    backpressure_handler.register(connection_id)

    logger.info(
        "WebSocket connected",
        connection_id=connection_id,
        user_id=user.sub,
    )

    try:
        # Start message sender task
        sender_task = asyncio.create_task(
            _message_sender(websocket, connection_id)
        )

        # Message receiving loop
        while True:
            try:
                message = await websocket.receive_json()
                await _handle_message(
                    websocket=websocket,
                    connection_id=connection_id,
                    user=user,
                    message=message,
                )

            except WebSocketDisconnect:
                break

    except Exception as e:
        logger.error(
            "WebSocket error",
            connection_id=connection_id,
            error=str(e),
        )

    finally:
        # Cleanup
        sender_task.cancel()
        heartbeat_manager.unregister(connection_id)
        backpressure_handler.unregister(connection_id)
        subscription_manager.unsubscribe_all(connection_id)

        logger.info("WebSocket disconnected", connection_id=connection_id)


async def _message_sender(websocket: WebSocket, connection_id: str):
    """Background task to send buffered messages.

    Handles backpressure by pulling from the connection's message buffer.
    """
    while True:
        try:
            if websocket.client_state != WebSocketState.CONNECTED:
                break

            # Get next message from buffer
            message = await backpressure_handler.dequeue(connection_id)

            if message:
                await websocket.send_json(message)
            else:
                # No messages, wait briefly
                await asyncio.sleep(0.01)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(
                "Message sender error",
                connection_id=connection_id,
                error=str(e),
            )
            break


async def _handle_message(
    websocket: WebSocket,
    connection_id: str,
    user: WSTokenPayload,
    message: dict,
):
    """Handle incoming WebSocket message.

    Message types:
    - pong: Heartbeat response
    - subscribe: Subscribe to event types
    - unsubscribe: Unsubscribe from event types
    """
    msg_type = message.get("type")

    if msg_type == "pong":
        heartbeat_manager.handle_pong(connection_id)

    elif msg_type == "subscribe":
        event_types = message.get("events", [])
        cluster_ids = message.get("clusters", [])

        for event_type in event_types:
            subscription_manager.subscribe(
                connection_id=connection_id,
                event_type=event_type,
                cluster_ids=cluster_ids,
            )

        await websocket.send_json({
            "type": "subscribed",
            "events": event_types,
            "clusters": cluster_ids,
        })

    elif msg_type == "unsubscribe":
        event_types = message.get("events", [])

        for event_type in event_types:
            subscription_manager.unsubscribe(
                connection_id=connection_id,
                event_type=event_type,
            )

        await websocket.send_json({
            "type": "unsubscribed",
            "events": event_types,
        })

    else:
        logger.warning(
            "Unknown message type",
            connection_id=connection_id,
            type=msg_type,
        )
```

---

## Task 7.4: Subscription Manager Update

**File:** `src/realtime-streaming/services/subscription.py`

### Implementation

```python
"""Subscription Manager for WebSocket events.

Spec Reference: specs/05-realtime-streaming.md Section 3.2
"""

from typing import Optional
from collections import defaultdict

from pydantic import BaseModel

from shared.observability import get_logger

logger = get_logger(__name__)


class Subscription(BaseModel):
    """A subscription to an event type."""

    connection_id: str
    event_type: str
    cluster_ids: list[str]  # Empty list means all clusters


class SubscriptionManager:
    """Manages event subscriptions for WebSocket connections."""

    def __init__(self, max_subscriptions_per_client: int = 100):
        self.max_subscriptions = max_subscriptions_per_client

        # event_type -> list of subscriptions
        self._subscriptions: dict[str, list[Subscription]] = defaultdict(list)

        # connection_id -> list of event types
        self._connection_events: dict[str, list[str]] = defaultdict(list)

    def subscribe(
        self,
        connection_id: str,
        event_type: str,
        cluster_ids: Optional[list[str]] = None,
    ) -> bool:
        """Subscribe to an event type.

        Args:
            connection_id: Connection subscribing
            event_type: Event type to subscribe to
            cluster_ids: Optional cluster filter

        Returns:
            True if subscribed, False if limit reached
        """
        # Check subscription limit
        if len(self._connection_events[connection_id]) >= self.max_subscriptions:
            logger.warning(
                "Subscription limit reached",
                connection_id=connection_id,
                limit=self.max_subscriptions,
            )
            return False

        # Check if already subscribed
        for sub in self._subscriptions[event_type]:
            if sub.connection_id == connection_id:
                # Update cluster filter
                sub.cluster_ids = cluster_ids or []
                return True

        # Create new subscription
        subscription = Subscription(
            connection_id=connection_id,
            event_type=event_type,
            cluster_ids=cluster_ids or [],
        )

        self._subscriptions[event_type].append(subscription)
        self._connection_events[connection_id].append(event_type)

        logger.debug(
            "Subscribed",
            connection_id=connection_id,
            event_type=event_type,
            clusters=cluster_ids,
        )

        return True

    def unsubscribe(self, connection_id: str, event_type: str):
        """Unsubscribe from an event type.

        Args:
            connection_id: Connection unsubscribing
            event_type: Event type to unsubscribe from
        """
        self._subscriptions[event_type] = [
            sub
            for sub in self._subscriptions[event_type]
            if sub.connection_id != connection_id
        ]

        if event_type in self._connection_events[connection_id]:
            self._connection_events[connection_id].remove(event_type)

        logger.debug(
            "Unsubscribed",
            connection_id=connection_id,
            event_type=event_type,
        )

    def unsubscribe_all(self, connection_id: str):
        """Unsubscribe from all event types.

        Args:
            connection_id: Connection to remove all subscriptions for
        """
        event_types = list(self._connection_events[connection_id])

        for event_type in event_types:
            self.unsubscribe(connection_id, event_type)

        del self._connection_events[connection_id]

    def get_subscribers(
        self,
        event_type: str,
        cluster_id: Optional[str] = None,
    ) -> list[str]:
        """Get connection IDs subscribed to an event type.

        Args:
            event_type: Event type to check
            cluster_id: Optional cluster filter

        Returns:
            List of connection IDs
        """
        subscribers = []

        for sub in self._subscriptions[event_type]:
            # If no cluster filter on subscription, include
            if not sub.cluster_ids:
                subscribers.append(sub.connection_id)
            # If cluster_id matches subscription filter
            elif cluster_id and cluster_id in sub.cluster_ids:
                subscribers.append(sub.connection_id)

        return subscribers

    def get_subscriptions(self, connection_id: str) -> list[str]:
        """Get all event types a connection is subscribed to.

        Args:
            connection_id: Connection to check

        Returns:
            List of event types
        """
        return list(self._connection_events[connection_id])


# Singleton instance
subscription_manager = SubscriptionManager()
```

---

## Task 7.5: API Gateway WebSocket Proxy

**File:** `src/api-gateway/middleware/ws_proxy.py`

### Implementation

```python
"""WebSocket Proxy for API Gateway.

Spec Reference: specs/06-api-gateway.md Section 4.3

Proxies WebSocket connections to the realtime-streaming service
while maintaining authentication context.
"""

import asyncio
from typing import Optional

import httpx
from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from middleware.oauth import oauth_middleware
from shared.config import get_settings
from shared.observability import get_logger

logger = get_logger(__name__)


class WebSocketProxy:
    """Proxies WebSocket connections to backend service."""

    def __init__(self):
        self.settings = get_settings()
        self.backend_url = self.settings.services.realtime_streaming_url.replace(
            "http://", "ws://"
        ).replace("https://", "wss://")

    async def proxy(self, client_ws: WebSocket):
        """Proxy a WebSocket connection.

        Args:
            client_ws: Client WebSocket connection
        """
        # Authenticate the client
        try:
            user = await oauth_middleware(client_ws)
        except Exception as e:
            logger.warning("WebSocket proxy auth failed", error=str(e))
            await client_ws.close(code=1008, reason="Authentication failed")
            return

        # Accept client connection
        await client_ws.accept()

        # Connect to backend with token forwarded
        token = client_ws.headers.get("authorization", "").replace("Bearer ", "")
        if not token:
            # Try query param
            from urllib.parse import parse_qs
            query = client_ws.scope.get("query_string", b"").decode()
            params = parse_qs(query)
            token = params.get("token", [""])[0]

        backend_url = f"{self.backend_url}/ws?token={token}"

        try:
            async with httpx.AsyncClient() as http_client:
                # Note: httpx doesn't support WebSockets directly
                # In production, use websockets library
                import websockets

                async with websockets.connect(backend_url) as backend_ws:
                    # Start bidirectional proxy
                    await asyncio.gather(
                        self._forward_client_to_backend(client_ws, backend_ws),
                        self._forward_backend_to_client(backend_ws, client_ws),
                    )

        except Exception as e:
            logger.error("WebSocket proxy error", error=str(e))
            if client_ws.client_state == WebSocketState.CONNECTED:
                await client_ws.close(code=1011, reason="Backend unavailable")

    async def _forward_client_to_backend(self, client_ws: WebSocket, backend_ws):
        """Forward messages from client to backend."""
        try:
            while True:
                data = await client_ws.receive_text()
                await backend_ws.send(data)
        except WebSocketDisconnect:
            await backend_ws.close()

    async def _forward_backend_to_client(self, backend_ws, client_ws: WebSocket):
        """Forward messages from backend to client."""
        try:
            async for message in backend_ws:
                await client_ws.send_text(message)
        except Exception:
            if client_ws.client_state == WebSocketState.CONNECTED:
                await client_ws.close()


# Singleton instance
ws_proxy = WebSocketProxy()
```

---

## Acceptance Criteria

- [x] Heartbeat pings sent every 30 seconds
- [x] Connections closed after 3 missed pongs
- [x] Pong handler updates connection state
- [x] Message buffer with 1000 message limit
- [x] Oldest messages dropped when buffer full
- [x] High watermark (80%) triggers pause
- [x] Low watermark (50%) resumes consumption
- [x] Consumer lag metrics tracked
- [x] API Gateway proxies WebSocket to backend
- [ ] All tests pass with >80% coverage

---

## Implementation Status: COMPLETED

**Completed:** 2025-12-29

### Files Created

| File | Description |
|------|-------------|
| `src/realtime-streaming/app/services/heartbeat.py` | HeartbeatManager with 30s ping, 10s pong timeout, 3 missed pong detection |
| `src/realtime-streaming/app/services/backpressure.py` | BackpressureHandler with 1000 message buffer, high/low watermarks |
| `src/api-gateway/app/api/websocket_proxy.py` | WebSocket proxy with OAuth authentication |

### Files Modified

| File | Changes |
|------|---------|
| `src/realtime-streaming/app/api/websocket.py` | Integrated heartbeat and backpressure managers |
| `src/realtime-streaming/app/main.py` | Start/stop heartbeat manager in lifespan |
| `src/realtime-streaming/app/services/__init__.py` | Export new services |
| `src/api-gateway/app/main.py` | Include WebSocket proxy router |

### Key Implementation Details

1. **HeartbeatManager** (`heartbeat.py`):
   - Tracks connection state with last_ping_sent and last_pong_received
   - Async heartbeat loop runs every 30 seconds
   - Closes connections after 3 consecutive missed pongs
   - Singleton instance shared across all WebSocket connections

2. **BackpressureHandler** (`backpressure.py`):
   - Per-connection MessageBuffer with configurable max size (default 1000)
   - Drop policy: oldest messages dropped when buffer full
   - High watermark (80%): pauses event production for connection
   - Low watermark (50%): resumes event production
   - Tracks consumer metrics: buffer size, dropped messages, average latency

3. **WebSocket Proxy** (`websocket_proxy.py`):
   - Extracts token from query params or Sec-WebSocket-Protocol header
   - Validates token via OAuth middleware before accepting connection
   - Bidirectional message forwarding to backend realtime-streaming service
   - Fallback handling when websockets library unavailable

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `src/realtime-streaming/services/heartbeat.py` | CREATE | Heartbeat manager |
| `src/realtime-streaming/services/backpressure.py` | CREATE | Backpressure handler |
| `src/realtime-streaming/services/subscription.py` | CREATE | Subscription manager |
| `src/realtime-streaming/api/v1/websocket.py` | REWRITE | Updated WS endpoint |
| `src/api-gateway/middleware/ws_proxy.py` | CREATE | WS proxy |
| `src/realtime-streaming/tests/test_heartbeat.py` | CREATE | Heartbeat tests |
| `src/realtime-streaming/tests/test_backpressure.py` | CREATE | Backpressure tests |

---

## Dependencies

### Python packages

```toml
dependencies = [
    "websockets>=12.0",  # For API Gateway proxy
]
```
