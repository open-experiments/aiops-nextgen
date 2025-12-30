"""Subscription Manager for client subscriptions.

Spec Reference: specs/05-realtime-streaming.md Section 7.2
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from shared.observability import get_logger

logger = get_logger(__name__)


@dataclass
class Subscription:
    """Client subscription configuration."""

    event_types: list[str] = field(default_factory=list)
    cluster_filter: list[str] = field(default_factory=list)
    namespace_filter: list[str] = field(default_factory=list)


class SubscriptionManager:
    """Manages client subscriptions.

    Spec Reference: specs/05-realtime-streaming.md Section 7.2
    """

    # Valid event types per spec Section 5
    VALID_EVENT_TYPES = {
        # Cluster events
        "CLUSTER_REGISTERED",
        "CLUSTER_UPDATED",
        "CLUSTER_DELETED",
        "CLUSTER_STATUS_CHANGED",
        "CLUSTER_CREDENTIALS_UPDATED",
        "CLUSTER_CAPABILITIES_CHANGED",
        # Observability events
        "METRIC_UPDATE",
        "ALERT_FIRED",
        "ALERT_RESOLVED",
        "GPU_UPDATE",
        "TRACE_RECEIVED",
        # Intelligence events
        "ANOMALY_DETECTED",
        "CHAT_MESSAGE",
        "RCA_COMPLETE",
        "REPORT_GENERATED",
    }

    def __init__(self):
        self._subscriptions: dict[str, Subscription] = {}
        self._lock = asyncio.Lock()

    async def subscribe(
        self,
        client_id: str,
        event_types: list[str] | None = None,
        cluster_filter: list[str] | None = None,
        namespace_filter: list[str] | None = None,
    ) -> None:
        """Add subscription for client.

        Args:
            client_id: Client identifier
            event_types: Event types to subscribe to
            cluster_filter: Optional cluster IDs to filter
            namespace_filter: Optional namespaces to filter
        """
        async with self._lock:
            # Validate event types
            valid_types = []
            for et in event_types or []:
                if et in self.VALID_EVENT_TYPES:
                    valid_types.append(et)
                else:
                    logger.warning(
                        "Invalid event type in subscription",
                        client_id=client_id,
                        event_type=et,
                    )

            # Create or update subscription
            self._subscriptions[client_id] = Subscription(
                event_types=valid_types,
                cluster_filter=cluster_filter or [],
                namespace_filter=namespace_filter or [],
            )

        logger.info(
            "Client subscription updated",
            client_id=client_id,
            event_types=valid_types,
        )

    async def unsubscribe(
        self,
        client_id: str,
        event_types: list[str] | None = None,
    ) -> None:
        """Remove subscriptions.

        Args:
            client_id: Client identifier
            event_types: Specific types to unsubscribe (None = all)
        """
        async with self._lock:
            if event_types is None:
                # Remove all subscriptions
                self._subscriptions.pop(client_id, None)
            elif client_id in self._subscriptions:
                # Remove specific event types
                sub = self._subscriptions[client_id]
                sub.event_types = [et for et in sub.event_types if et not in event_types]
                if not sub.event_types:
                    self._subscriptions.pop(client_id, None)

    async def get_subscriptions(self, client_id: str) -> Subscription | None:
        """Get client's subscription."""
        return self._subscriptions.get(client_id)

    async def match_event(self, event: dict[str, Any]) -> list[str]:
        """Get client IDs that should receive event.

        Args:
            event: Event data with event_type, cluster_id, etc.

        Returns:
            List of client IDs that match the event
        """
        event_type = event.get("event_type")
        cluster_id = event.get("cluster_id")
        namespace = event.get("payload", {}).get("namespace")

        matched_clients = []

        async with self._lock:
            for client_id, sub in self._subscriptions.items():
                # Check event type match
                if event_type not in sub.event_types:
                    continue

                # Check cluster filter
                if sub.cluster_filter and cluster_id:
                    if str(cluster_id) not in sub.cluster_filter:
                        continue

                # Check namespace filter
                if sub.namespace_filter and namespace:
                    if namespace not in sub.namespace_filter:
                        continue

                matched_clients.append(client_id)

        return matched_clients

    def get_subscription_count(self) -> int:
        """Get total number of active subscriptions."""
        return len(self._subscriptions)

    def get_stats(self) -> dict[str, Any]:
        """Get subscription statistics."""
        by_event_type: dict[str, int] = {}
        by_cluster: dict[str, int] = {}

        for sub in self._subscriptions.values():
            for et in sub.event_types:
                by_event_type[et] = by_event_type.get(et, 0) + 1
            for cluster in sub.cluster_filter:
                by_cluster[cluster] = by_cluster.get(cluster, 0) + 1

        return {
            "total": len(self._subscriptions),
            "by_event_type": by_event_type,
            "by_cluster": by_cluster,
        }
