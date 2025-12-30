"""WebSocket Hub for managing connections.

Spec Reference: specs/05-realtime-streaming.md Section 7.1
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from fastapi import WebSocket

from shared.observability import get_logger

logger = get_logger(__name__)


class WebSocketHub:
    """Manages WebSocket connections.

    Spec Reference: specs/05-realtime-streaming.md Section 7.1
    """

    MAX_QUEUE_SIZE = 100

    def __init__(self):
        self._connections: dict[str, WebSocket] = {}
        self._client_info: dict[str, dict[str, Any]] = {}
        self._message_queues: dict[str, asyncio.Queue] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        """Handle new connection.

        Args:
            websocket: The WebSocket connection
            client_id: Unique client identifier
        """
        async with self._lock:
            self._connections[client_id] = websocket
            self._client_info[client_id] = {
                "connected_at": datetime.utcnow().isoformat() + "Z",
                "subscriptions": [],
            }
            self._message_queues[client_id] = asyncio.Queue(maxsize=self.MAX_QUEUE_SIZE)

        logger.info(
            "Client connected to hub",
            client_id=client_id,
            total_clients=len(self._connections),
        )

    async def disconnect(self, client_id: str) -> None:
        """Handle disconnection.

        Args:
            client_id: Client identifier
        """
        async with self._lock:
            self._connections.pop(client_id, None)
            self._client_info.pop(client_id, None)
            self._message_queues.pop(client_id, None)

        logger.info(
            "Client disconnected from hub",
            client_id=client_id,
            total_clients=len(self._connections),
        )

    async def send_to_client(self, client_id: str, message: dict) -> bool:
        """Send message to specific client.

        Args:
            client_id: Target client identifier
            message: Message to send

        Returns:
            True if message was sent successfully
        """
        websocket = self._connections.get(client_id)
        if not websocket:
            return False

        try:
            await websocket.send_json(message)
            return True
        except Exception as e:
            logger.warning(
                "Failed to send message to client",
                client_id=client_id,
                error=str(e),
            )
            return False

    async def broadcast(
        self,
        message: dict,
        client_ids: list[str] | None = None,
    ) -> int:
        """Broadcast message to clients.

        Args:
            message: Message to broadcast
            client_ids: Specific client IDs to send to (None = all)

        Returns:
            Number of clients that received the message
        """
        targets = client_ids if client_ids else list(self._connections.keys())
        sent_count = 0

        for client_id in targets:
            if await self.send_to_client(client_id, message):
                sent_count += 1

        return sent_count

    def get_client_count(self) -> int:
        """Get number of connected clients."""
        return len(self._connections)

    def get_clients(self) -> dict[str, dict[str, Any]]:
        """Get all connected clients info."""
        return self._client_info.copy()

    def is_connected(self, client_id: str) -> bool:
        """Check if client is connected."""
        return client_id in self._connections
