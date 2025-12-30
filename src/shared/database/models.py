"""SQLAlchemy ORM models.

Spec References:
- specs/02-cluster-registry.md Section 7 - Cluster tables
- specs/04-intelligence-engine.md Section 4.6 - Chat tables
"""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base

# =============================================================================
# Cluster Registry Models (spec 02-cluster-registry.md Section 7)
# =============================================================================


class ClusterModel(Base):
    """Cluster database model.

    Spec Reference: specs/02-cluster-registry.md Section 7.1
    """

    __tablename__ = "clusters"
    __table_args__ = (
        CheckConstraint(
            "name ~ '^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$'",
            name="valid_name",
        ),
        CheckConstraint(
            "cluster_type IN ('HUB', 'SPOKE', 'EDGE', 'FAR_EDGE')",
            name="valid_cluster_type",
        ),
        CheckConstraint(
            "platform IN ('OPENSHIFT', 'KUBERNETES', 'MICROSHIFT')",
            name="valid_platform",
        ),
        CheckConstraint(
            "environment IN ('PRODUCTION', 'STAGING', 'DEVELOPMENT', 'LAB')",
            name="valid_environment",
        ),
        Index("idx_clusters_name", "name"),
        Index("idx_clusters_cluster_type", "cluster_type"),
        Index("idx_clusters_environment", "environment"),
        Index("idx_clusters_region", "region"),
        {"schema": "clusters"},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(63), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(128))
    api_server_url: Mapped[str] = mapped_column(String(512), nullable=False)
    cluster_type: Mapped[str] = mapped_column(String(20), nullable=False, default="SPOKE")
    platform: Mapped[str] = mapped_column(String(20), nullable=False, default="OPENSHIFT")
    platform_version: Mapped[str | None] = mapped_column(String(20))
    region: Mapped[str | None] = mapped_column(String(64))
    environment: Mapped[str] = mapped_column(String(20), default="DEVELOPMENT")
    labels: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    endpoints: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    capabilities: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default={"state": "UNKNOWN"}
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    health_history: Mapped[list["ClusterHealthHistoryModel"]] = relationship(
        back_populates="cluster", cascade="all, delete-orphan"
    )


class ClusterHealthHistoryModel(Base):
    """Cluster health check history.

    Spec Reference: specs/02-cluster-registry.md Section 7.1
    """

    __tablename__ = "cluster_health_history"
    __table_args__ = (
        Index("idx_health_history_cluster_time", "cluster_id", "checked_at"),
        {"schema": "clusters"},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    cluster_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("clusters.clusters.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    cluster: Mapped["ClusterModel"] = relationship(back_populates="health_history")


# =============================================================================
# Intelligence Engine Models (spec 04-intelligence-engine.md)
# =============================================================================


class ChatSessionModel(Base):
    """Chat session database model.

    Spec Reference: specs/01-data-models.md Section 5.5
    """

    __tablename__ = "chat_sessions"
    __table_args__ = (
        Index("idx_chat_sessions_user_id", "user_id"),
        Index("idx_chat_sessions_created_at", "created_at"),
        {"schema": "intelligence"},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    persona_id: Mapped[str] = mapped_column(String(63), default="default")
    cluster_context: Mapped[list[str]] = mapped_column(JSONB, default=list)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    messages: Mapped[list["ChatMessageModel"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class ChatMessageModel(Base):
    """Chat message database model.

    Spec Reference: specs/01-data-models.md Section 5.2
    """

    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("idx_chat_messages_session_id", "session_id"),
        Index("idx_chat_messages_created_at", "created_at"),
        {"schema": "intelligence"},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("intelligence.chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    persona_id: Mapped[str | None] = mapped_column(String(63))
    tool_calls: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    tool_results: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    model: Mapped[str | None] = mapped_column(String(128))
    tokens_used: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session: Mapped["ChatSessionModel"] = relationship(back_populates="messages")


class AnomalyDetectionModel(Base):
    """Anomaly detection database model.

    Spec Reference: specs/01-data-models.md Section 5.6
    """

    __tablename__ = "anomaly_detections"
    __table_args__ = (
        Index("idx_anomaly_cluster_id", "cluster_id"),
        Index("idx_anomaly_detected_at", "detected_at"),
        {"schema": "intelligence"},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    cluster_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(255), nullable=False)
    labels: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    detection_type: Mapped[str] = mapped_column(String(20), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)
    confidence_score: Mapped[float] = mapped_column(nullable=False)
    anomaly_type: Mapped[str] = mapped_column(String(20), nullable=False)
    expected_value: Mapped[float] = mapped_column(nullable=False)
    actual_value: Mapped[float] = mapped_column(nullable=False)
    deviation_percent: Mapped[float] = mapped_column(nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    related_alerts: Mapped[list[str]] = mapped_column(JSONB, default=list)


class ReportModel(Base):
    """Report database model.

    Spec Reference: specs/01-data-models.md Section 7.1
    """

    __tablename__ = "reports"
    __table_args__ = (
        Index("idx_reports_generated_by", "generated_by"),
        Index("idx_reports_created_at", "created_at"),
        {"schema": "intelligence"},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    report_type: Mapped[str] = mapped_column(String(30), nullable=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    cluster_scope: Mapped[list[str]] = mapped_column(JSONB, default=list)
    time_range: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    generated_by: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
