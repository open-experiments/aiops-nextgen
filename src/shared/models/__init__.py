"""Shared data models for AIOps NextGen.

Spec Reference: specs/01-data-models.md

All models follow these conventions:
- Timestamps: ISO 8601 format with timezone (UTC preferred)
- IDs: UUID v4
- Field names: lowercase snake_case
- Enums: uppercase SNAKE_CASE
"""

# Base
from .base import AIOpsBaseModel

# Cluster domain (Section 2)
from .cluster import (
    AuthType,
    Cluster,
    ClusterCapabilities,
    ClusterCreate,
    ClusterCredentials,
    ClusterEndpoints,
    ClusterState,
    ClusterStatus,
    ClusterType,
    ClusterUpdate,
    CNFType,
    Connectivity,
    Environment,
    Platform,
)

# Common types (Section 8)
from .common import (
    ErrorResponse,
    PaginatedResponse,
    PaginationParams,
    TimeRange,
)

# Event models (Section 6)
from .events import (
    Event,
    EventType,
    Subscription,
    SubscriptionRequest,
)

# GPU domain (Section 4)
from .gpu import (
    GPU,
    GPUNode,
    GPUProcess,
    GPUProcessType,
)

# Intelligence domain (Section 5)
from .intelligence import (
    AnomalyDetection,
    AnomalySeverity,
    AnomalyType,
    ChatMessage,
    ChatMessageCreate,
    ChatSession,
    ChatSessionCreate,
    DetectionType,
    MessageRole,
    Persona,
    ToolCall,
    ToolResult,
    ToolResultStatus,
)

# Observability domain (Section 3)
from .observability import (
    Alert,
    AlertSeverity,
    AlertState,
    LogDirection,
    LogEntry,
    LogQuery,
    MetricQuery,
    MetricResult,
    MetricResultStatus,
    MetricResultType,
    MetricSeries,
    Span,
    SpanLog,
    SpanStatus,
    Trace,
    TraceQuery,
)

# Report models (Section 7)
from .reports import (
    Report,
    ReportFormat,
    ReportRequest,
    ReportType,
)

__all__ = [
    # Base
    "AIOpsBaseModel",
    # Common
    "ErrorResponse",
    "PaginatedResponse",
    "PaginationParams",
    "TimeRange",
    # Cluster
    "AuthType",
    "Cluster",
    "ClusterCapabilities",
    "ClusterCreate",
    "ClusterCredentials",
    "ClusterEndpoints",
    "ClusterState",
    "ClusterStatus",
    "ClusterType",
    "ClusterUpdate",
    "CNFType",
    "Connectivity",
    "Environment",
    "Platform",
    # Observability
    "Alert",
    "AlertSeverity",
    "AlertState",
    "LogDirection",
    "LogEntry",
    "LogQuery",
    "MetricQuery",
    "MetricResult",
    "MetricResultStatus",
    "MetricResultType",
    "MetricSeries",
    "Span",
    "SpanLog",
    "SpanStatus",
    "Trace",
    "TraceQuery",
    # GPU
    "GPU",
    "GPUNode",
    "GPUProcess",
    "GPUProcessType",
    # Intelligence
    "AnomalyDetection",
    "AnomalySeverity",
    "AnomalyType",
    "ChatMessage",
    "ChatMessageCreate",
    "ChatSession",
    "ChatSessionCreate",
    "DetectionType",
    "MessageRole",
    "Persona",
    "ToolCall",
    "ToolResult",
    "ToolResultStatus",
    # Events
    "Event",
    "EventType",
    "Subscription",
    "SubscriptionRequest",
    # Reports
    "Report",
    "ReportFormat",
    "ReportRequest",
    "ReportType",
]
