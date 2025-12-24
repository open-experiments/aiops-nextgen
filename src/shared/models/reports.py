"""Report models.

Spec Reference: specs/01-data-models.md Section 7 - Report Models
"""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import Field

from .base import AIOpsBaseModel
from .common import TimeRange


class ReportType(str, Enum):
    """Type of report. Spec: Section 7.1"""

    EXECUTIVE_SUMMARY = "EXECUTIVE_SUMMARY"
    DETAILED_ANALYSIS = "DETAILED_ANALYSIS"
    INCIDENT_REPORT = "INCIDENT_REPORT"
    CAPACITY_PLAN = "CAPACITY_PLAN"


class ReportFormat(str, Enum):
    """Report output format. Spec: Section 7.1"""

    HTML = "HTML"
    PDF = "PDF"
    MARKDOWN = "MARKDOWN"
    JSON = "JSON"


class Report(AIOpsBaseModel):
    """A generated report.

    Spec Reference: Section 7.1
    """

    id: UUID
    title: str
    report_type: ReportType
    format: ReportFormat
    cluster_scope: list[UUID] = Field(default_factory=list)
    time_range: TimeRange | None = None
    generated_by: str = Field(
        description="User or 'system' for scheduled reports"
    )
    storage_path: str = Field(description="Object storage path")
    size_bytes: int
    created_at: datetime
    expires_at: datetime | None = None


class ReportRequest(AIOpsBaseModel):
    """Request to generate a report."""

    title: str
    report_type: ReportType
    format: ReportFormat = ReportFormat.PDF
    cluster_scope: list[UUID] = Field(default_factory=list)
    time_range: TimeRange | None = None
