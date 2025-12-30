"""Alerts service for handling Alertmanager alerts.

Spec Reference: specs/03-observability-collector.md Section 5.4
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from shared.models.events import Event, EventType
from shared.models.observability import AlertSeverity, AlertState
from shared.observability import get_logger
from shared.redis_client import RedisClient, RedisDB

logger = get_logger(__name__)


class AlertsService:
    """Service for managing alerts.

    Spec Reference: specs/03-observability-collector.md Section 5.4
    """

    ALERT_CACHE_TTL = 86400  # 24 hours
    ACTIVE_ALERTS_CACHE_TTL = 10  # 10 seconds

    def __init__(self, redis: RedisClient):
        self.redis = redis

    async def list_alerts(
        self,
        cluster_ids: list[UUID] | None = None,
        state: AlertState | None = None,
        severity: AlertSeverity | None = None,
    ) -> dict[str, Any]:
        """List alerts from cache.

        Spec Reference: specs/03-observability-collector.md Section 5.4
        """
        # Get all alert keys from cache DB
        cache_client = self.redis.get_client(RedisDB.CACHE)
        pattern = "cache:alerts:*"

        alerts = []
        by_severity = {"CRITICAL": 0, "WARNING": 0, "INFO": 0}

        async for key in cache_client.scan_iter(match=pattern):
            alert_data = await cache_client.get(key)
            if not alert_data:
                continue

            # Parse alert
            if isinstance(alert_data, str):
                alert = json.loads(alert_data)
            else:
                alert = alert_data

            # Filter by cluster
            if cluster_ids and alert.get("cluster_id") not in [str(c) for c in cluster_ids]:
                continue

            # Filter by state
            if state and alert.get("state") != state.value:
                continue

            # Filter by severity
            if severity and alert.get("severity") != severity.value:
                continue

            alerts.append(alert)
            sev = alert.get("severity", "INFO")
            if sev in by_severity:
                by_severity[sev] += 1

        return {
            "alerts": alerts,
            "total": len(alerts),
            "by_severity": by_severity,
        }

    async def get_alert(self, fingerprint: str) -> dict[str, Any] | None:
        """Get alert by fingerprint.

        Spec Reference: specs/03-observability-collector.md Section 5.4
        """
        cache_key = fingerprint
        return await self.redis.cache_get_json("alerts", cache_key)

    async def receive_webhook(
        self,
        cluster_id: UUID,
        payload: Any,
    ) -> None:
        """Process incoming Alertmanager webhook.

        Spec Reference: specs/03-observability-collector.md Section 6.3
        """
        logger.info(
            "Received Alertmanager webhook",
            cluster_id=str(cluster_id),
            alerts_count=len(payload.alerts),
        )

        for alert_data in payload.alerts:
            # Create alert model
            alert = {
                "id": str(uuid4()),
                "fingerprint": alert_data.fingerprint,
                "cluster_id": str(cluster_id),
                "cluster_name": f"cluster-{str(cluster_id)[:8]}",  # Will be resolved
                "alertname": alert_data.labels.get("alertname", "Unknown"),
                "severity": alert_data.labels.get("severity", "WARNING").upper(),
                "state": "FIRING" if alert_data.status == "firing" else "RESOLVED",
                "labels": alert_data.labels,
                "annotations": alert_data.annotations,
                "starts_at": alert_data.startsAt,
                "ends_at": alert_data.endsAt,
                "generator_url": alert_data.generatorURL,
            }

            # Store in cache
            cache_key = alert_data.fingerprint
            await self.redis.cache_set("alerts", cache_key, alert, self.ALERT_CACHE_TTL)

            # Publish event
            event_type = (
                EventType.ALERT_FIRED if alert["state"] == "FIRING" else EventType.ALERT_RESOLVED
            )

            event = Event(
                event_id=uuid4(),
                event_type=event_type,
                cluster_id=cluster_id,
                timestamp=datetime.utcnow(),
                payload=alert,
            )

            await self.redis.publish_event(event)

            logger.info(
                "Alert processed",
                fingerprint=alert_data.fingerprint,
                alertname=alert["alertname"],
                state=alert["state"],
            )
