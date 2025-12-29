"""Event Router for Redis PubSub to WebSocket routing.

Spec Reference: specs/05-realtime-streaming.md Section 7.3
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from shared.observability import get_logger
from shared.redis_client import RedisClient

from .hub import WebSocketHub
from .subscriptions import SubscriptionManager

logger = get_logger(__name__)


class EventRouter:
    """Routes events from Redis to WebSocket clients.

    Spec Reference: specs/05-realtime-streaming.md Section 7.3

    Subscribes to Redis PubSub channels and routes events
    to matching WebSocket clients based on their subscriptions.
    """

    # Redis channels to subscribe to
    # Spec Reference: specs/05-realtime-streaming.md Section 9.2
    CHANNELS = [
        "aiops:events:all",
        "aiops:events:cluster:*",
        "aiops:events:alerts",
        "aiops:events:gpu",
    ]

    def __init__(
        self,
        redis: RedisClient,
        hub: WebSocketHub,
        subscription_manager: SubscriptionManager,
    ):
        self.redis = redis
        self.hub = hub
        self.subscription_manager = subscription_manager
        self._running = False
        self._pubsub = None
        self.events_routed = 0

    async def start(self) -> None:
        """Start listening to Redis PubSub.

        Spec Reference: specs/05-realtime-streaming.md Section 7.3
        """
        self._running = True

        logger.info("Starting EventRouter")

        # Subscribe to all events channel
        try:
            self._pubsub = await self.redis.subscribe(
                ["aiops:events:all"],
                self._handle_message,
            )

            # Run the pubsub message listener
            while self._running:
                try:
                    await self._pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=1.0,
                    )
                    await asyncio.sleep(0.01)
                except Exception as e:
                    if self._running:
                        logger.error("PubSub error", error=str(e))
                        await asyncio.sleep(1.0)

        except asyncio.CancelledError:
            logger.info("EventRouter cancelled")
        except Exception as e:
            logger.error("EventRouter failed to start", error=str(e))

    async def stop(self) -> None:
        """Stop listening."""
        self._running = False
        if self._pubsub:
            await self._pubsub.unsubscribe()
            await self._pubsub.close()

        logger.info("EventRouter stopped")

    async def _handle_message(self, channel: str, data: str) -> None:
        """Handle incoming Redis message.

        Args:
            channel: Redis channel name
            data: Message data (JSON string)
        """
        try:
            event = json.loads(data)
            await self.route_event(event)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON in Redis message", channel=channel)
        except Exception as e:
            logger.error(
                "Error handling Redis message",
                channel=channel,
                error=str(e),
            )

    async def route_event(self, event: dict[str, Any]) -> None:
        """Route event to matching subscriptions.

        Args:
            event: Event data from Redis
        """
        # Find matching clients
        client_ids = await self.subscription_manager.match_event(event)

        if not client_ids:
            return

        # Build WebSocket message
        message = {
            "type": "event",
            "event_id": event.get("id"),
            "event_type": event.get("event_type"),
            "cluster_id": event.get("cluster_id"),
            "timestamp": event.get("timestamp"),
            "payload": event.get("payload", {}),
        }

        # Broadcast to matching clients
        sent_count = await self.hub.broadcast(message, client_ids)

        self.events_routed += 1

        logger.debug(
            "Event routed",
            event_type=event.get("event_type"),
            matched_clients=len(client_ids),
            sent_count=sent_count,
        )

    async def publish_event(self, event: dict[str, Any]) -> None:
        """Publish event directly (for testing/internal use).

        Args:
            event: Event to publish
        """
        await self.route_event(event)
