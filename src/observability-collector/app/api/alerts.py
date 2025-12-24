"""Alerts API endpoints.

Spec Reference: specs/03-observability-collector.md Section 4.4
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from shared.models.observability import AlertSeverity, AlertState
from shared.observability import get_logger

from ..services.alerts_service import AlertsService

logger = get_logger(__name__)

router = APIRouter()


class AlertResponse(BaseModel):
    """Alert response model.

    Spec Reference: specs/01-data-models.md Section 3.9
    """

    id: UUID
    fingerprint: str
    cluster_id: UUID
    cluster_name: str
    alertname: str
    severity: AlertSeverity
    state: AlertState
    labels: dict[str, str]
    annotations: dict[str, str]
    starts_at: datetime
    ends_at: datetime | None = None
    generator_url: str | None = None


class AlertListResponse(BaseModel):
    """Response for list alerts.

    Spec Reference: specs/03-observability-collector.md Section 4.7
    """

    alerts: list[AlertResponse]
    total: int
    by_severity: dict[str, int]


class AlertmanagerAlert(BaseModel):
    """Single alert from Alertmanager webhook."""

    status: str
    labels: dict[str, str]
    annotations: dict[str, str]
    startsAt: str
    endsAt: str | None = None
    generatorURL: str | None = None
    fingerprint: str


class AlertmanagerWebhookPayload(BaseModel):
    """Alertmanager webhook payload.

    Spec Reference: specs/03-observability-collector.md Section 6.3
    """

    version: str
    groupKey: str
    status: str
    receiver: str
    groupLabels: dict[str, str]
    commonLabels: dict[str, str]
    commonAnnotations: dict[str, str]
    externalURL: str
    alerts: list[AlertmanagerAlert]


@router.get(
    "/alerts",
    response_model=AlertListResponse,
    summary="List active alerts",
    description="List active alerts from specified or all clusters.",
)
async def list_alerts(
    request: Request,
    cluster_id: UUID | None = None,
    state: AlertState | None = None,
    severity: AlertSeverity | None = None,
):
    """List active alerts.

    Spec Reference: specs/03-observability-collector.md Section 4.4
    """
    redis = request.app.state.redis

    service = AlertsService(redis)

    cluster_ids = [cluster_id] if cluster_id else []

    try:
        alerts = await service.list_alerts(
            cluster_ids=cluster_ids,
            state=state,
            severity=severity,
        )
        return alerts
    except Exception as e:
        logger.error("List alerts failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/alerts/{fingerprint}",
    response_model=AlertResponse,
    summary="Get alert by fingerprint",
    description="Get specific alert by its fingerprint.",
)
async def get_alert(request: Request, fingerprint: str):
    """Get alert by fingerprint.

    Spec Reference: specs/03-observability-collector.md Section 4.4
    """
    redis = request.app.state.redis

    service = AlertsService(redis)

    try:
        alert = await service.get_alert(fingerprint)
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        return alert
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get alert failed", error=str(e), fingerprint=fingerprint)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/alerts/webhook/{cluster_id}",
    summary="Alertmanager webhook receiver",
    description="Receive alerts from Alertmanager webhook.",
)
async def receive_webhook(
    request: Request,
    cluster_id: UUID,
    payload: AlertmanagerWebhookPayload,
):
    """Receive Alertmanager webhook.

    Spec Reference: specs/03-observability-collector.md Section 6.3
    """
    redis = request.app.state.redis

    service = AlertsService(redis)

    try:
        await service.receive_webhook(cluster_id, payload)
        return {"status": "received", "alerts_count": len(payload.alerts)}
    except Exception as e:
        logger.error(
            "Webhook processing failed",
            error=str(e),
            cluster_id=str(cluster_id),
        )
        raise HTTPException(status_code=500, detail=str(e))
