"""CNF API endpoints for PTP, SR-IOV, and DPDK telemetry.

Spec Reference: specs/03-observability-collector.md Section 4.6
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from shared.observability import get_logger

from ..services.cnf_service import CNFService

logger = get_logger(__name__)

router = APIRouter(prefix="/cnf", tags=["CNF"])


# =============================================================================
# Response Models
# =============================================================================


class CNFWorkload(BaseModel):
    """CNF workload information."""

    cluster_id: str
    cluster_name: str
    namespace: str
    name: str
    type: str = Field(description="CNF type (vDU, vCU, UPF, etc.)")
    status: str
    node: str
    containers: list[str]
    last_updated: datetime


class CNFWorkloadsResponse(BaseModel):
    """Response for CNF workloads list."""

    workloads: list[CNFWorkload]
    total: int
    clusters_queried: int


class PTPStatus(BaseModel):
    """PTP synchronization status."""

    cluster_id: str
    cluster_name: str
    node: str
    interface: str
    state: str = Field(description="LOCKED, FREERUN, or HOLDOVER")
    offset_ns: float = Field(description="Current offset from grandmaster in ns")
    max_offset_ns: float = Field(description="Maximum allowed offset in ns")
    clock_accuracy: str = Field(description="HIGH, MEDIUM, or LOW")
    grandmaster: str = Field(description="Grandmaster clock identifier")
    last_updated: datetime


class PTPSummary(BaseModel):
    """PTP status summary."""

    locked: int
    freerun: int
    avg_offset_ns: float


class PTPStatusResponse(BaseModel):
    """Response for PTP status."""

    statuses: list[PTPStatus]
    total: int
    summary: PTPSummary
    clusters_queried: int


class SRIOVVirtualFunction(BaseModel):
    """SR-IOV Virtual Function information."""

    vf_id: int
    mac: str
    vlan: int | None = None


class SRIOVStatus(BaseModel):
    """SR-IOV interface status."""

    cluster_id: str
    cluster_name: str
    node: str
    interface: str
    pci_address: str
    driver: str
    vendor: str
    device_id: str
    total_vfs: int
    configured_vfs: int
    vfs: list[dict[str, Any]] = Field(default_factory=list)
    mtu: int
    link_speed: str
    last_updated: datetime


class SRIOVSummary(BaseModel):
    """SR-IOV status summary."""

    total_vfs_capacity: int
    configured_vfs: int
    utilization_percent: float


class SRIOVStatusResponse(BaseModel):
    """Response for SR-IOV status."""

    statuses: list[SRIOVStatus]
    total: int
    summary: SRIOVSummary
    clusters_queried: int


class DPDKPort(BaseModel):
    """DPDK port statistics."""

    port_id: int
    rx_packets: int
    tx_packets: int
    rx_bytes: int
    tx_bytes: int
    rx_errors: int
    tx_errors: int
    rx_dropped: int
    tx_dropped: int


class DPDKStatsResponse(BaseModel):
    """Response for DPDK statistics."""

    cluster_id: str
    cluster_name: str
    namespace: str
    pod_name: str
    ports: list[DPDKPort]
    cpu_cycles: int | None = None
    instructions: int | None = None
    cache_misses: int | None = None
    last_updated: datetime


class CNFSummaryResponse(BaseModel):
    """Fleet-wide CNF summary."""

    workloads: dict[str, Any]
    ptp: dict[str, Any]
    sriov: dict[str, Any]


# =============================================================================
# API Endpoints
# =============================================================================


@router.get(
    "/workloads",
    response_model=CNFWorkloadsResponse,
    summary="List CNF workloads",
    description="List CNF workloads (vDU, vCU, UPF, etc.) across clusters.",
)
async def list_cnf_workloads(
    request: Request,
    cluster_id: UUID | None = Query(None, description="Filter by cluster"),
    workload_type: str | None = Query(None, description="Filter by CNF type"),
):
    """List CNF workloads.

    Spec Reference: specs/03-observability-collector.md Section 4.6
    """
    cluster_registry = request.app.state.cluster_registry
    redis = request.app.state.redis

    service = CNFService(cluster_registry, redis)

    cluster_ids = [cluster_id] if cluster_id else None

    try:
        result = await service.get_workloads(
            cluster_ids=cluster_ids,
            workload_type=workload_type,
        )
        return result
    except Exception as e:
        logger.error("List CNF workloads failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from None


@router.get(
    "/ptp/status",
    response_model=PTPStatusResponse,
    summary="Get PTP sync status",
    description="Get PTP synchronization status across clusters.",
)
async def get_ptp_status(
    request: Request,
    cluster_id: UUID | None = Query(None, description="Filter by cluster"),
):
    """Get PTP synchronization status.

    Spec Reference: specs/03-observability-collector.md Section 4.6

    Returns PTP status including:
    - Sync state (LOCKED, FREERUN, HOLDOVER)
    - Offset from grandmaster clock
    - Clock accuracy
    """
    cluster_registry = request.app.state.cluster_registry
    redis = request.app.state.redis

    service = CNFService(cluster_registry, redis)

    cluster_ids = [cluster_id] if cluster_id else None

    try:
        result = await service.get_ptp_status(cluster_ids=cluster_ids)
        return result
    except Exception as e:
        logger.error("Get PTP status failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from None


@router.get(
    "/sriov/status",
    response_model=SRIOVStatusResponse,
    summary="Get SR-IOV VF status",
    description="Get SR-IOV Virtual Function allocation status across clusters.",
)
async def get_sriov_status(
    request: Request,
    cluster_id: UUID | None = Query(None, description="Filter by cluster"),
):
    """Get SR-IOV VF allocation status.

    Spec Reference: specs/03-observability-collector.md Section 4.6

    Returns SR-IOV status including:
    - Physical function interfaces
    - VF allocation and configuration
    - Network device information
    """
    cluster_registry = request.app.state.cluster_registry
    redis = request.app.state.redis

    service = CNFService(cluster_registry, redis)

    cluster_ids = [cluster_id] if cluster_id else None

    try:
        result = await service.get_sriov_status(cluster_ids=cluster_ids)
        return result
    except Exception as e:
        logger.error("Get SR-IOV status failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from None


@router.get(
    "/dpdk/stats/{cluster_id}/{namespace}/{pod_name}",
    response_model=DPDKStatsResponse,
    summary="Get DPDK statistics",
    description="Get DPDK packet processing statistics for a specific pod.",
)
async def get_dpdk_stats(
    request: Request,
    cluster_id: UUID,
    namespace: str,
    pod_name: str,
):
    """Get DPDK statistics for a pod.

    Spec Reference: specs/03-observability-collector.md Section 4.6

    Returns DPDK statistics including:
    - Per-port packet and byte counters
    - Error and drop statistics
    - CPU performance counters (if available)
    """
    cluster_registry = request.app.state.cluster_registry
    redis = request.app.state.redis

    service = CNFService(cluster_registry, redis)

    try:
        result = await service.get_dpdk_stats(
            cluster_id=cluster_id,
            namespace=namespace,
            pod_name=pod_name,
        )
        if not result:
            raise HTTPException(status_code=404, detail="DPDK stats not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Get DPDK stats failed",
            error=str(e),
            cluster_id=str(cluster_id),
            pod_name=pod_name,
        )
        raise HTTPException(status_code=500, detail=str(e)) from None


@router.get(
    "/summary",
    response_model=CNFSummaryResponse,
    summary="Get CNF summary",
    description="Get fleet-wide CNF summary including workloads, PTP, and SR-IOV.",
)
async def get_cnf_summary(request: Request):
    """Get fleet-wide CNF summary.

    Spec Reference: specs/03-observability-collector.md Section 4.6

    Returns aggregated summary of:
    - CNF workloads by type
    - PTP synchronization status
    - SR-IOV VF utilization
    """
    cluster_registry = request.app.state.cluster_registry
    redis = request.app.state.redis

    service = CNFService(cluster_registry, redis)

    try:
        result = await service.get_summary()
        return result
    except Exception as e:
        logger.error("Get CNF summary failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from None
