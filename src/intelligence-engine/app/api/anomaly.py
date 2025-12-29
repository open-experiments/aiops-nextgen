"""Anomaly Detection API endpoints.

Spec Reference: specs/04-intelligence-engine.md Section 7.3
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel

from shared.models import AnomalyDetection
from shared.observability import get_logger

from ..services.anomaly_detection import (
    DetectionMethod,
    MetricData,
    anomaly_detector,
)
from ..services.rca import RootCause, rca_analyzer

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/anomaly", tags=["anomaly"])


class DetectRequest(BaseModel):
    """Request for anomaly detection."""

    cluster_id: str
    metric_name: str
    values: list[dict]  # [{"timestamp": float, "value": float}, ...]
    labels: dict[str, str] = {}
    methods: list[str] | None = None


class DetectResponse(BaseModel):
    """Response from anomaly detection."""

    anomalies: list[AnomalyDetection]
    total_count: int
    detection_time_ms: int


class RCARequest(BaseModel):
    """Request for root cause analysis."""

    cluster_id: str
    anomalies: list[AnomalyDetection]


class RCAResponse(BaseModel):
    """Response from root cause analysis."""

    root_causes: list[RootCause]
    analysis_time_ms: int


@router.post("/detect", response_model=DetectResponse)
async def detect_anomalies(request: DetectRequest) -> DetectResponse:
    """Detect anomalies in metric data.

    Args:
        request: Detection request with metric data

    Returns:
        Detected anomalies
    """
    start_time = datetime.now(UTC)

    # Parse detection methods
    methods = None
    if request.methods:
        methods = [DetectionMethod(m) for m in request.methods]

    # Create metric data
    metric_data = MetricData(
        metric_name=request.metric_name,
        cluster_id=request.cluster_id,
        labels=request.labels,
        values=request.values,
    )

    # Detect anomalies
    anomalies = anomaly_detector.detect(metric_data, methods)

    elapsed_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)

    logger.info(
        "Anomaly detection completed",
        cluster_id=request.cluster_id,
        metric=request.metric_name,
        anomalies_found=len(anomalies),
        elapsed_ms=elapsed_ms,
    )

    return DetectResponse(
        anomalies=anomalies,
        total_count=len(anomalies),
        detection_time_ms=elapsed_ms,
    )


@router.post("/rca", response_model=RCAResponse)
async def analyze_root_cause(request: RCARequest) -> RCAResponse:
    """Perform root cause analysis on anomalies.

    Args:
        request: RCA request with anomalies

    Returns:
        Identified root causes
    """
    start_time = datetime.now(UTC)

    # Analyze root causes
    root_causes = await rca_analyzer.analyze(request.anomalies)

    elapsed_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)

    logger.info(
        "Root cause analysis completed",
        cluster_id=request.cluster_id,
        anomalies_analyzed=len(request.anomalies),
        root_causes_found=len(root_causes),
        elapsed_ms=elapsed_ms,
    )

    return RCAResponse(
        root_causes=root_causes,
        analysis_time_ms=elapsed_ms,
    )


@router.get("/history")
async def get_anomaly_history(
    cluster_id: str,
    hours: int = Query(default=24, ge=1, le=168),
    severity: str | None = None,
) -> list[AnomalyDetection]:
    """Get historical anomalies for a cluster.

    Args:
        cluster_id: Target cluster ID
        hours: Hours of history (max 168 = 1 week)
        severity: Optional severity filter (HIGH, MEDIUM, LOW)

    Returns:
        List of historical anomalies
    """
    # In production, this would query from a database
    # For now, return empty list as we don't have persistent storage
    logger.info(
        "Fetching anomaly history",
        cluster_id=cluster_id,
        hours=hours,
        severity=severity,
    )

    return []


@router.get("/methods")
async def list_detection_methods() -> dict:
    """List available anomaly detection methods.

    Returns:
        Available detection methods and their descriptions
    """
    return {
        "methods": [
            {
                "id": "zscore",
                "name": "Z-Score",
                "description": "Statistical method based on standard deviations from mean",
                "type": "statistical",
            },
            {
                "id": "iqr",
                "name": "IQR (Interquartile Range)",
                "description": "Statistical method based on quartile analysis",
                "type": "statistical",
            },
            {
                "id": "isolation_forest",
                "name": "Isolation Forest",
                "description": "ML-based anomaly detection using random forests",
                "type": "ml",
                "requires": "scikit-learn",
            },
            {
                "id": "seasonal",
                "name": "Seasonal Decomposition",
                "description": "Pattern-based detection for time series with seasonality",
                "type": "pattern",
                "requires": "statsmodels",
            },
            {
                "id": "lof",
                "name": "Local Outlier Factor",
                "description": "ML-based detection using local density analysis",
                "type": "ml",
                "requires": "scikit-learn",
            },
        ]
    }
