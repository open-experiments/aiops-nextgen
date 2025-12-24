"""Observability domain models.

Spec Reference: specs/01-data-models.md Section 3 - Observability Domain Models
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import Field

from .base import AIOpsBaseModel


# Enums
class MetricResultStatus(str, Enum):
    """Status of a metric query result. Spec: Section 3.2"""

    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"
    PARTIAL = "PARTIAL"


class MetricResultType(str, Enum):
    """Type of metric result. Spec: Section 3.2"""

    MATRIX = "MATRIX"
    VECTOR = "VECTOR"
    SCALAR = "SCALAR"
    STRING = "STRING"


class SpanStatus(str, Enum):
    """Span status. Spec: Section 3.6"""

    OK = "OK"
    ERROR = "ERROR"
    UNSET = "UNSET"


class LogDirection(str, Enum):
    """Log query direction. Spec: Section 3.7"""

    FORWARD = "FORWARD"
    BACKWARD = "BACKWARD"


class AlertSeverity(str, Enum):
    """Alert severity levels. Spec: Section 3.9"""

    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


class AlertState(str, Enum):
    """Alert state. Spec: Section 3.9"""

    FIRING = "FIRING"
    RESOLVED = "RESOLVED"
    PENDING = "PENDING"


# Metric Models
class MetricQuery(AIOpsBaseModel):
    """PromQL query request.

    Spec Reference: Section 3.1
    """

    query: str = Field(description="PromQL query string")
    cluster_ids: list[UUID] = Field(
        default_factory=list, description="Target clusters (empty = all)"
    )
    start_time: datetime | None = Field(
        default=None, description="Query start time (default: now - 1h)"
    )
    end_time: datetime | None = Field(
        default=None, description="Query end time (default: now)"
    )
    step: str = Field(default="1m", description="Query resolution step")
    timeout: int = Field(
        default=30, ge=1, le=300, description="Query timeout in seconds"
    )


class MetricSeries(AIOpsBaseModel):
    """A single metric time series.

    Spec Reference: Section 3.3
    """

    metric: dict[str, str] = Field(description="Label set")
    values: list[tuple[float, str]] = Field(
        default_factory=list, description="[timestamp, value] pairs"
    )


class MetricResult(AIOpsBaseModel):
    """Result from a metric query for a single cluster.

    Spec Reference: Section 3.2
    """

    cluster_id: UUID
    cluster_name: str
    status: MetricResultStatus
    result_type: MetricResultType | None = None
    data: list[MetricSeries] = Field(default_factory=list)
    error: str | None = Field(default=None, description="Error if status != SUCCESS")
    query_time_ms: int | None = Field(
        default=None, description="Query execution time in ms"
    )


# Trace Models
class SpanLog(AIOpsBaseModel):
    """Log entry within a span.

    Spec Reference: Section 3.6
    """

    timestamp: datetime
    message: str


class Span(AIOpsBaseModel):
    """A single span within a trace.

    Spec Reference: Section 3.6
    """

    span_id: str
    parent_span_id: str | None = None
    operation_name: str
    service_name: str
    start_time: datetime
    duration_ms: int
    status: SpanStatus = SpanStatus.UNSET
    tags: dict[str, str] = Field(default_factory=dict)
    logs: list[SpanLog] = Field(default_factory=list)


class TraceQuery(AIOpsBaseModel):
    """Query parameters for trace search.

    Spec Reference: Section 3.4
    """

    cluster_ids: list[UUID] = Field(default_factory=list)
    service_name: str | None = Field(
        default=None, description="Filter by service (supports wildcards)"
    )
    operation_name: str | None = None
    trace_id: str | None = Field(default=None, description="Specific trace ID")
    min_duration_ms: int | None = None
    max_duration_ms: int | None = None
    tags: dict[str, str] = Field(default_factory=dict, description="Tag filters")
    start_time: datetime | None = None
    end_time: datetime | None = None
    limit: int = Field(default=20, ge=1, le=100)


class Trace(AIOpsBaseModel):
    """A distributed trace.

    Spec Reference: Section 3.5
    """

    trace_id: str
    cluster_id: UUID
    cluster_name: str
    root_service: str = Field(description="Service that initiated the trace")
    root_operation: str
    start_time: datetime
    duration_ms: int
    span_count: int
    service_count: int
    has_errors: bool = False
    spans: list[Span] = Field(default_factory=list)


# Log Models
class LogQuery(AIOpsBaseModel):
    """Query parameters for log search.

    Spec Reference: Section 3.7
    """

    cluster_ids: list[UUID] = Field(default_factory=list)
    query: str = Field(description="LogQL query string")
    start_time: datetime | None = None
    end_time: datetime | None = None
    limit: int = Field(default=100, ge=1, le=5000)
    direction: LogDirection = LogDirection.BACKWARD


class LogEntry(AIOpsBaseModel):
    """A single log entry.

    Spec Reference: Section 3.8
    """

    cluster_id: UUID
    cluster_name: str
    timestamp: datetime
    stream: dict[str, str] = Field(description="Log stream labels")
    message: str = Field(description="Log line content")


# Alert Models
class Alert(AIOpsBaseModel):
    """An alert from Alertmanager.

    Spec Reference: Section 3.9
    """

    id: UUID
    fingerprint: str = Field(description="Unique alert fingerprint from Alertmanager")
    cluster_id: UUID
    cluster_name: str
    alertname: str
    severity: AlertSeverity
    state: AlertState
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    starts_at: datetime
    ends_at: datetime | None = None
    generator_url: str | None = Field(
        default=None, description="Link to Prometheus/source"
    )
