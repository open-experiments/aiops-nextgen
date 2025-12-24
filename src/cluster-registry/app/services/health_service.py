"""Health service for cluster health monitoring.

Spec Reference: specs/02-cluster-registry.md Section 5.4, 8
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker

from shared.config import ClusterRegistrySettings
from shared.observability import get_logger
from shared.redis_client import RedisClient
from shared.models.cluster import ClusterState, ClusterType

from ..repositories.cluster_repository import ClusterRepository
from .event_service import EventService

logger = get_logger(__name__)


# Health check intervals per cluster type (seconds)
# Spec Reference: specs/02-cluster-registry.md Section 8.3
HEALTH_CHECK_INTERVALS = {
    ClusterType.HUB.value: 15,
    ClusterType.SPOKE.value: 30,
    ClusterType.EDGE.value: 60,
    ClusterType.FAR_EDGE.value: 120,
}

# Timeout per cluster type (seconds)
HEALTH_CHECK_TIMEOUTS = {
    ClusterType.HUB.value: 5,
    ClusterType.SPOKE.value: 10,
    ClusterType.EDGE.value: 15,
    ClusterType.FAR_EDGE.value: 30,
}


class HealthService:
    """Service for cluster health monitoring.

    Spec Reference: specs/02-cluster-registry.md Section 5.4

    Implements background health checking with intervals based
    on cluster type (Section 8.3).
    """

    def __init__(
        self,
        session_factory: async_sessionmaker,
        redis_client: RedisClient,
        settings: ClusterRegistrySettings,
    ):
        self.session_factory = session_factory
        self.redis = redis_client
        self.settings = settings
        self.event_service = EventService(redis_client)
        self._running = False

    async def check_health(self, cluster_id: UUID) -> dict[str, Any]:
        """Run health check on specific cluster.

        Spec Reference: specs/02-cluster-registry.md Section 5.4, 8.1

        Check sequence:
        1. API Server Check
        2. Prometheus Check (if configured)
        3. Tempo Check (if configured)
        4. Loki Check (if configured)
        5. Calculate Health Score
        """
        async with self.session_factory() as session:
            repo = ClusterRepository(session)
            cluster = await repo.get_by_id(cluster_id)

            if not cluster:
                return {"error": "Cluster not found"}

            # Get current status for comparison
            old_state = cluster.status.get("state", "UNKNOWN")

            # Mock health check - in production would actually test connectivity
            # Spec Reference: specs/02-cluster-registry.md Section 8.1
            new_status = await self._perform_health_check(cluster)

            # Update cluster status
            await repo.update_status(cluster_id, new_status)

            # Add to health history
            await repo.add_health_history(cluster_id, new_status)

            # Publish event if state changed
            new_state = new_status.get("state", "UNKNOWN")
            if old_state != new_state:
                await self.event_service.publish_cluster_status_changed(
                    cluster_id, old_state, new_state
                )
                logger.info(
                    "Cluster state changed",
                    cluster_id=str(cluster_id),
                    old_state=old_state,
                    new_state=new_state,
                )

            return new_status

    async def run_all_checks(self) -> dict[str, dict[str, Any]]:
        """Run health checks on all clusters.

        Spec Reference: specs/02-cluster-registry.md Section 5.4
        """
        results = {}

        async with self.session_factory() as session:
            repo = ClusterRepository(session)
            clusters = await repo.get_all_clusters()

        for cluster in clusters:
            try:
                result = await self.check_health(cluster.id)
                results[str(cluster.id)] = result
            except Exception as e:
                logger.error(
                    "Health check failed",
                    cluster_id=str(cluster.id),
                    error=str(e),
                )
                results[str(cluster.id)] = {"error": str(e)}

        return results

    async def run_periodic_checks(self) -> None:
        """Run periodic health checks in background.

        Spec Reference: specs/02-cluster-registry.md Section 8.3
        """
        self._running = True
        logger.info("Starting periodic health checks")

        while self._running:
            try:
                async with self.session_factory() as session:
                    repo = ClusterRepository(session)
                    clusters = await repo.get_all_clusters()

                for cluster in clusters:
                    try:
                        await self.check_health(cluster.id)
                    except Exception as e:
                        logger.error(
                            "Periodic health check failed",
                            cluster_id=str(cluster.id),
                            error=str(e),
                        )

                # Wait for next check cycle (use minimum interval)
                await asyncio.sleep(self.settings.health_check_interval_seconds)

            except asyncio.CancelledError:
                logger.info("Periodic health checks cancelled")
                break
            except Exception as e:
                logger.error("Error in periodic health check loop", error=str(e))
                await asyncio.sleep(5)  # Brief pause before retry

        self._running = False

    async def get_status(self, cluster_id: UUID) -> dict[str, Any] | None:
        """Get cached status (no new check).

        Spec Reference: specs/02-cluster-registry.md Section 5.4
        """
        async with self.session_factory() as session:
            repo = ClusterRepository(session)
            cluster = await repo.get_by_id(cluster_id)

            if not cluster:
                return None

            return cluster.status

    async def _perform_health_check(self, cluster) -> dict[str, Any]:
        """Perform actual health check on cluster.

        Spec Reference: specs/02-cluster-registry.md Section 8.1

        In local development, this returns mock data.
        In production, this would:
        1. Check API server with kubectl get namespaces
        2. Check Prometheus readiness
        3. Check Tempo readiness
        4. Check Loki readiness
        5. Calculate health score
        """
        endpoints = cluster.endpoints or {}

        # Mock health check results
        # In production, these would be actual connectivity tests
        api_server_ok = True  # Would test: kubectl get namespaces
        prometheus_ok = bool(endpoints.get("prometheus_url"))
        tempo_ok = bool(endpoints.get("tempo_url"))
        loki_ok = bool(endpoints.get("loki_url"))

        # Calculate health score
        # Spec Reference: specs/02-cluster-registry.md Section 8.1
        health_score = 100
        if not api_server_ok:
            health_score -= 50
        if endpoints.get("prometheus_url") and not prometheus_ok:
            health_score -= 20
        if endpoints.get("tempo_url") and not tempo_ok:
            health_score -= 15
        if endpoints.get("loki_url") and not loki_ok:
            health_score -= 15
        health_score = max(0, health_score)

        # Determine state
        # Spec Reference: specs/02-cluster-registry.md Section 8.2
        if not api_server_ok:
            state = ClusterState.OFFLINE.value
        elif health_score < 100:
            state = ClusterState.DEGRADED.value
        else:
            state = ClusterState.ONLINE.value

        return {
            "state": state,
            "health_score": health_score,
            "connectivity": "CONNECTED" if api_server_ok else "DISCONNECTED",
            "last_check_at": datetime.utcnow().isoformat() + "Z",
            "prometheus_healthy": prometheus_ok if endpoints.get("prometheus_url") else None,
            "tempo_healthy": tempo_ok if endpoints.get("tempo_url") else None,
            "loki_healthy": loki_ok if endpoints.get("loki_url") else None,
            "error_message": None,
        }
