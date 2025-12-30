"""Intelligence domain models.

Spec Reference: specs/01-data-models.md Section 5 - Intelligence Domain Models
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import Field

from .base import AIOpsBaseModel


# Enums
class MessageRole(str, Enum):
    """Chat message role. Spec: Section 5.2"""

    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"
    TOOL = "TOOL"


class ToolResultStatus(str, Enum):
    """Tool execution status. Spec: Section 5.4"""

    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"


class DetectionType(str, Enum):
    """Anomaly detection method. Spec: Section 5.6"""

    STATISTICAL = "STATISTICAL"
    ML_BASED = "ML_BASED"
    LLM_ASSISTED = "LLM_ASSISTED"


class AnomalySeverity(str, Enum):
    """Anomaly severity levels.

    Spec: Section 5.6
    Note: Different from Alert severity (CRITICAL/WARNING/INFO).
    Frontend should map between these when correlating.
    """

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class AnomalyType(str, Enum):
    """Type of anomaly detected. Spec: Section 5.6"""

    SPIKE = "SPIKE"
    DROP = "DROP"
    TREND_CHANGE = "TREND_CHANGE"
    PATTERN_BREAK = "PATTERN_BREAK"
    THRESHOLD_BREACH = "THRESHOLD_BREACH"


# Models
class Persona(AIOpsBaseModel):
    """An AI persona with specialized capabilities.

    Spec Reference: Section 5.1
    """

    id: str = Field(
        pattern=r"^[a-z][a-z0-9-]{2,30}[a-z0-9]$",
        description="Unique persona identifier",
    )
    name: str
    description: str
    system_prompt: str = Field(description="System prompt defining persona behavior")
    capabilities: list[str] = Field(
        default_factory=list, description="MCP tools this persona can use"
    )
    icon: str | None = Field(default=None, description="Icon identifier for UI")
    is_builtin: bool = Field(default=False, description="Whether this is a system-provided persona")
    created_by: str | None = Field(default=None, description="User who created custom persona")


class ToolCall(AIOpsBaseModel):
    """A tool invocation by the AI.

    Spec Reference: Section 5.3
    """

    id: str
    name: str = Field(description="MCP tool name")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Tool arguments as JSON")


class ToolResult(AIOpsBaseModel):
    """Result from a tool execution.

    Spec Reference: Section 5.4
    """

    tool_call_id: str
    status: ToolResultStatus
    result: dict[str, Any] | None = Field(default=None, description="Tool result as JSON")
    error: str | None = None


class ChatMessage(AIOpsBaseModel):
    """A message in a chat session.

    Spec Reference: Section 5.2
    """

    id: UUID
    session_id: UUID
    role: MessageRole
    content: str
    persona_id: str | None = Field(default=None, description="Active persona when message was sent")
    tool_calls: list[ToolCall] = Field(
        default_factory=list, description="Tools invoked by assistant"
    )
    tool_results: list[ToolResult] = Field(
        default_factory=list, description="Results from tool calls"
    )
    model: str | None = Field(default=None, description="LLM model used")
    tokens_used: int | None = None
    latency_ms: int | None = None
    created_at: datetime


class ChatSession(AIOpsBaseModel):
    """A chat conversation session.

    Spec Reference: Section 5.5
    """

    id: UUID
    user_id: str = Field(description="User who owns the session")
    title: str | None = Field(default=None, description="Auto-generated or user-set title")
    persona_id: str = Field(default="default")
    cluster_context: list[UUID] = Field(
        default_factory=list, description="Clusters in scope for this session"
    )
    message_count: int = Field(default=0)
    created_at: datetime
    updated_at: datetime | None = None
    expires_at: datetime | None = Field(
        default=None, description="Session expiration (default: 24h from last activity)"
    )


class AnomalyDetection(AIOpsBaseModel):
    """A detected anomaly in metrics.

    Spec Reference: Section 5.6
    """

    id: UUID
    cluster_id: UUID
    metric_name: str
    labels: dict[str, str] = Field(default_factory=dict)
    detection_type: DetectionType
    severity: AnomalySeverity
    confidence_score: float = Field(ge=0, le=1)
    anomaly_type: AnomalyType
    expected_value: float
    actual_value: float
    deviation_percent: float
    explanation: str = Field(description="Human-readable explanation")
    detected_at: datetime
    related_alerts: list[UUID] = Field(default_factory=list)


# Request/Response models
class ChatSessionCreate(AIOpsBaseModel):
    """Request model for creating a chat session."""

    persona_id: str = Field(default="default")
    cluster_context: list[UUID] = Field(default_factory=list)
    title: str | None = None


class ChatMessageCreate(AIOpsBaseModel):
    """Request model for sending a chat message."""

    content: str
