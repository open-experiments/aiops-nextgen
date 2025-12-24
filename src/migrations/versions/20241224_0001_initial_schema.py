"""Initial schema creation.

Revision ID: 0001
Revises:
Create Date: 2024-12-24

Spec References:
- specs/02-cluster-registry.md Section 7 - clusters schema
- specs/04-intelligence-engine.md Section 4.6 - intelligence schema
- specs/08-integration-matrix.md Section 6.1 - Database layout
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create schemas
    op.execute("CREATE SCHEMA IF NOT EXISTS clusters")
    op.execute("CREATE SCHEMA IF NOT EXISTS intelligence")

    # =========================================================================
    # Clusters Schema Tables
    # =========================================================================

    # clusters.clusters table
    op.create_table(
        "clusters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(63), unique=True, nullable=False),
        sa.Column("display_name", sa.String(128), nullable=True),
        sa.Column("api_server_url", sa.String(512), nullable=False),
        sa.Column("cluster_type", sa.String(20), nullable=False, server_default="SPOKE"),
        sa.Column("platform", sa.String(20), nullable=False, server_default="OPENSHIFT"),
        sa.Column("platform_version", sa.String(20), nullable=True),
        sa.Column("region", sa.String(64), nullable=True),
        sa.Column("environment", sa.String(20), server_default="DEVELOPMENT"),
        sa.Column("labels", postgresql.JSONB, server_default="{}"),
        sa.Column("endpoints", postgresql.JSONB, server_default="{}"),
        sa.Column("capabilities", postgresql.JSONB, nullable=True),
        sa.Column(
            "status",
            postgresql.JSONB,
            nullable=False,
            server_default='{"state": "UNKNOWN"}',
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "name ~ '^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$'",
            name="valid_name",
        ),
        sa.CheckConstraint(
            "cluster_type IN ('HUB', 'SPOKE', 'EDGE', 'FAR_EDGE')",
            name="valid_cluster_type",
        ),
        sa.CheckConstraint(
            "platform IN ('OPENSHIFT', 'KUBERNETES', 'MICROSHIFT')",
            name="valid_platform",
        ),
        sa.CheckConstraint(
            "environment IN ('PRODUCTION', 'STAGING', 'DEVELOPMENT', 'LAB')",
            name="valid_environment",
        ),
        schema="clusters",
    )

    # Indexes for clusters.clusters
    op.create_index(
        "idx_clusters_name", "clusters", ["name"], schema="clusters"
    )
    op.create_index(
        "idx_clusters_cluster_type", "clusters", ["cluster_type"], schema="clusters"
    )
    op.create_index(
        "idx_clusters_environment", "clusters", ["environment"], schema="clusters"
    )
    op.create_index(
        "idx_clusters_region", "clusters", ["region"], schema="clusters"
    )

    # clusters.cluster_health_history table
    op.create_table(
        "cluster_health_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "cluster_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("clusters.clusters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", postgresql.JSONB, nullable=False),
        sa.Column(
            "checked_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        schema="clusters",
    )

    # Indexes for clusters.cluster_health_history
    op.create_index(
        "idx_health_history_cluster_time",
        "cluster_health_history",
        ["cluster_id", "checked_at"],
        schema="clusters",
    )

    # =========================================================================
    # Intelligence Schema Tables
    # =========================================================================

    # intelligence.chat_sessions table
    op.create_table(
        "chat_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("persona_id", sa.String(63), server_default="default"),
        sa.Column("cluster_context", postgresql.JSONB, server_default="[]"),
        sa.Column("message_count", sa.Integer, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        schema="intelligence",
    )

    # Indexes for intelligence.chat_sessions
    op.create_index(
        "idx_chat_sessions_user_id",
        "chat_sessions",
        ["user_id"],
        schema="intelligence",
    )
    op.create_index(
        "idx_chat_sessions_created_at",
        "chat_sessions",
        ["created_at"],
        schema="intelligence",
    )

    # intelligence.chat_messages table
    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence.chat_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("persona_id", sa.String(63), nullable=True),
        sa.Column("tool_calls", postgresql.JSONB, server_default="[]"),
        sa.Column("tool_results", postgresql.JSONB, server_default="[]"),
        sa.Column("model", sa.String(128), nullable=True),
        sa.Column("tokens_used", sa.Integer, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        schema="intelligence",
    )

    # Indexes for intelligence.chat_messages
    op.create_index(
        "idx_chat_messages_session_id",
        "chat_messages",
        ["session_id"],
        schema="intelligence",
    )
    op.create_index(
        "idx_chat_messages_created_at",
        "chat_messages",
        ["created_at"],
        schema="intelligence",
    )

    # intelligence.anomaly_detections table
    op.create_table(
        "anomaly_detections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("cluster_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("metric_name", sa.String(255), nullable=False),
        sa.Column("labels", postgresql.JSONB, server_default="{}"),
        sa.Column("detection_type", sa.String(20), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("confidence_score", sa.Float, nullable=False),
        sa.Column("anomaly_type", sa.String(20), nullable=False),
        sa.Column("expected_value", sa.Float, nullable=False),
        sa.Column("actual_value", sa.Float, nullable=False),
        sa.Column("deviation_percent", sa.Float, nullable=False),
        sa.Column("explanation", sa.Text, nullable=False),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("related_alerts", postgresql.JSONB, server_default="[]"),
        schema="intelligence",
    )

    # Indexes for intelligence.anomaly_detections
    op.create_index(
        "idx_anomaly_cluster_id",
        "anomaly_detections",
        ["cluster_id"],
        schema="intelligence",
    )
    op.create_index(
        "idx_anomaly_detected_at",
        "anomaly_detections",
        ["detected_at"],
        schema="intelligence",
    )

    # intelligence.reports table
    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("report_type", sa.String(30), nullable=False),
        sa.Column("format", sa.String(20), nullable=False),
        sa.Column("cluster_scope", postgresql.JSONB, server_default="[]"),
        sa.Column("time_range", postgresql.JSONB, nullable=True),
        sa.Column("generated_by", sa.String(255), nullable=False),
        sa.Column("storage_path", sa.String(512), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        schema="intelligence",
    )

    # Indexes for intelligence.reports
    op.create_index(
        "idx_reports_generated_by",
        "reports",
        ["generated_by"],
        schema="intelligence",
    )
    op.create_index(
        "idx_reports_created_at",
        "reports",
        ["created_at"],
        schema="intelligence",
    )


def downgrade() -> None:
    # Drop intelligence schema tables
    op.drop_table("reports", schema="intelligence")
    op.drop_table("anomaly_detections", schema="intelligence")
    op.drop_table("chat_messages", schema="intelligence")
    op.drop_table("chat_sessions", schema="intelligence")

    # Drop clusters schema tables
    op.drop_table("cluster_health_history", schema="clusters")
    op.drop_table("clusters", schema="clusters")

    # Drop schemas
    op.execute("DROP SCHEMA IF EXISTS intelligence")
    op.execute("DROP SCHEMA IF EXISTS clusters")
