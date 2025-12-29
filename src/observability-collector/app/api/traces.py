"""Traces API endpoints for distributed tracing.

Spec Reference: specs/03-observability-collector.md Section 4.2
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.services.traces_service import TracesService
from shared.observability import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/traces", tags=["Traces"])


class TraceSearchRequest(BaseModel):
    """Request for trace search."""

    cluster_id: str | None = Field(None, description="Specific cluster to query")
    service_name: str | None = Field(None, description="Filter by service name")
    operation: str | None = Field(None, description="Filter by operation name")
    tags: dict[str, str] | None = Field(None, description="Filter by span tags")
    min_duration: str | None = Field(None, description="Minimum duration (e.g., '100ms')")
    max_duration: str | None = Field(None, description="Maximum duration (e.g., '1s')")
    start: datetime | None = Field(None, description="Search start time")
    end: datetime | None = Field(None, description="Search end time")
    limit: int = Field(20, ge=1, le=100, description="Maximum traces to return")


class TraceSummary(BaseModel):
    """Summary of a trace from search results."""

    trace_id: str = Field(..., alias="traceID")
    root_service_name: str = Field(..., alias="rootServiceName")
    root_trace_name: str = Field(..., alias="rootTraceName")
    start_time_unix_nano: int = Field(..., alias="startTimeUnixNano")
    duration_ms: float = Field(..., alias="durationMs")
    span_count: int = Field(..., alias="spanCount")

    model_config = {"populate_by_name": True}


class TraceSearchResponse(BaseModel):
    """Response for trace search."""

    results: list[dict[str, Any]]
    total_query_time_ms: int
    clusters_queried: int
    clusters_succeeded: int


class TraceDetail(BaseModel):
    """Detailed trace information."""

    trace_id: str = Field(..., alias="traceID")
    spans: list[dict[str, Any]]
    span_count: int = Field(..., alias="spanCount")
    services: list[str]

    model_config = {"populate_by_name": True}


class TraceResponse(BaseModel):
    """Response for single trace retrieval."""

    cluster_id: str
    cluster_name: str
    status: str
    error: str | None = None
    trace: TraceDetail | None = None


class ServicesResponse(BaseModel):
    """Response for services list."""

    services: list[str]
    cluster_id: str | None


class OperationsResponse(BaseModel):
    """Response for operations list."""

    operations: list[str]
    service: str
    cluster_id: str | None


class ServiceGraphNode(BaseModel):
    """Node in service graph."""

    id: str
    label: str


class ServiceGraphEdge(BaseModel):
    """Edge in service graph."""

    source: str
    target: str
    weight: int


class ServiceGraphResponse(BaseModel):
    """Response for service dependency graph."""

    nodes: list[ServiceGraphNode]
    edges: list[ServiceGraphEdge]
    cluster_id: str | None


# Singleton service
_traces_service: TracesService | None = None


def get_traces_service() -> TracesService:
    """Get or create traces service instance."""
    global _traces_service
    if _traces_service is None:
        _traces_service = TracesService()
    return _traces_service


@router.post("/search", response_model=TraceSearchResponse)
async def search_traces(request: TraceSearchRequest) -> TraceSearchResponse:
    """Search traces across clusters by criteria.

    Spec Reference: specs/03-observability-collector.md Section 4.2
    """
    service = get_traces_service()

    start_time = datetime.now()
    results = await service.search(
        cluster_id=request.cluster_id,
        service_name=request.service_name,
        operation=request.operation,
        tags=request.tags,
        min_duration=request.min_duration,
        max_duration=request.max_duration,
        start_time=request.start,
        end_time=request.end,
        limit=request.limit,
    )
    query_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

    succeeded = sum(1 for r in results if r.get("status") == "SUCCESS")

    return TraceSearchResponse(
        results=results,
        total_query_time_ms=query_time_ms,
        clusters_queried=len(results),
        clusters_succeeded=succeeded,
    )


# NOTE: Static routes MUST be defined before parameterized routes
# to prevent /{trace_id} from matching /services, /operations, /dependencies


@router.get("/services", response_model=ServicesResponse)
async def get_services(
    cluster_id: str | None = Query(None, description="Specific cluster"),
) -> ServicesResponse:
    """Get list of services with traces.

    Spec Reference: specs/03-observability-collector.md Section 4.2
    """
    service = get_traces_service()
    services = await service.get_services(cluster_id=cluster_id)

    return ServicesResponse(
        services=services,
        cluster_id=cluster_id,
    )


@router.get("/operations", response_model=OperationsResponse)
async def get_operations(
    service_name: str = Query(..., description="Service name"),
    cluster_id: str | None = Query(None, description="Specific cluster"),
) -> OperationsResponse:
    """Get operations/span names for a service.

    Spec Reference: specs/03-observability-collector.md Section 4.2
    """
    svc = get_traces_service()
    operations = await svc.get_operations(
        service_name=service_name,
        cluster_id=cluster_id,
    )

    return OperationsResponse(
        operations=operations,
        service=service_name,
        cluster_id=cluster_id,
    )


@router.get("/dependencies", response_model=ServiceGraphResponse)
async def get_service_graph(
    cluster_id: str | None = Query(None, description="Specific cluster"),
    start: datetime | None = Query(None, description="Start time"),
    end: datetime | None = Query(None, description="End time"),
) -> ServiceGraphResponse:
    """Get service dependency graph.

    Spec Reference: specs/03-observability-collector.md Section 4.2
    """
    service = get_traces_service()
    graph = await service.get_service_graph(
        cluster_id=cluster_id,
        start_time=start,
        end_time=end,
    )

    return ServiceGraphResponse(
        nodes=[ServiceGraphNode(**n) for n in graph.get("nodes", [])],
        edges=[ServiceGraphEdge(**e) for e in graph.get("edges", [])],
        cluster_id=cluster_id,
    )


# Parameterized routes - MUST come after static routes


@router.get("/{trace_id}")
async def get_trace(
    trace_id: str,
    cluster_id: str | None = Query(None, description="Specific cluster to query"),
) -> TraceResponse:
    """Get a specific trace by ID.

    Spec Reference: specs/03-observability-collector.md Section 4.2
    """
    service = get_traces_service()
    result = await service.get_trace(trace_id=trace_id, cluster_id=cluster_id)

    return TraceResponse(
        cluster_id=result.get("cluster_id", ""),
        cluster_name=result.get("cluster_name", ""),
        status=result.get("status", "ERROR"),
        error=result.get("error"),
        trace=result.get("trace"),
    )


@router.get("/{trace_id}/spans")
async def get_trace_spans(
    trace_id: str,
    cluster_id: str | None = Query(None, description="Specific cluster to query"),
) -> dict[str, Any]:
    """Get spans for a specific trace.

    Spec Reference: specs/03-observability-collector.md Section 4.2
    """
    service = get_traces_service()
    result = await service.get_trace(trace_id=trace_id, cluster_id=cluster_id)

    if result.get("status") != "SUCCESS":
        return {
            "trace_id": trace_id,
            "status": result.get("status"),
            "error": result.get("error"),
            "spans": [],
        }

    trace = result.get("trace", {})
    return {
        "trace_id": trace_id,
        "status": "SUCCESS",
        "spans": trace.get("spans", []),
        "span_count": trace.get("spanCount", 0),
    }
