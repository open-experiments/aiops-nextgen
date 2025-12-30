"""Fleet operations API endpoints.

Spec Reference: specs/02-cluster-registry.md Section 4.1 - Fleet Operations
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from shared.observability import get_logger

from ..schemas.cluster import ClusterFilters
from ..schemas.fleet import ClusterHealthSummary, FleetHealth, FleetSummary
from ..services.cluster_service import ClusterService

logger = get_logger(__name__)

router = APIRouter()


@router.get(
    "/fleet/summary",
    response_model=FleetSummary,
    summary="Get fleet summary",
    description="Get summary statistics for the entire fleet.",
)
async def get_fleet_summary(request: Request):
    """Get fleet summary statistics.

    Spec Reference: specs/02-cluster-registry.md Section 4.1, 4.2
    """
    session_factory = request.app.state.session_factory
    redis = request.app.state.redis

    async with session_factory() as session:
        service = ClusterService(session, redis)
        return await service.get_fleet_summary()


@router.get(
    "/fleet/health",
    response_model=FleetHealth,
    summary="Get fleet health",
    description="Get health overview for all clusters.",
)
async def get_fleet_health(request: Request):
    """Get fleet health overview.

    Spec Reference: specs/02-cluster-registry.md Section 4.1
    """
    session_factory = request.app.state.session_factory
    redis = request.app.state.redis

    async with session_factory() as session:
        service = ClusterService(session, redis)

        # Get all clusters with pagination
        all_clusters = []
        page = 1
        page_size = 100  # Max allowed by ClusterFilters

        while True:
            filters = ClusterFilters(page=page, page_size=page_size)
            result = await service.list(filters)
            all_clusters.extend(result.items)

            if page >= result.total_pages:
                break
            page += 1

        # Calculate health summary
        healthy = 0
        degraded = 0
        offline = 0
        unknown = 0
        cluster_summaries = []

        for cluster in all_clusters:
            state = cluster.status.state.value if cluster.status else "UNKNOWN"

            if state == "ONLINE":
                healthy += 1
            elif state == "DEGRADED":
                degraded += 1
            elif state == "OFFLINE":
                offline += 1
            else:
                unknown += 1

            cluster_summaries.append(
                ClusterHealthSummary(
                    cluster_id=str(cluster.id),
                    cluster_name=cluster.name,
                    state=state,
                    health_score=cluster.status.health_score if cluster.status else 0,
                    last_check_at=cluster.status.last_check_at.isoformat()
                    if cluster.status and cluster.status.last_check_at
                    else None,
                )
            )

        return FleetHealth(
            total_clusters=len(all_clusters),
            healthy=healthy,
            degraded=degraded,
            offline=offline,
            unknown=unknown,
            clusters=cluster_summaries,
        )


@router.get(
    "/fleet/capabilities",
    summary="Get fleet capabilities",
    description="Get aggregated capabilities across the fleet.",
)
async def get_fleet_capabilities(request: Request):
    """Get aggregated fleet capabilities.

    Spec Reference: specs/02-cluster-registry.md Section 4.1
    """
    session_factory = request.app.state.session_factory
    redis = request.app.state.redis

    async with session_factory() as session:
        service = ClusterService(session, redis)

        # Get all clusters with pagination
        all_clusters = []
        page = 1
        page_size = 100  # Max allowed by ClusterFilters

        while True:
            filters = ClusterFilters(page=page, page_size=page_size)
            result = await service.list(filters)
            all_clusters.extend(result.items)

            if page >= result.total_pages:
                break
            page += 1

        # Aggregate capabilities
        total_gpus = 0
        gpu_types = set()
        cnf_types = set()
        clusters_with_gpu = 0
        clusters_with_cnf = 0
        clusters_with_prometheus = 0
        clusters_with_tempo = 0
        clusters_with_loki = 0

        for cluster in all_clusters:
            if cluster.capabilities:
                if cluster.capabilities.has_gpu_nodes:
                    clusters_with_gpu += 1
                    total_gpus += cluster.capabilities.gpu_count
                    gpu_types.update(cluster.capabilities.gpu_types)

                if cluster.capabilities.has_cnf_workloads:
                    clusters_with_cnf += 1
                    cnf_types.update(cluster.capabilities.cnf_types)

                if cluster.capabilities.has_prometheus:
                    clusters_with_prometheus += 1
                if cluster.capabilities.has_tempo:
                    clusters_with_tempo += 1
                if cluster.capabilities.has_loki:
                    clusters_with_loki += 1

        return {
            "total_clusters": len(all_clusters),
            "gpu": {
                "total_gpu_count": total_gpus,
                "gpu_types": list(gpu_types),
                "clusters_with_gpu": clusters_with_gpu,
            },
            "cnf": {
                "cnf_types": list(cnf_types),
                "clusters_with_cnf": clusters_with_cnf,
            },
            "observability": {
                "clusters_with_prometheus": clusters_with_prometheus,
                "clusters_with_tempo": clusters_with_tempo,
                "clusters_with_loki": clusters_with_loki,
            },
        }
