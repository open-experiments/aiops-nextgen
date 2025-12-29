"""Reports API endpoints.

Spec Reference: specs/04-intelligence-engine.md Section 6
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query
from pydantic import BaseModel

from shared.models import Report, ReportFormat, ReportType
from shared.observability import get_logger

from ..services.reports import report_generator

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


class GenerateReportRequest(BaseModel):
    """Request to generate a report."""

    report_type: str  # executive_summary, detailed_analysis, incident_report, capacity_plan
    cluster_ids: list[str]
    format: str = "markdown"  # json, markdown, html, pdf
    hours: int = 24


class GenerateReportResponse(BaseModel):
    """Response with generated report."""

    report: Report
    content: str


@router.post("/generate", response_model=GenerateReportResponse)
async def generate_report(request: GenerateReportRequest) -> GenerateReportResponse:
    """Generate a report.

    Args:
        request: Report generation request

    Returns:
        Generated report with content
    """
    # Map string to enum
    type_mapping = {
        "executive_summary": ReportType.EXECUTIVE_SUMMARY,
        "detailed_analysis": ReportType.DETAILED_ANALYSIS,
        "incident_report": ReportType.INCIDENT_REPORT,
        "capacity_plan": ReportType.CAPACITY_PLAN,
    }

    format_mapping = {
        "json": ReportFormat.JSON,
        "markdown": ReportFormat.MARKDOWN,
        "html": ReportFormat.HTML,
        "pdf": ReportFormat.PDF,
    }

    report_type = type_mapping.get(request.report_type, ReportType.EXECUTIVE_SUMMARY)
    report_format = format_mapping.get(request.format.lower(), ReportFormat.MARKDOWN)

    now = datetime.now(UTC)
    start = now - timedelta(hours=request.hours)

    report = await report_generator.generate(
        report_type=report_type,
        cluster_ids=request.cluster_ids,
        start=start,
        end=now,
        report_format=report_format,
    )

    # Generate content again for response
    if report_type == ReportType.EXECUTIVE_SUMMARY:
        data = await report_generator._generate_executive_summary(
            request.cluster_ids, start, now
        )
    elif report_type == ReportType.DETAILED_ANALYSIS:
        data = await report_generator._generate_detailed_analysis(
            request.cluster_ids, start, now
        )
    elif report_type == ReportType.INCIDENT_REPORT:
        data = await report_generator._generate_incident_report(
            request.cluster_ids, start, now
        )
    else:
        data = await report_generator._generate_capacity_plan(
            request.cluster_ids, start, now
        )

    content = report_generator._format_report(data, report_format)

    logger.info(
        "Report generated",
        report_type=request.report_type,
        clusters=len(request.cluster_ids),
        format=request.format,
    )

    return GenerateReportResponse(report=report, content=content)


@router.get("/types")
async def list_report_types() -> dict:
    """List available report types.

    Returns:
        Available report types and their descriptions
    """
    return {
        "types": [
            {
                "id": "executive_summary",
                "name": "Executive Summary",
                "description": "High-level overview of cluster health and key metrics",
            },
            {
                "id": "detailed_analysis",
                "name": "Detailed Analysis",
                "description": "In-depth analysis including anomaly detection results",
            },
            {
                "id": "incident_report",
                "name": "Incident Report",
                "description": "Summary of incidents and their resolutions",
            },
            {
                "id": "capacity_plan",
                "name": "Capacity Plan",
                "description": "Capacity planning recommendations based on trends",
            },
        ],
        "formats": ["json", "markdown", "html", "pdf"],
    }


@router.get("/history")
async def get_report_history(
    hours: int = Query(default=24, ge=1, le=168),
    report_type: str | None = None,
) -> list[Report]:
    """Get history of generated reports.

    Args:
        hours: Hours of history
        report_type: Optional type filter

    Returns:
        List of generated reports
    """
    # In production, would query from database
    return []
