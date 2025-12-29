"""WebSocket Backpressure Handler.

Spec Reference: specs/05-realtime-streaming.md Section 3.4

Handles slow consumers by:
- Buffering messages up to a limit
- Dropping oldest messages when buffer full
- Tracking consumer lag metrics
"""

from __future__ import annotations

import asyncio
from collections import deque
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from shared.observability import get_logger

logger = get_logger(__name__)


class ConsumerMetrics(BaseModel):
    """Metrics for a consumer's buffer state."""

    connection_id: str
    buffer_size: int
    max_buffer_size: int
    messages_dropped: int
    last_send_time: datetime | None = None
    average_latency_ms: float = 0


class MessageBuffer:
    """Per-connection message buffer with backpressure handling."""

    def __init__(
        self,
        connection_id: str,
        max_size: int = 1000,
        drop_policy: str = "oldest",  # oldest, newest
    ):
        """Initialize the message buffer.

        Args:
            connection_id: Connection identifier
            max_size: Maximum buffer size
            drop_policy: Policy for dropping messages when full
        """
        self.connection_id = connection_id
        self.max_size = max_size
        self.drop_policy = drop_policy

        # Use deque with maxlen for oldest policy
        self._buffer: deque[dict[str, Any]] = deque(
            maxlen=max_size if drop_policy == "oldest" else None
        )
        self._messages_dropped = 0
        self._latencies: deque[float] = deque(maxlen=100)
        self._last_send_time: datetime | None = None
        self._lock = asyncio.Lock()

    async def put(self, message: dict[str, Any]) -> bool:
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
                    "queued_at": datetime.now(UTC),
                })
                if was_full:
                    self._messages_dropped += 1
                    logger.debug(
                        "Message dropped (oldest policy)",
                        connection_id=self.connection_id,
                        dropped_total=self._messages_dropped,
                    )
                    return False
                return True

            else:  # newest
                if len(self._buffer) >= self.max_size:
                    self._messages_dropped += 1
                    logger.debug(
                        "Message dropped (newest policy)",
                        connection_id=self.connection_id,
                        dropped_total=self._messages_dropped,
                    )
                    return False

                self._buffer.append({
                    "data": message,
                    "queued_at": datetime.now(UTC),
                })
                return True

    async def get(self) -> dict[str, Any] | None:
        """Get next message from buffer.

        Returns:
            Message dict or None if empty
        """
        async with self._lock:
            if not self._buffer:
                return None

            item = self._buffer.popleft()
            now = datetime.now(UTC)

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
        avg_latency = (
            sum(self._latencies) / len(self._latencies)
            if self._latencies
            else 0
        )

        return ConsumerMetrics(
            connection_id=self.connection_id,
            buffer_size=len(self._buffer),
            max_buffer_size=self.max_size,
            messages_dropped=self._messages_dropped,
            last_send_time=self._last_send_time,
            average_latency_ms=round(avg_latency, 2),
        )


class BackpressureHandler:
    """Manages backpressure across all WebSocket connections.

    Spec Reference: specs/05-realtime-streaming.md Section 3.4
    """

    def __init__(
        self,
        default_buffer_size: int = 1000,
        high_watermark: float = 0.8,
        low_watermark: float = 0.5,
    ):
        """Initialize the backpressure handler.

        Args:
            default_buffer_size: Default message buffer size per connection
            high_watermark: Buffer fill ratio to trigger pause
            low_watermark: Buffer fill ratio to resume consumption
        """
        self.default_buffer_size = default_buffer_size
        self.high_watermark = high_watermark
        self.low_watermark = low_watermark

        self._buffers: dict[str, MessageBuffer] = {}
        self._paused: set[str] = set()

    def register(self, connection_id: str, buffer_size: int | None = None) -> None:
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

    def unregister(self, connection_id: str) -> None:
        """Unregister a connection buffer.

        Args:
            connection_id: Connection to remove
        """
        if connection_id in self._buffers:
            del self._buffers[connection_id]
        self._paused.discard(connection_id)

    async def enqueue(self, connection_id: str, message: dict[str, Any]) -> bool:
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

        elif fill_ratio <= self.low_watermark and connection_id in self._paused:
            self._paused.discard(connection_id)
            logger.info(
                "Connection resumed - below low watermark",
                connection_id=connection_id,
            )

        return result

    async def dequeue(self, connection_id: str) -> dict[str, Any] | None:
        """Dequeue next message for a connection.

        Args:
            connection_id: Connection to dequeue from

        Returns:
            Message or None if empty
        """
        buffer = self._buffers.get(connection_id)
        if not buffer:
            return None

        message = await buffer.get()

        # Check if we can resume
        if connection_id in self._paused:
            fill_ratio = buffer.size() / buffer.max_size
            if fill_ratio <= self.low_watermark:
                self._paused.discard(connection_id)
                logger.info(
                    "Connection resumed after dequeue",
                    connection_id=connection_id,
                )

        return message

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

    def get_metrics(self, connection_id: str) -> ConsumerMetrics | None:
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

    def get_paused_count(self) -> int:
        """Get number of paused connections.

        Returns:
            Number of paused connections
        """
        return len(self._paused)

    def get_total_dropped(self) -> int:
        """Get total messages dropped across all connections.

        Returns:
            Total dropped message count
        """
        return sum(buf.get_metrics().messages_dropped for buf in self._buffers.values())


# Singleton instance
backpressure_handler = BackpressureHandler()
