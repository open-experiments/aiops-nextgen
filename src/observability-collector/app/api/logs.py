"""Logs API endpoints for LogQL queries.

Spec Reference: specs/03-observability-collector.md Section 4.3
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.services.logs_service import LogsService
from shared.observability import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/logs", tags=["Logs"])


class LogQueryRequest(BaseModel):
    """Request for log query."""

    query: str = Field(..., description="LogQL query string")
    cluster_id: str | None = Field(None, description="Specific cluster to query")
    limit: int = Field(100, ge=1, le=5000, description="Maximum entries to return")
    time: datetime | None = Field(None, description="Evaluation timestamp")
    direction: str = Field("backward", description="Log direction (forward/backward)")


class LogRangeQueryRequest(BaseModel):
    """Request for range log query."""

    query: str = Field(..., description="LogQL query string")
    cluster_id: str | None = Field(None, description="Specific cluster to query")
    start: datetime = Field(..., description="Query start time")
    end: datetime = Field(..., description="Query end time")
    limit: int = Field(1000, ge=1, le=5000, description="Maximum entries")
    step: str | None = Field(None, description="Query step for metric queries")
    direction: str = Field("backward", description="Log direction")


class LogQueryResponse(BaseModel):
    """Response for log queries."""

    results: list[dict[str, Any]]
    total_query_time_ms: int
    clusters_queried: int
    clusters_succeeded: int


class LabelsResponse(BaseModel):
    """Response for labels query."""

    labels: list[str]
    cluster_id: str | None


class LabelValuesResponse(BaseModel):
    """Response for label values query."""

    values: list[str]
    label: str
    cluster_id: str | None


# Singleton service
_logs_service: LogsService | None = None


def get_logs_service() -> LogsService:
    """Get or create logs service instance."""
    global _logs_service
    if _logs_service is None:
        _logs_service = LogsService()
    return _logs_service


@router.post("/query", response_model=LogQueryResponse)
async def query_logs(request: LogQueryRequest) -> LogQueryResponse:
    """Execute instant LogQL query across clusters.

    Spec Reference: specs/03-observability-collector.md Section 4.3
    """
    service = get_logs_service()

    start_time = datetime.now()
    results = await service.query(
        query=request.query,
        cluster_id=request.cluster_id,
        limit=request.limit,
        time=request.time,
        direction=request.direction,
    )
    query_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

    succeeded = sum(1 for r in results if r.get("status") == "SUCCESS")

    return LogQueryResponse(
        results=results,
        total_query_time_ms=query_time_ms,
        clusters_queried=len(results),
        clusters_succeeded=succeeded,
    )


@router.post("/query_range", response_model=LogQueryResponse)
async def query_logs_range(request: LogRangeQueryRequest) -> LogQueryResponse:
    """Execute range LogQL query across clusters.

    Spec Reference: specs/03-observability-collector.md Section 4.3
    """
    service = get_logs_service()

    start_time = datetime.now()
    results = await service.query_range(
        query=request.query,
        cluster_id=request.cluster_id,
        start_time=request.start,
        end_time=request.end,
        limit=request.limit,
        step=request.step,
        direction=request.direction,
    )
    query_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

    succeeded = sum(1 for r in results if r.get("status") == "SUCCESS")

    return LogQueryResponse(
        results=results,
        total_query_time_ms=query_time_ms,
        clusters_queried=len(results),
        clusters_succeeded=succeeded,
    )


@router.get("/labels", response_model=LabelsResponse)
async def get_labels(
    cluster_id: str | None = Query(None, description="Specific cluster"),
) -> LabelsResponse:
    """Get available log label names.

    Spec Reference: specs/03-observability-collector.md Section 4.3
    """
    service = get_logs_service()
    labels = await service.get_labels(cluster_id=cluster_id)

    return LabelsResponse(
        labels=labels,
        cluster_id=cluster_id,
    )


@router.get("/label/{name}/values", response_model=LabelValuesResponse)
async def get_label_values(
    name: str,
    cluster_id: str | None = Query(None, description="Specific cluster"),
) -> LabelValuesResponse:
    """Get values for a specific log label.

    Spec Reference: specs/03-observability-collector.md Section 4.3
    """
    service = get_logs_service()
    values = await service.get_label_values(label=name, cluster_id=cluster_id)

    return LabelValuesResponse(
        values=values,
        label=name,
        cluster_id=cluster_id,
    )
