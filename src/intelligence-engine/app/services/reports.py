"""Report Generation Service.

Spec Reference: specs/04-intelligence-engine.md Section 6

Generates comprehensive reports:
- Cluster health summaries
- Anomaly reports
- GPU utilization reports
- Incident reports
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel

from shared.models import Report, ReportFormat, ReportType
from shared.observability import get_logger

logger = get_logger(__name__)


class ReportSection(BaseModel):
    """A section of a report."""

    title: str
    content: dict | str
    charts: list[dict] = []
    tables: list[dict] = []


class ReportData(BaseModel):
    """Complete report data structure."""

    title: str
    report_type: ReportType
    generated_at: datetime
    time_range_start: datetime
    time_range_end: datetime
    cluster_ids: list[str]
    sections: list[ReportSection]
    summary: str
    recommendations: list[str]


class ReportGenerator:
    """Generates various report types."""

    def __init__(self):
        """Initialize the report generator."""
        pass

    async def generate(
        self,
        report_type: ReportType,
        cluster_ids: list[str],
        start: datetime,
        end: datetime,
        report_format: ReportFormat = ReportFormat.JSON,
    ) -> Report:
        """Generate a report.

        Args:
            report_type: Type of report to generate
            cluster_ids: Clusters to include
            start: Report start time
            end: Report end time
            report_format: Output format

        Returns:
            Generated Report object
        """
        # Generate report data based on type
        if report_type == ReportType.EXECUTIVE_SUMMARY:
            data = await self._generate_executive_summary(cluster_ids, start, end)
        elif report_type == ReportType.DETAILED_ANALYSIS:
            data = await self._generate_detailed_analysis(cluster_ids, start, end)
        elif report_type == ReportType.INCIDENT_REPORT:
            data = await self._generate_incident_report(cluster_ids, start, end)
        elif report_type == ReportType.CAPACITY_PLAN:
            data = await self._generate_capacity_plan(cluster_ids, start, end)
        else:
            data = await self._generate_custom_report(cluster_ids, start, end)

        # Format the report
        formatted_content = self._format_report(data, report_format)

        return Report(
            id=uuid4(),
            title=data.title,
            report_type=report_type,
            format=report_format,
            cluster_scope=[],  # Would parse UUIDs from cluster_ids
            generated_by="system",
            storage_path=f"/reports/{uuid4().hex}.{report_format.value.lower()}",
            size_bytes=len(formatted_content.encode()),
            created_at=datetime.now(UTC),
        )

    async def _generate_executive_summary(
        self,
        cluster_ids: list[str],
        start: datetime,
        end: datetime,
    ) -> ReportData:
        """Generate executive summary report."""
        sections = []

        for cluster_id in cluster_ids:
            # Mock metrics - in production would query observability-collector
            cpu_avg = 45.2
            memory_avg = 62.8

            sections.append(
                ReportSection(
                    title=f"Cluster: {cluster_id}",
                    content={
                        "cpu_utilization_percent": round(cpu_avg, 2),
                        "memory_utilization_percent": round(memory_avg, 2),
                        "status": "healthy" if cpu_avg < 80 and memory_avg < 80 else "degraded",
                    },
                    tables=[
                        {
                            "title": "Resource Utilization",
                            "headers": ["Metric", "Average", "Status"],
                            "rows": [
                                ["CPU", f"{cpu_avg:.1f}%", "OK" if cpu_avg < 80 else "High"],
                                ["Memory", f"{memory_avg:.1f}%", "OK" if memory_avg < 80 else "High"],  # noqa: E501
                            ],
                        }
                    ],
                )
            )

        return ReportData(
            title="Executive Summary Report",
            report_type=ReportType.EXECUTIVE_SUMMARY,
            generated_at=datetime.now(UTC),
            time_range_start=start,
            time_range_end=end,
            cluster_ids=cluster_ids,
            sections=sections,
            summary=f"Health summary for {len(cluster_ids)} clusters",
            recommendations=self._generate_health_recommendations(sections),
        )

    async def _generate_detailed_analysis(
        self,
        cluster_ids: list[str],
        start: datetime,
        end: datetime,
    ) -> ReportData:
        """Generate detailed analysis report."""
        from .anomaly_detection import MetricData, anomaly_detector

        sections = []
        all_anomalies = []

        for cluster_id in cluster_ids:
            # Mock data for demonstration
            mock_values = [
                {"timestamp": start.timestamp() + i * 60, "value": 50 + (i % 10) * 2}
                for i in range(60)
            ]

            metric_data = MetricData(
                metric_name="cpu_usage",
                cluster_id=cluster_id,
                labels={"cluster": cluster_id},
                values=mock_values,
            )

            cluster_anomalies = anomaly_detector.detect(metric_data)
            all_anomalies.extend(cluster_anomalies)

            # Summarize by severity
            by_severity: dict[str, int] = {}
            for anomaly in cluster_anomalies:
                sev = anomaly.severity.value
                by_severity[sev] = by_severity.get(sev, 0) + 1

            sections.append(
                ReportSection(
                    title=f"Cluster: {cluster_id}",
                    content={
                        "total_anomalies": len(cluster_anomalies),
                        "by_severity": by_severity,
                    },
                    tables=[
                        {
                            "title": "Anomalies by Severity",
                            "headers": ["Severity", "Count"],
                            "rows": [[k, v] for k, v in by_severity.items()],
                        }
                    ],
                )
            )

        return ReportData(
            title="Detailed Analysis Report",
            report_type=ReportType.DETAILED_ANALYSIS,
            generated_at=datetime.now(UTC),
            time_range_start=start,
            time_range_end=end,
            cluster_ids=cluster_ids,
            sections=sections,
            summary=f"Found {len(all_anomalies)} anomalies across {len(cluster_ids)} clusters",
            recommendations=self._generate_anomaly_recommendations(all_anomalies),
        )

    async def _generate_incident_report(
        self,
        cluster_ids: list[str],
        start: datetime,
        end: datetime,
    ) -> ReportData:
        """Generate incident report."""
        sections = []

        for cluster_id in cluster_ids:
            sections.append(
                ReportSection(
                    title=f"Incident Report: {cluster_id}",
                    content={
                        "incident_count": 0,
                        "critical_incidents": 0,
                        "resolved_incidents": 0,
                    },
                )
            )

        return ReportData(
            title="Incident Report",
            report_type=ReportType.INCIDENT_REPORT,
            generated_at=datetime.now(UTC),
            time_range_start=start,
            time_range_end=end,
            cluster_ids=cluster_ids,
            sections=sections,
            summary=f"Incident report for {len(cluster_ids)} clusters",
            recommendations=[],
        )

    async def _generate_capacity_plan(
        self,
        cluster_ids: list[str],
        start: datetime,
        end: datetime,
    ) -> ReportData:
        """Generate capacity planning report."""
        sections = []

        for cluster_id in cluster_ids:
            sections.append(
                ReportSection(
                    title=f"Capacity Plan: {cluster_id}",
                    content={
                        "current_capacity": "70%",
                        "projected_growth": "5% per month",
                        "recommended_action": "Plan capacity expansion in 6 months",
                    },
                )
            )

        return ReportData(
            title="Capacity Planning Report",
            report_type=ReportType.CAPACITY_PLAN,
            generated_at=datetime.now(UTC),
            time_range_start=start,
            time_range_end=end,
            cluster_ids=cluster_ids,
            sections=sections,
            summary=f"Capacity plan for {len(cluster_ids)} clusters",
            recommendations=[
                "Monitor growth trends monthly",
                "Plan infrastructure expansion based on projections",
            ],
        )

    async def _generate_custom_report(
        self,
        cluster_ids: list[str],
        start: datetime,
        end: datetime,
    ) -> ReportData:
        """Generate custom report."""
        return ReportData(
            title="Custom Report",
            report_type=ReportType.EXECUTIVE_SUMMARY,
            generated_at=datetime.now(UTC),
            time_range_start=start,
            time_range_end=end,
            cluster_ids=cluster_ids,
            sections=[],
            summary="Custom report",
            recommendations=[],
        )

    def _format_report(self, data: ReportData, report_format: ReportFormat) -> str:
        """Format report data to specified format."""
        if report_format == ReportFormat.JSON:
            return data.model_dump_json(indent=2)

        elif report_format == ReportFormat.MARKDOWN:
            return self._format_markdown(data)

        elif report_format == ReportFormat.HTML:
            return self._format_html(data)

        elif report_format == ReportFormat.PDF:
            # PDF generation would require additional library
            return self._format_markdown(data)

        return data.model_dump_json()

    def _format_markdown(self, data: ReportData) -> str:
        """Format report as Markdown."""
        lines = [
            f"# {data.title}",
            "",
            f"**Generated:** {data.generated_at.isoformat()}",
            f"**Time Range:** {data.time_range_start.isoformat()} to "
            f"{data.time_range_end.isoformat()}",
            f"**Clusters:** {', '.join(data.cluster_ids)}",
            "",
            "## Summary",
            data.summary,
            "",
        ]

        for section in data.sections:
            lines.append(f"## {section.title}")
            lines.append("")

            if isinstance(section.content, dict):
                for key, value in section.content.items():
                    lines.append(f"- **{key}:** {value}")
            else:
                lines.append(str(section.content))

            for table in section.tables:
                lines.append("")
                lines.append(f"### {table['title']}")
                lines.append("")
                lines.append("| " + " | ".join(table["headers"]) + " |")
                lines.append("| " + " | ".join(["---"] * len(table["headers"])) + " |")
                for row in table["rows"]:
                    lines.append("| " + " | ".join(str(cell) for cell in row) + " |")

            lines.append("")

        if data.recommendations:
            lines.append("## Recommendations")
            for rec in data.recommendations:
                lines.append(f"- {rec}")

        return "\n".join(lines)

    def _format_html(self, data: ReportData) -> str:
        """Format report as HTML."""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <title>{data.title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
    </style>
</head>
<body>
    <h1>{data.title}</h1>
    <p><strong>Generated:</strong> {data.generated_at.isoformat()}</p>
    <p><strong>Summary:</strong> {data.summary}</p>
    {self._sections_to_html(data.sections)}
</body>
</html>
"""

    def _sections_to_html(self, sections: list[ReportSection]) -> str:
        """Convert sections to HTML."""
        html = []
        for section in sections:
            html.append(f"<h2>{section.title}</h2>")
            if isinstance(section.content, dict):
                html.append("<ul>")
                for k, v in section.content.items():
                    html.append(f"<li><strong>{k}:</strong> {v}</li>")
                html.append("</ul>")
        return "\n".join(html)

    def _generate_health_recommendations(
        self, sections: list[ReportSection]
    ) -> list[str]:
        """Generate health-based recommendations."""
        recommendations = []

        for section in sections:
            content = section.content
            if isinstance(content, dict):
                if content.get("cpu_utilization_percent", 0) > 80:
                    recommendations.append(
                        f"High CPU utilization in {section.title}. Consider scaling."
                    )
                if content.get("memory_utilization_percent", 0) > 80:
                    recommendations.append(
                        f"High memory utilization in {section.title}. Review memory limits."
                    )

        return recommendations

    def _generate_anomaly_recommendations(
        self, anomalies: list
    ) -> list[str]:
        """Generate anomaly-based recommendations."""
        if not anomalies:
            return ["No anomalies detected. System is operating normally."]

        recommendations = [
            f"Review {len(anomalies)} detected anomalies",
            "Run root cause analysis to identify underlying issues",
            "Check recent deployment changes that may have caused anomalies",
        ]

        return recommendations


# Singleton instance
report_generator = ReportGenerator()
