"""Streaming API endpoints.

Spec Reference: specs/05-realtime-streaming.md Section 6.1
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class StreamingStatus(BaseModel):
    """Streaming service status."""

    connected_clients: int
    total_subscriptions: int
    events_routed: int


@router.get(
    "/streaming/status",
    response_model=StreamingStatus,
    summary="Get streaming service status",
    description="Returns current status of the streaming service.",
)
async def get_status(request: Request):
    """Get streaming service status.

    Spec Reference: specs/05-realtime-streaming.md Section 6.1
    """
    hub = request.app.state.hub
    subscription_manager = request.app.state.subscription_manager
    event_router = request.app.state.event_router

    return StreamingStatus(
        connected_clients=hub.get_client_count(),
        total_subscriptions=subscription_manager.get_subscription_count(),
        events_routed=event_router.events_routed,
    )


@router.get(
    "/streaming/clients",
    summary="List connected clients",
    description="Returns list of connected WebSocket clients.",
)
async def list_clients(request: Request):
    """List connected clients.

    Spec Reference: specs/05-realtime-streaming.md Section 6.1
    """
    hub = request.app.state.hub

    clients = []
    for client_id, info in hub.get_clients().items():
        clients.append({
            "client_id": client_id,
            "connected_at": info.get("connected_at"),
            "subscriptions": info.get("subscriptions", []),
        })

    return {"clients": clients, "total": len(clients)}


@router.get(
    "/streaming/subscriptions",
    summary="Get subscription statistics",
    description="Returns subscription statistics.",
)
async def get_subscriptions(request: Request):
    """Get subscription statistics.

    Spec Reference: specs/05-realtime-streaming.md Section 6.1
    """
    subscription_manager = request.app.state.subscription_manager

    stats = subscription_manager.get_stats()

    return {
        "total_subscriptions": stats.get("total", 0),
        "by_event_type": stats.get("by_event_type", {}),
        "by_cluster": stats.get("by_cluster", {}),
    }
