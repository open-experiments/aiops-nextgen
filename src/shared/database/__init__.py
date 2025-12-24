"""Database configuration and models.

Spec References:
- specs/08-integration-matrix.md Section 6.1 - Database configuration
- specs/02-cluster-registry.md Section 7 - Cluster schema
- specs/04-intelligence-engine.md - Intelligence schema
"""

from .base import Base, create_engine, create_session_factory
from .models import (
    AnomalyDetectionModel,
    ChatMessageModel,
    ChatSessionModel,
    ClusterHealthHistoryModel,
    ClusterModel,
    ReportModel,
)

__all__ = [
    # Base
    "Base",
    "create_engine",
    "create_session_factory",
    # Cluster schema
    "ClusterModel",
    "ClusterHealthHistoryModel",
    # Intelligence schema
    "ChatSessionModel",
    "ChatMessageModel",
    "AnomalyDetectionModel",
    "ReportModel",
]
