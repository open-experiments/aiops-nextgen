"""WebSocket endpoint with heartbeat and backpressure support.

Spec Reference: specs/05-realtime-streaming.md Section 4
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, WebSocketException
from starlette.websockets import WebSocketState

from shared.config import get_settings
from shared.observability import get_logger

from ..middleware.ws_auth import authenticate_websocket
from ..services.backpressure import backpressure_handler
from ..services.heartbeat import heartbeat_manager

router = APIRouter()
logger = get_logger(__name__)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket connection endpoint with lifecycle management.

    Spec Reference: specs/05-realtime-streaming.md Section 4.1

    Protocol:
    1. Client connects with authentication token
    2. Server validates token before accepting
    3. Register with heartbeat and backpressure managers
    4. Client subscribes to event types
    5. Server sends events matching subscriptions
    6. Ping/pong for keepalive with timeout detection
    """
    settings = get_settings()
    hub = websocket.app.state.hub
    subscription_manager = websocket.app.state.subscription_manager

    # Authenticate before accepting connection
    # Skip authentication if OAuth is not configured (development mode)
    user = None
    if settings.oauth.issuer:
        try:
            user = await authenticate_websocket(websocket)
        except WebSocketException as e:
            await websocket.close(code=e.code, reason=e.reason)
            return

    # Generate client ID (use user_id if authenticated)
    client_id = user.sub if user else str(uuid4())
    user_id = user.sub if user else "anonymous"

    # Accept connection after successful authentication
    await websocket.accept()

    # Store user context for authorization checks
    if user:
        websocket.state.user_id = user.sub
        websocket.state.username = user.preferred_username
        websocket.state.groups = user.groups

    # Register with heartbeat manager
    heartbeat_manager.register(
        connection_id=client_id,
        websocket=websocket,
        user_id=user_id,
    )

    # Register with backpressure handler
    backpressure_handler.register(client_id)

    # Register with hub
    await hub.connect(websocket, client_id)

    logger.info(
        "WebSocket client connected",
        client_id=client_id,
        authenticated=user is not None,
        username=user.preferred_username if user else None,
    )

    # Start message sender task for backpressure handling
    sender_task = asyncio.create_task(
        _message_sender(websocket, client_id)
    )

    try:
        # Send connection confirmation
        await websocket.send_json({
            "type": "connected",
            "client_id": client_id,
            "server_time": datetime.now(UTC).isoformat(),
        })

        # Message handling loop
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                await handle_message(
                    websocket,
                    client_id,
                    message,
                    hub,
                    subscription_manager,
                )
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "code": "INVALID_MESSAGE",
                    "message": "Invalid JSON message",
                })

    except WebSocketDisconnect:
        logger.info(
            "WebSocket client disconnected",
            client_id=client_id,
        )
    except Exception as e:
        logger.error(
            "WebSocket error",
            client_id=client_id,
            error=str(e),
        )
    finally:
        # Cleanup
        sender_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await sender_task

        heartbeat_manager.unregister(client_id)
        backpressure_handler.unregister(client_id)
        await hub.disconnect(client_id)
        await subscription_manager.unsubscribe(client_id)


async def _message_sender(websocket: WebSocket, connection_id: str) -> None:
    """Background task to send buffered messages.

    Handles backpressure by pulling from the connection's message buffer.

    Args:
        websocket: The WebSocket connection
        connection_id: Connection identifier
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


async def handle_message(
    websocket: WebSocket,
    client_id: str,
    message: dict,
    hub,
    subscription_manager,
) -> None:
    """Handle incoming WebSocket message.

    Spec Reference: specs/05-realtime-streaming.md Section 4.3

    Message types:
    - auth: Legacy authentication (now done at connection time)
    - subscribe: Subscribe to event types
    - unsubscribe: Unsubscribe from event types
    - ping: Client ping (not the heartbeat ping)
    - pong: Response to server heartbeat ping

    Args:
        websocket: The WebSocket connection
        client_id: Client identifier
        message: Received message
        hub: WebSocket hub instance
        subscription_manager: Subscription manager instance
    """
    msg_type = message.get("type")

    if msg_type == "auth":
        # Authentication is now done at connection time
        # This message type is kept for backward compatibility
        await websocket.send_json({
            "type": "auth_response",
            "status": "authenticated",
            "client_id": client_id,
            "message": "Authentication validated at connection time",
        })

    elif msg_type == "subscribe":
        subscription = message.get("subscription", {})
        event_types = subscription.get("event_types", [])
        cluster_filter = subscription.get("cluster_filter", [])
        namespace_filter = subscription.get("namespace_filter", [])

        await subscription_manager.subscribe(
            client_id,
            event_types=event_types,
            cluster_filter=cluster_filter,
            namespace_filter=namespace_filter,
        )

        await websocket.send_json({
            "type": "subscribed",
            "event_types": event_types,
            "cluster_filter": cluster_filter,
            "namespace_filter": namespace_filter,
        })

        logger.info(
            "Client subscribed",
            client_id=client_id,
            event_types=event_types,
        )

    elif msg_type == "unsubscribe":
        event_types = message.get("event_types")
        await subscription_manager.unsubscribe(client_id, event_types)

        await websocket.send_json({
            "type": "unsubscribed",
            "event_types": event_types,
        })

    elif msg_type == "ping":
        # Client-initiated ping (different from server heartbeat)
        timestamp = message.get("timestamp")
        await websocket.send_json({
            "type": "pong",
            "timestamp": timestamp,
            "server_time": datetime.now(UTC).isoformat(),
        })

    elif msg_type == "pong":
        # Response to server heartbeat ping
        heartbeat_manager.handle_pong(client_id)

    else:
        await websocket.send_json({
            "type": "error",
            "code": "UNKNOWN_MESSAGE_TYPE",
            "message": f"Unknown message type: {msg_type}",
        })
