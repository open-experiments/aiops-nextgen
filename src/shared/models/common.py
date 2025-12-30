"""Common types used across all models.

Spec Reference: specs/01-data-models.md Section 8 - Common Types
"""

import re
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import Field, field_validator

from .base import AIOpsBaseModel

T = TypeVar("T")


class PaginationParams(AIOpsBaseModel):
    """Pagination parameters for list endpoints.

    Spec Reference: Section 8.1
    """

    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page (max 100)")


class PaginatedResponse(AIOpsBaseModel, Generic[T]):
    """Paginated response wrapper.

    Spec Reference: Section 8.1
    """

    items: list[T]
    total: int = Field(description="Total number of items")
    page: int
    page_size: int
    total_pages: int


class TimeRange(AIOpsBaseModel):
    """Time range specification.

    Spec Reference: Section 8.2
    """

    start: datetime | None = None
    end: datetime | None = None
    duration: str | None = Field(
        default=None,
        pattern=r"^[0-9]+[smhdw]$",
        description="Relative duration (e.g., '1h', '30m', '7d')",
    )

    @field_validator("duration")
    @classmethod
    def validate_duration(cls, v: str | None) -> str | None:
        if v is not None and not re.match(r"^[0-9]+[smhdw]$", v):
            raise ValueError("Duration must match pattern: ^[0-9]+[smhdw]$")
        return v


class ErrorResponse(AIOpsBaseModel):
    """Standard error response format.

    Spec Reference: Section 8.3
    """

    error_code: str = Field(description="Machine-readable error code")
    message: str = Field(description="Human-readable error message")
    details: dict[str, Any] | None = Field(default=None, description="Additional error context")
    trace_id: str | None = Field(default=None, description="Request trace ID for debugging")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
