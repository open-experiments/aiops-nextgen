"""WebSocket Heartbeat Manager.

Spec Reference: specs/05-realtime-streaming.md Section 3.3

Manages connection health through periodic heartbeats:
- Server sends ping every 30 seconds
- Client must respond with pong within 10 seconds
- Stale connections are automatically closed
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

from shared.observability import get_logger

if TYPE_CHECKING:
    from fastapi import WebSocket

logger = get_logger(__name__)


class ConnectionState(BaseModel):
    """State of a WebSocket connection."""

    connection_id: str
    user_id: str
    connected_at: datetime
    last_ping_sent: datetime | None = None
    last_pong_received: datetime | None = None
    missed_pongs: int = 0
    is_alive: bool = True

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True


class HeartbeatManager:
    """Manages WebSocket connection heartbeats.

    Spec Reference: specs/05-realtime-streaming.md Section 3.3
    """

    def __init__(
        self,
        ping_interval: int = 30,
        pong_timeout: int = 10,
        max_missed_pongs: int = 3,
    ):
        """Initialize the heartbeat manager.

        Args:
            ping_interval: Seconds between ping messages
            pong_timeout: Seconds to wait for pong response
            max_missed_pongs: Number of missed pongs before closing connection
        """
        self.ping_interval = ping_interval
        self.pong_timeout = pong_timeout
        self.max_missed_pongs = max_missed_pongs

        self._connections: dict[str, tuple[WebSocket, ConnectionState]] = {}
        self._heartbeat_task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Start the heartbeat manager."""
        if self._running:
            return

        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("Heartbeat manager started")

    async def stop(self) -> None:
        """Stop the heartbeat manager."""
        self._running = False

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._heartbeat_task

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
            connected_at=datetime.now(UTC),
        )

        self._connections[connection_id] = (websocket, state)

        logger.info(
            "Connection registered for heartbeat",
            connection_id=connection_id,
            user_id=user_id,
        )

        return state

    def unregister(self, connection_id: str) -> None:
        """Unregister a WebSocket connection.

        Args:
            connection_id: Connection identifier to remove
        """
        if connection_id in self._connections:
            del self._connections[connection_id]
            logger.info("Connection unregistered from heartbeat", connection_id=connection_id)

    def handle_pong(self, connection_id: str) -> None:
        """Handle pong response from client.

        Args:
            connection_id: Connection that sent pong
        """
        if connection_id in self._connections:
            _, state = self._connections[connection_id]
            state.last_pong_received = datetime.now(UTC)
            state.missed_pongs = 0

            logger.debug("Pong received", connection_id=connection_id)

    def get_connection_state(self, connection_id: str) -> ConnectionState | None:
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

    def get_connection_count(self) -> int:
        """Get total number of registered connections.

        Returns:
            Number of connections
        """
        return len(self._connections)

    async def _heartbeat_loop(self) -> None:
        """Main heartbeat loop - sends pings and checks for stale connections."""
        while self._running:
            try:
                await asyncio.sleep(self.ping_interval)

                stale_connections = []
                now = datetime.now(UTC)

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

    async def _close_stale_connection(self, connection_id: str) -> None:
        """Close a stale connection.

        Args:
            connection_id: Connection to close
        """
        if connection_id not in self._connections:
            return

        ws, _ = self._connections[connection_id]

        with contextlib.suppress(Exception):
            await ws.close(code=1000, reason="Connection timeout")

        self.unregister(connection_id)


# Singleton instance
heartbeat_manager = HeartbeatManager()
