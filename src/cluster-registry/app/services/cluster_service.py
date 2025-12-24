"""Cluster service for CRUD operations.

Spec Reference: specs/02-cluster-registry.md Section 5.1
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shared.observability import get_logger
from shared.redis_client import RedisClient

from ..repositories.cluster_repository import ClusterRepository
from ..schemas.cluster import (
    ClusterCreateRequest,
    ClusterUpdateRequest,
    ClusterResponse,
    ClusterListResponse,
    ClusterFilters,
    ClusterStatus,
    ClusterCapabilities,
    ClusterEndpoints,
)
from ..schemas.fleet import FleetSummary
from .event_service import EventService

logger = get_logger(__name__)


class ClusterNotFoundError(Exception):
    """Raised when a cluster is not found."""

    pass


class ClusterAlreadyExistsError(Exception):
    """Raised when a cluster with the same name already exists."""

    pass


class ClusterService:
    """Service for cluster CRUD operations.

    Spec Reference: specs/02-cluster-registry.md Section 5.1
    """

    def __init__(
        self,
        session: AsyncSession,
        redis_client: RedisClient,
    ):
        self.repository = ClusterRepository(session)
        self.event_service = EventService(redis_client)

    async def create(self, request: ClusterCreateRequest) -> ClusterResponse:
        """Register a new cluster.

        Spec Reference: specs/02-cluster-registry.md Section 5.1
        """
        # Check if cluster with same name exists
        existing = await self.repository.get_by_name(request.name)
        if existing:
            raise ClusterAlreadyExistsError(
                f"Cluster with name '{request.name}' already exists"
            )

        # Prepare cluster data
        cluster_data = {
            "name": request.name,
            "display_name": request.display_name or request.name,
            "api_server_url": request.api_server_url,
            "cluster_type": request.cluster_type.value,
            "platform": request.platform.value,
            "platform_version": request.platform_version,
            "region": request.region,
            "environment": request.environment.value,
            "labels": request.labels,
            "endpoints": request.endpoints.model_dump() if request.endpoints else {},
            "status": {
                "state": "UNKNOWN",
                "health_score": 0,
                "connectivity": "DISCONNECTED",
            },
            "capabilities": None,
        }

        cluster = await self.repository.create(cluster_data)

        logger.info("Cluster registered", cluster_id=str(cluster.id), name=cluster.name)

        # Publish event
        await self.event_service.publish_cluster_registered(
            self._to_response(cluster)
        )

        return self._to_response(cluster)

    async def get(self, cluster_id: UUID) -> ClusterResponse:
        """Get cluster by ID.

        Spec Reference: specs/02-cluster-registry.md Section 5.1
        """
        cluster = await self.repository.get_by_id(cluster_id)
        if not cluster:
            raise ClusterNotFoundError(f"Cluster with ID '{cluster_id}' not found")
        return self._to_response(cluster)

    async def get_by_name(self, name: str) -> ClusterResponse:
        """Get cluster by name.

        Spec Reference: specs/02-cluster-registry.md Section 4.1
        """
        cluster = await self.repository.get_by_name(name)
        if not cluster:
            raise ClusterNotFoundError(f"Cluster with name '{name}' not found")
        return self._to_response(cluster)

    async def list(self, filters: ClusterFilters) -> ClusterListResponse:
        """List clusters with filtering and pagination.

        Spec Reference: specs/02-cluster-registry.md Section 5.1
        """
        clusters, total = await self.repository.list(filters)

        total_pages = (total + filters.page_size - 1) // filters.page_size

        return ClusterListResponse(
            items=[self._to_response(c) for c in clusters],
            total=total,
            page=filters.page,
            page_size=filters.page_size,
            total_pages=total_pages,
        )

    async def update(
        self, cluster_id: UUID, request: ClusterUpdateRequest
    ) -> ClusterResponse:
        """Update cluster metadata.

        Spec Reference: specs/02-cluster-registry.md Section 5.1
        """
        cluster = await self.repository.get_by_id(cluster_id)
        if not cluster:
            raise ClusterNotFoundError(f"Cluster with ID '{cluster_id}' not found")

        update_data = {}
        if request.display_name is not None:
            update_data["display_name"] = request.display_name
        if request.cluster_type is not None:
            update_data["cluster_type"] = request.cluster_type.value
        if request.platform_version is not None:
            update_data["platform_version"] = request.platform_version
        if request.region is not None:
            update_data["region"] = request.region
        if request.environment is not None:
            update_data["environment"] = request.environment.value
        if request.labels is not None:
            update_data["labels"] = request.labels
        if request.endpoints is not None:
            update_data["endpoints"] = request.endpoints.model_dump()

        if update_data:
            cluster = await self.repository.update(cluster_id, update_data)

        logger.info("Cluster updated", cluster_id=str(cluster_id))

        # Publish event
        await self.event_service.publish_cluster_updated(
            self._to_response(cluster)
        )

        return self._to_response(cluster)

    async def delete(self, cluster_id: UUID) -> None:
        """Delete a cluster.

        Spec Reference: specs/02-cluster-registry.md Section 5.1
        """
        cluster = await self.repository.get_by_id(cluster_id)
        if not cluster:
            raise ClusterNotFoundError(f"Cluster with ID '{cluster_id}' not found")

        deleted = await self.repository.delete(cluster_id)
        if not deleted:
            raise ClusterNotFoundError(f"Cluster with ID '{cluster_id}' not found")

        logger.info("Cluster deleted", cluster_id=str(cluster_id))

        # Publish event
        await self.event_service.publish_cluster_deleted(cluster_id)

    async def refresh(self, cluster_id: UUID) -> ClusterResponse:
        """Force refresh cluster status and capabilities.

        Spec Reference: specs/02-cluster-registry.md Section 5.1
        """
        cluster = await self.repository.get_by_id(cluster_id)
        if not cluster:
            raise ClusterNotFoundError(f"Cluster with ID '{cluster_id}' not found")

        # TODO: Trigger actual health check and capability discovery
        logger.info("Cluster refresh requested", cluster_id=str(cluster_id))

        return self._to_response(cluster)

    async def get_fleet_summary(self) -> FleetSummary:
        """Get fleet summary statistics.

        Spec Reference: specs/02-cluster-registry.md Section 4.2
        """
        summary_data = await self.repository.get_fleet_summary()
        return FleetSummary(**summary_data)

    def _to_response(self, cluster) -> ClusterResponse:
        """Convert database model to response schema."""
        status_data = cluster.status or {}
        capabilities_data = cluster.capabilities
        endpoints_data = cluster.endpoints or {}

        return ClusterResponse(
            id=cluster.id,
            name=cluster.name,
            display_name=cluster.display_name,
            api_server_url=cluster.api_server_url,
            cluster_type=cluster.cluster_type,
            platform=cluster.platform,
            platform_version=cluster.platform_version,
            region=cluster.region,
            environment=cluster.environment,
            status=ClusterStatus(**status_data),
            capabilities=ClusterCapabilities(**capabilities_data)
            if capabilities_data
            else None,
            endpoints=ClusterEndpoints(**endpoints_data),
            labels=cluster.labels or {},
            created_at=cluster.created_at,
            updated_at=cluster.updated_at,
            last_seen_at=cluster.last_seen_at,
        )
