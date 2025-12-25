"""WebSocket endpoint.

Spec Reference: specs/05-realtime-streaming.md Section 4
"""

from __future__ import annotations

import json
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from shared.observability import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket connection endpoint.

    Spec Reference: specs/05-realtime-streaming.md Section 4.1

    Protocol:
    1. Client connects
    2. Client sends auth message (optional in dev mode)
    3. Client subscribes to event types
    4. Server sends events matching subscriptions
    5. Ping/pong for keepalive
    """
    hub = websocket.app.state.hub
    subscription_manager = websocket.app.state.subscription_manager

    # Generate client ID
    client_id = str(uuid4())

    # Accept connection
    await websocket.accept()

    # Register with hub
    await hub.connect(websocket, client_id)

    logger.info(
        "WebSocket client connected",
        client_id=client_id,
    )

    try:
        # Send connection confirmation
        await websocket.send_json({
            "type": "connected",
            "client_id": client_id,
            "server_time": datetime.utcnow().isoformat() + "Z",
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
        await hub.disconnect(client_id)
        await subscription_manager.unsubscribe(client_id)


async def handle_message(
    websocket: WebSocket,
    client_id: str,
    message: dict,
    hub,
    subscription_manager,
):
    """Handle incoming WebSocket message.

    Spec Reference: specs/05-realtime-streaming.md Section 4.3
    """
    msg_type = message.get("type")

    if msg_type == "auth":
        # For MVP, accept any auth (in production, validate token)
        await websocket.send_json({
            "type": "auth_response",
            "status": "authenticated",
            "client_id": client_id,
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
        timestamp = message.get("timestamp")
        await websocket.send_json({
            "type": "pong",
            "timestamp": timestamp,
            "server_time": datetime.utcnow().isoformat() + "Z",
        })

    else:
        await websocket.send_json({
            "type": "error",
            "code": "UNKNOWN_MESSAGE_TYPE",
            "message": f"Unknown message type: {msg_type}",
        })
