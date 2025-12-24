"""GPU API endpoints.

Spec Reference: specs/03-observability-collector.md Section 4.5
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from shared.models.gpu import GPU, GPUNode, GPUProcess
from shared.observability import get_logger

from ..services.gpu_service import GPUService

logger = get_logger(__name__)

router = APIRouter()


class GPUNodeResponse(BaseModel):
    """GPU node response.

    Spec Reference: specs/01-data-models.md Section 4.1
    """

    cluster_id: UUID
    cluster_name: str
    node_name: str
    gpus: list[dict[str, Any]]
    last_updated: datetime


class GPUNodesListResponse(BaseModel):
    """Response for list GPU nodes.

    Spec Reference: specs/03-observability-collector.md Section 4.7
    """

    nodes: list[GPUNodeResponse]
    total: int


class GPUSummaryResponse(BaseModel):
    """Fleet GPU summary response.

    Spec Reference: specs/03-observability-collector.md Section 4.5
    """

    total_nodes: int
    total_gpus: int
    total_memory_gb: float
    used_memory_gb: float
    avg_utilization_percent: float
    gpu_types: dict[str, int]
    clusters_with_gpu: int


@router.get(
    "/gpu/nodes",
    response_model=GPUNodesListResponse,
    summary="List GPU nodes",
    description="List GPU nodes across specified or all clusters.",
)
async def list_gpu_nodes(
    request: Request,
    cluster_id: UUID | None = None,
):
    """List GPU nodes.

    Spec Reference: specs/03-observability-collector.md Section 4.5
    """
    cluster_registry = request.app.state.cluster_registry
    redis = request.app.state.redis

    service = GPUService(cluster_registry, redis)

    cluster_ids = [cluster_id] if cluster_id else []

    try:
        nodes = await service.get_nodes(cluster_ids=cluster_ids)
        return nodes
    except Exception as e:
        logger.error("List GPU nodes failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/gpu/nodes/{cluster_id}/{node_name}",
    response_model=GPUNodeResponse,
    summary="Get GPU node details",
    description="Get detailed GPU information for specific node.",
)
async def get_gpu_node(
    request: Request,
    cluster_id: UUID,
    node_name: str,
):
    """Get GPU node details.

    Spec Reference: specs/03-observability-collector.md Section 4.5
    """
    cluster_registry = request.app.state.cluster_registry
    redis = request.app.state.redis

    service = GPUService(cluster_registry, redis)

    try:
        node = await service.get_node_details(cluster_id, node_name)
        if not node:
            raise HTTPException(status_code=404, detail="GPU node not found")
        return node
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Get GPU node failed",
            error=str(e),
            cluster_id=str(cluster_id),
            node_name=node_name,
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/gpu/summary",
    response_model=GPUSummaryResponse,
    summary="Get fleet GPU summary",
    description="Get aggregated GPU summary across the fleet.",
)
async def get_gpu_summary(request: Request):
    """Get fleet GPU summary.

    Spec Reference: specs/03-observability-collector.md Section 4.5
    """
    cluster_registry = request.app.state.cluster_registry
    redis = request.app.state.redis

    service = GPUService(cluster_registry, redis)

    try:
        summary = await service.get_summary()
        return summary
    except Exception as e:
        logger.error("Get GPU summary failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/gpu/processes",
    summary="List GPU processes",
    description="List running GPU processes across specified or all clusters.",
)
async def list_gpu_processes(
    request: Request,
    cluster_id: UUID | None = None,
):
    """List GPU processes.

    Spec Reference: specs/03-observability-collector.md Section 4.5
    """
    cluster_registry = request.app.state.cluster_registry
    redis = request.app.state.redis

    service = GPUService(cluster_registry, redis)

    cluster_ids = [cluster_id] if cluster_id else []

    try:
        processes = await service.get_processes(cluster_ids=cluster_ids)
        return {"processes": processes, "total": len(processes)}
    except Exception as e:
        logger.error("List GPU processes failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
