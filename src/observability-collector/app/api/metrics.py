"""Metrics API endpoints.

Spec Reference: specs/03-observability-collector.md Section 4.1
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from shared.observability import get_logger

from ..services.metrics_service import MetricsService

logger = get_logger(__name__)

router = APIRouter()


class MetricQueryRequest(BaseModel):
    """Request for instant metric query.

    Spec Reference: specs/01-data-models.md Section 3.1
    """

    query: str = Field(description="PromQL query string")
    cluster_ids: list[UUID] = Field(
        default_factory=list, description="Target clusters (empty = all)"
    )
    time: datetime | None = Field(default=None, description="Query time (default: now)")
    timeout: int = Field(default=30, ge=1, le=300, description="Timeout in seconds")


class MetricRangeQueryRequest(BaseModel):
    """Request for range metric query.

    Spec Reference: specs/01-data-models.md Section 3.1
    """

    query: str = Field(description="PromQL query string")
    cluster_ids: list[UUID] = Field(
        default_factory=list, description="Target clusters (empty = all)"
    )
    start_time: datetime = Field(description="Query start time")
    end_time: datetime = Field(description="Query end time")
    step: str = Field(default="1m", description="Query resolution step")
    timeout: int = Field(default=30, ge=1, le=300, description="Timeout in seconds")


class MetricQueryResponse(BaseModel):
    """Response from metric query.

    Spec Reference: specs/03-observability-collector.md Section 4.7
    """

    results: list[dict[str, Any]]
    total_query_time_ms: int
    clusters_queried: int
    clusters_succeeded: int


@router.post(
    "/metrics/query",
    response_model=MetricQueryResponse,
    summary="Execute instant PromQL query",
    description="Execute instant PromQL query across specified or all clusters.",
)
async def query_metrics(request: Request, query_request: MetricQueryRequest):
    """Execute instant PromQL query.

    Spec Reference: specs/03-observability-collector.md Section 4.1
    """
    cluster_registry = request.app.state.cluster_registry
    redis = request.app.state.redis

    service = MetricsService(cluster_registry, redis)

    try:
        results = await service.query(
            query=query_request.query,
            cluster_ids=query_request.cluster_ids,
            time=query_request.time,
            timeout=query_request.timeout,
        )
        return results
    except Exception as e:
        logger.error("Metric query failed", error=str(e), query=query_request.query)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post(
    "/metrics/query_range",
    response_model=MetricQueryResponse,
    summary="Execute range PromQL query",
    description="Execute range PromQL query across specified or all clusters.",
)
async def query_range_metrics(request: Request, query_request: MetricRangeQueryRequest):
    """Execute range PromQL query.

    Spec Reference: specs/03-observability-collector.md Section 4.1
    """
    cluster_registry = request.app.state.cluster_registry
    redis = request.app.state.redis

    service = MetricsService(cluster_registry, redis)

    try:
        results = await service.query_range(
            query=query_request.query,
            cluster_ids=query_request.cluster_ids,
            start_time=query_request.start_time,
            end_time=query_request.end_time,
            step=query_request.step,
            timeout=query_request.timeout,
        )
        return results
    except Exception as e:
        logger.error("Range query failed", error=str(e), query=query_request.query)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get(
    "/metrics/labels",
    summary="Get label names",
    description="Get all label names from specified or all clusters.",
)
async def get_labels(
    request: Request,
    cluster_id: UUID | None = None,
):
    """Get available label names.

    Spec Reference: specs/03-observability-collector.md Section 4.1
    """
    cluster_registry = request.app.state.cluster_registry
    redis = request.app.state.redis

    service = MetricsService(cluster_registry, redis)

    cluster_ids = [cluster_id] if cluster_id else []

    try:
        labels = await service.get_labels(cluster_ids=cluster_ids)
        return {"labels": labels}
    except Exception as e:
        logger.error("Get labels failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e
