"""Event service for Redis pub/sub.

Spec Reference: specs/02-cluster-registry.md Section 5.5, 6
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from shared.observability import get_logger
from shared.redis_client import RedisClient
from shared.models.events import Event, EventType

logger = get_logger(__name__)


class EventService:
    """Service for publishing events to Redis.

    Spec Reference: specs/02-cluster-registry.md Section 5.5

    Events emitted (Section 6):
    - CLUSTER_REGISTERED
    - CLUSTER_UPDATED
    - CLUSTER_DELETED
    - CLUSTER_STATUS_CHANGED
    - CLUSTER_CREDENTIALS_UPDATED
    - CLUSTER_CAPABILITIES_CHANGED
    """

    def __init__(self, redis_client: RedisClient):
        self.redis = redis_client

    async def publish(
        self, event_type: EventType, payload: dict[str, Any], cluster_id: UUID | None = None
    ) -> None:
        """Publish an event to Redis.

        Spec Reference: specs/02-cluster-registry.md Section 6
        """
        event = Event(
            event_id=uuid4(),
            event_type=event_type,
            cluster_id=cluster_id,
            timestamp=datetime.utcnow(),
            payload=payload,
        )

        await self.redis.publish_event(event)
        logger.debug("Event published", event_type=event_type.value)

    async def publish_cluster_registered(self, cluster: Any) -> None:
        """Publish CLUSTER_REGISTERED event.

        Spec Reference: specs/02-cluster-registry.md Section 6
        """
        payload = {
            "cluster_id": str(cluster.id),
            "name": cluster.name,
            "cluster_type": cluster.cluster_type,
            "environment": cluster.environment,
        }
        await self.publish(EventType.CLUSTER_REGISTERED, payload, cluster.id)

    async def publish_cluster_updated(self, cluster: Any) -> None:
        """Publish CLUSTER_UPDATED event.

        Spec Reference: specs/02-cluster-registry.md Section 6
        """
        payload = {
            "cluster_id": str(cluster.id),
            "name": cluster.name,
        }
        await self.publish(EventType.CLUSTER_UPDATED, payload, cluster.id)

    async def publish_cluster_deleted(self, cluster_id: UUID) -> None:
        """Publish CLUSTER_DELETED event.

        Spec Reference: specs/02-cluster-registry.md Section 6
        """
        payload = {"cluster_id": str(cluster_id)}
        await self.publish(EventType.CLUSTER_DELETED, payload, cluster_id)

    async def publish_cluster_status_changed(
        self, cluster_id: UUID, old_state: str, new_state: str
    ) -> None:
        """Publish CLUSTER_STATUS_CHANGED event.

        Spec Reference: specs/02-cluster-registry.md Section 6
        """
        payload = {
            "cluster_id": str(cluster_id),
            "old_state": old_state,
            "new_state": new_state,
        }
        await self.publish(EventType.CLUSTER_STATUS_CHANGED, payload, cluster_id)

    async def publish_cluster_credentials_updated(self, cluster_id: UUID) -> None:
        """Publish CLUSTER_CREDENTIALS_UPDATED event.

        Spec Reference: specs/02-cluster-registry.md Section 6
        """
        payload = {"cluster_id": str(cluster_id)}
        await self.publish(EventType.CLUSTER_CREDENTIALS_UPDATED, payload, cluster_id)

    async def publish_cluster_capabilities_changed(
        self, cluster_id: UUID, capabilities: dict[str, Any]
    ) -> None:
        """Publish CLUSTER_CAPABILITIES_CHANGED event.

        Spec Reference: specs/02-cluster-registry.md Section 6
        """
        payload = {
            "cluster_id": str(cluster_id),
            "capabilities": capabilities,
        }
        await self.publish(EventType.CLUSTER_CAPABILITIES_CHANGED, payload, cluster_id)
