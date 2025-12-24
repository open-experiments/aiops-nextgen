"""Event models for real-time streaming.

Spec Reference: specs/01-data-models.md Section 6 - Event Models
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import Field

from .base import AIOpsBaseModel


class EventType(str, Enum):
    """Event types for streaming.

    Spec Reference: Section 6.1
    """

    # Cluster Registry Events
    CLUSTER_REGISTERED = "CLUSTER_REGISTERED"
    CLUSTER_UPDATED = "CLUSTER_UPDATED"
    CLUSTER_DELETED = "CLUSTER_DELETED"
    CLUSTER_STATUS_CHANGED = "CLUSTER_STATUS_CHANGED"
    CLUSTER_CREDENTIALS_UPDATED = "CLUSTER_CREDENTIALS_UPDATED"
    CLUSTER_CAPABILITIES_CHANGED = "CLUSTER_CAPABILITIES_CHANGED"

    # Observability Collector Events
    METRIC_UPDATE = "METRIC_UPDATE"
    ALERT_FIRED = "ALERT_FIRED"
    ALERT_RESOLVED = "ALERT_RESOLVED"
    TRACE_RECEIVED = "TRACE_RECEIVED"
    GPU_UPDATE = "GPU_UPDATE"

    # Intelligence Engine Events
    ANOMALY_DETECTED = "ANOMALY_DETECTED"
    CHAT_MESSAGE = "CHAT_MESSAGE"
    RCA_COMPLETE = "RCA_COMPLETE"
    REPORT_GENERATED = "REPORT_GENERATED"


class Event(AIOpsBaseModel):
    """Base event model for real-time streaming.

    Spec Reference: Section 6.1
    Note: Events are ephemeral (not persisted, streamed only)
    """

    event_id: UUID
    event_type: EventType
    cluster_id: UUID | None = None
    timestamp: datetime
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Event-specific payload"
    )


class Subscription(AIOpsBaseModel):
    """WebSocket subscription for real-time events.

    Spec Reference: Section 6.2
    Note: Session-scoped (WebSocket connection lifetime)
    """

    id: UUID
    client_id: str = Field(description="WebSocket client identifier")
    event_types: list[EventType] = Field(
        default_factory=list, description="Event types to receive"
    )
    cluster_filter: list[UUID] = Field(
        default_factory=list, description="Filter by cluster IDs (empty = all)"
    )
    namespace_filter: list[str] = Field(
        default_factory=list, description="Filter by namespaces"
    )
    created_at: datetime


class SubscriptionRequest(AIOpsBaseModel):
    """Request to create/update a subscription."""

    event_types: list[EventType] = Field(default_factory=list)
    cluster_filter: list[UUID] = Field(default_factory=list)
    namespace_filter: list[str] = Field(default_factory=list)
