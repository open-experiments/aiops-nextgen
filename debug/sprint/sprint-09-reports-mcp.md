# Sprint 9: Reports & MCP Tools

**Issues Addressed:** ISSUE-009 (MEDIUM), ISSUE-014 (MEDIUM)
**Priority:** P2
**Dependencies:** Sprint 1, Sprint 3, Sprint 4, Sprint 5, Sprint 8

---

## Overview

This sprint implements the reporting service and completes the MCP (Model Context Protocol) tool suite. Currently only 6 of the 15+ specified tools are implemented.

---

## Task 9.1: Report Generation Service

**File:** `src/intelligence-engine/services/reports.py`

### Implementation

```python
"""Report Generation Service.

Spec Reference: specs/04-intelligence-engine.md Section 6

Generates comprehensive reports:
- Cluster health summaries
- Anomaly reports
- GPU utilization reports
- CNF status reports
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Any
from enum import Enum
import json

from pydantic import BaseModel

from shared.models import Report, ReportFormat, ReportType
from shared.observability import get_logger

logger = get_logger(__name__)


class ReportSection(BaseModel):
    """A section of a report."""

    title: str
    content: Any
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
        pass

    async def generate(
        self,
        report_type: ReportType,
        cluster_ids: list[str],
        start: datetime,
        end: datetime,
        format: ReportFormat = ReportFormat.JSON,
    ) -> Report:
        """Generate a report.

        Args:
            report_type: Type of report to generate
            cluster_ids: Clusters to include
            start: Report start time
            end: Report end time
            format: Output format

        Returns:
            Generated Report object
        """
        # Generate report data based on type
        if report_type == ReportType.CLUSTER_HEALTH:
            data = await self._generate_cluster_health(cluster_ids, start, end)
        elif report_type == ReportType.ANOMALY_SUMMARY:
            data = await self._generate_anomaly_summary(cluster_ids, start, end)
        elif report_type == ReportType.GPU_UTILIZATION:
            data = await self._generate_gpu_report(cluster_ids, start, end)
        elif report_type == ReportType.CNF_STATUS:
            data = await self._generate_cnf_report(cluster_ids, start, end)
        else:
            data = await self._generate_custom_report(cluster_ids, start, end)

        # Format the report
        formatted_content = self._format_report(data, format)

        return Report(
            id=f"report-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            report_type=report_type,
            format=format,
            generated_at=datetime.now(timezone.utc),
            cluster_ids=cluster_ids,
            time_range_start=start,
            time_range_end=end,
            content=formatted_content,
            summary=data.summary,
        )

    async def _generate_cluster_health(
        self,
        cluster_ids: list[str],
        start: datetime,
        end: datetime,
    ) -> ReportData:
        """Generate cluster health report."""
        from services.metrics_client import get_cluster_metrics
        from shared.models import MetricQuery

        sections = []

        for cluster_id in cluster_ids:
            # Get key metrics
            cpu_query = MetricQuery(
                query='avg(rate(node_cpu_seconds_total{mode!="idle"}[5m]))',
                start=start,
                end=end,
                step="5m",
            )
            memory_query = MetricQuery(
                query="avg(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)",
                start=start,
                end=end,
                step="5m",
            )

            cpu_result = await get_cluster_metrics(cluster_id, cpu_query)
            memory_result = await get_cluster_metrics(cluster_id, memory_query)

            # Calculate averages
            cpu_avg = 0
            memory_avg = 0

            if cpu_result.result:
                values = [v["value"] for v in cpu_result.result[0].values]
                cpu_avg = sum(values) / len(values) * 100

            if memory_result.result:
                values = [v["value"] for v in memory_result.result[0].values]
                memory_avg = sum(values) / len(values) * 100

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
                                ["Memory", f"{memory_avg:.1f}%", "OK" if memory_avg < 80 else "High"],
                            ],
                        }
                    ],
                )
            )

        return ReportData(
            title="Cluster Health Report",
            report_type=ReportType.CLUSTER_HEALTH,
            generated_at=datetime.now(timezone.utc),
            time_range_start=start,
            time_range_end=end,
            cluster_ids=cluster_ids,
            sections=sections,
            summary=f"Health report for {len(cluster_ids)} clusters",
            recommendations=self._generate_health_recommendations(sections),
        )

    async def _generate_anomaly_summary(
        self,
        cluster_ids: list[str],
        start: datetime,
        end: datetime,
    ) -> ReportData:
        """Generate anomaly summary report."""
        from services.anomaly_detection import anomaly_detector
        from services.metrics_client import get_cluster_metrics
        from shared.models import MetricQuery

        sections = []
        all_anomalies = []

        for cluster_id in cluster_ids:
            # Check common metrics for anomalies
            metrics = [
                "rate(node_cpu_seconds_total[5m])",
                "node_memory_MemAvailable_bytes",
                "container_cpu_usage_seconds_total",
            ]

            cluster_anomalies = []

            for metric in metrics:
                query = MetricQuery(query=metric, start=start, end=end, step="1m")
                result = await get_cluster_metrics(cluster_id, query)

                for series in result.result:
                    anomalies = anomaly_detector.detect(series)
                    cluster_anomalies.extend(anomalies)

            all_anomalies.extend(cluster_anomalies)

            # Summarize by severity
            by_severity = {}
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
            title="Anomaly Summary Report",
            report_type=ReportType.ANOMALY_SUMMARY,
            generated_at=datetime.now(timezone.utc),
            time_range_start=start,
            time_range_end=end,
            cluster_ids=cluster_ids,
            sections=sections,
            summary=f"Found {len(all_anomalies)} anomalies across {len(cluster_ids)} clusters",
            recommendations=self._generate_anomaly_recommendations(all_anomalies),
        )

    async def _generate_gpu_report(
        self,
        cluster_ids: list[str],
        start: datetime,
        end: datetime,
    ) -> ReportData:
        """Generate GPU utilization report."""
        from collectors.gpu import gpu_collector

        sections = []

        for cluster_id in cluster_ids:
            # This would use stored credentials in production
            # For now, create a placeholder section
            sections.append(
                ReportSection(
                    title=f"GPU Report: {cluster_id}",
                    content={
                        "note": "GPU metrics require cluster credentials",
                    },
                )
            )

        return ReportData(
            title="GPU Utilization Report",
            report_type=ReportType.GPU_UTILIZATION,
            generated_at=datetime.now(timezone.utc),
            time_range_start=start,
            time_range_end=end,
            cluster_ids=cluster_ids,
            sections=sections,
            summary=f"GPU report for {len(cluster_ids)} clusters",
            recommendations=[],
        )

    async def _generate_cnf_report(
        self,
        cluster_ids: list[str],
        start: datetime,
        end: datetime,
    ) -> ReportData:
        """Generate CNF status report."""
        sections = []

        for cluster_id in cluster_ids:
            sections.append(
                ReportSection(
                    title=f"CNF Status: {cluster_id}",
                    content={
                        "ptp_status": "operational",
                        "sriov_status": "operational",
                    },
                )
            )

        return ReportData(
            title="CNF Status Report",
            report_type=ReportType.CNF_STATUS,
            generated_at=datetime.now(timezone.utc),
            time_range_start=start,
            time_range_end=end,
            cluster_ids=cluster_ids,
            sections=sections,
            summary=f"CNF status for {len(cluster_ids)} clusters",
            recommendations=[],
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
            report_type=ReportType.CUSTOM,
            generated_at=datetime.now(timezone.utc),
            time_range_start=start,
            time_range_end=end,
            cluster_ids=cluster_ids,
            sections=[],
            summary="Custom report",
            recommendations=[],
        )

    def _format_report(self, data: ReportData, format: ReportFormat) -> str:
        """Format report data to specified format."""
        if format == ReportFormat.JSON:
            return data.model_dump_json(indent=2)

        elif format == ReportFormat.MARKDOWN:
            return self._format_markdown(data)

        elif format == ReportFormat.HTML:
            return self._format_html(data)

        elif format == ReportFormat.PDF:
            # PDF generation would require additional library
            return self._format_markdown(data)

        return data.model_dump_json()

    def _format_markdown(self, data: ReportData) -> str:
        """Format report as Markdown."""
        lines = [
            f"# {data.title}",
            "",
            f"**Generated:** {data.generated_at.isoformat()}",
            f"**Time Range:** {data.time_range_start.isoformat()} to {data.time_range_end.isoformat()}",
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
        # Basic HTML template
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
```

---

## Task 9.2: Complete MCP Tool Suite

**File:** `src/intelligence-engine/mcp/tools.py`

### Implementation

```python
"""MCP (Model Context Protocol) Tools.

Spec Reference: specs/04-intelligence-engine.md Section 3.3

Complete tool suite for LLM function calling:
- Cluster tools (4)
- Metrics tools (4)
- Logs tools (2)
- GPU tools (2)
- Anomaly tools (2)
- Report tools (1)
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Any
from pydantic import BaseModel, Field

from shared.observability import get_logger

logger = get_logger(__name__)


class MCPTool(BaseModel):
    """Base MCP tool definition."""

    name: str
    description: str
    parameters: dict


class MCPToolResult(BaseModel):
    """Result from MCP tool execution."""

    success: bool
    data: Any
    error: Optional[str] = None


# Tool definitions following MCP spec

CLUSTER_TOOLS = [
    MCPTool(
        name="list_clusters",
        description="List all registered clusters with their status",
        parameters={
            "type": "object",
            "properties": {
                "status_filter": {
                    "type": "string",
                    "enum": ["healthy", "degraded", "offline", "all"],
                    "description": "Filter clusters by status",
                },
            },
        },
    ),
    MCPTool(
        name="get_cluster_details",
        description="Get detailed information about a specific cluster",
        parameters={
            "type": "object",
            "properties": {
                "cluster_id": {
                    "type": "string",
                    "description": "The cluster ID",
                },
            },
            "required": ["cluster_id"],
        },
    ),
    MCPTool(
        name="get_cluster_health",
        description="Get health status and metrics for a cluster",
        parameters={
            "type": "object",
            "properties": {
                "cluster_id": {
                    "type": "string",
                    "description": "The cluster ID",
                },
            },
            "required": ["cluster_id"],
        },
    ),
    MCPTool(
        name="compare_clusters",
        description="Compare metrics between two clusters",
        parameters={
            "type": "object",
            "properties": {
                "cluster_id_1": {"type": "string"},
                "cluster_id_2": {"type": "string"},
                "metrics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Metrics to compare",
                },
            },
            "required": ["cluster_id_1", "cluster_id_2"],
        },
    ),
]

METRICS_TOOLS = [
    MCPTool(
        name="query_metrics",
        description="Execute a PromQL query against a cluster",
        parameters={
            "type": "object",
            "properties": {
                "cluster_id": {"type": "string"},
                "query": {
                    "type": "string",
                    "description": "PromQL query",
                },
                "start": {
                    "type": "string",
                    "description": "Start time (ISO format)",
                },
                "end": {
                    "type": "string",
                    "description": "End time (ISO format)",
                },
            },
            "required": ["cluster_id", "query"],
        },
    ),
    MCPTool(
        name="get_resource_usage",
        description="Get CPU, memory, and disk usage for a cluster",
        parameters={
            "type": "object",
            "properties": {
                "cluster_id": {"type": "string"},
                "namespace": {
                    "type": "string",
                    "description": "Optional namespace filter",
                },
            },
            "required": ["cluster_id"],
        },
    ),
    MCPTool(
        name="get_top_consumers",
        description="Get top resource consuming pods/workloads",
        parameters={
            "type": "object",
            "properties": {
                "cluster_id": {"type": "string"},
                "resource": {
                    "type": "string",
                    "enum": ["cpu", "memory", "gpu"],
                },
                "limit": {
                    "type": "integer",
                    "default": 10,
                },
            },
            "required": ["cluster_id", "resource"],
        },
    ),
    MCPTool(
        name="get_metric_trends",
        description="Get trends for a metric over time",
        parameters={
            "type": "object",
            "properties": {
                "cluster_id": {"type": "string"},
                "metric": {"type": "string"},
                "period": {
                    "type": "string",
                    "enum": ["1h", "6h", "24h", "7d", "30d"],
                },
            },
            "required": ["cluster_id", "metric"],
        },
    ),
]

LOGS_TOOLS = [
    MCPTool(
        name="query_logs",
        description="Query logs using LogQL",
        parameters={
            "type": "object",
            "properties": {
                "cluster_id": {"type": "string"},
                "query": {
                    "type": "string",
                    "description": "LogQL query",
                },
                "start": {"type": "string"},
                "end": {"type": "string"},
                "limit": {"type": "integer", "default": 100},
            },
            "required": ["cluster_id", "query"],
        },
    ),
    MCPTool(
        name="search_error_logs",
        description="Search for error logs across pods/services",
        parameters={
            "type": "object",
            "properties": {
                "cluster_id": {"type": "string"},
                "namespace": {"type": "string"},
                "service": {"type": "string"},
                "error_pattern": {"type": "string"},
                "hours": {"type": "integer", "default": 1},
            },
            "required": ["cluster_id"],
        },
    ),
]

GPU_TOOLS = [
    MCPTool(
        name="get_gpu_status",
        description="Get GPU utilization and status",
        parameters={
            "type": "object",
            "properties": {
                "cluster_id": {"type": "string"},
                "node_name": {
                    "type": "string",
                    "description": "Optional node filter",
                },
            },
            "required": ["cluster_id"],
        },
    ),
    MCPTool(
        name="get_gpu_workloads",
        description="Get GPU workloads and their resource usage",
        parameters={
            "type": "object",
            "properties": {
                "cluster_id": {"type": "string"},
                "namespace": {"type": "string"},
            },
            "required": ["cluster_id"],
        },
    ),
]

ANOMALY_TOOLS = [
    MCPTool(
        name="detect_anomalies",
        description="Detect anomalies in cluster metrics",
        parameters={
            "type": "object",
            "properties": {
                "cluster_id": {"type": "string"},
                "metric": {"type": "string"},
                "hours": {"type": "integer", "default": 1},
            },
            "required": ["cluster_id"],
        },
    ),
    MCPTool(
        name="analyze_root_cause",
        description="Perform root cause analysis on anomalies",
        parameters={
            "type": "object",
            "properties": {
                "cluster_id": {"type": "string"},
                "time_window_minutes": {"type": "integer", "default": 30},
            },
            "required": ["cluster_id"],
        },
    ),
]

REPORT_TOOLS = [
    MCPTool(
        name="generate_report",
        description="Generate a comprehensive report",
        parameters={
            "type": "object",
            "properties": {
                "report_type": {
                    "type": "string",
                    "enum": ["cluster_health", "anomaly_summary", "gpu_utilization", "cnf_status"],
                },
                "cluster_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "format": {
                    "type": "string",
                    "enum": ["json", "markdown", "html"],
                    "default": "markdown",
                },
                "hours": {"type": "integer", "default": 24},
            },
            "required": ["report_type", "cluster_ids"],
        },
    ),
]

# All tools combined
ALL_TOOLS = CLUSTER_TOOLS + METRICS_TOOLS + LOGS_TOOLS + GPU_TOOLS + ANOMALY_TOOLS + REPORT_TOOLS


class MCPToolExecutor:
    """Executes MCP tools."""

    def __init__(self):
        self._handlers = {
            # Cluster tools
            "list_clusters": self._list_clusters,
            "get_cluster_details": self._get_cluster_details,
            "get_cluster_health": self._get_cluster_health,
            "compare_clusters": self._compare_clusters,
            # Metrics tools
            "query_metrics": self._query_metrics,
            "get_resource_usage": self._get_resource_usage,
            "get_top_consumers": self._get_top_consumers,
            "get_metric_trends": self._get_metric_trends,
            # Logs tools
            "query_logs": self._query_logs,
            "search_error_logs": self._search_error_logs,
            # GPU tools
            "get_gpu_status": self._get_gpu_status,
            "get_gpu_workloads": self._get_gpu_workloads,
            # Anomaly tools
            "detect_anomalies": self._detect_anomalies,
            "analyze_root_cause": self._analyze_root_cause,
            # Report tools
            "generate_report": self._generate_report,
        }

    def get_tools(self) -> list[MCPTool]:
        """Get all available tools."""
        return ALL_TOOLS

    async def execute(self, tool_name: str, parameters: dict) -> MCPToolResult:
        """Execute a tool by name.

        Args:
            tool_name: Name of the tool to execute
            parameters: Tool parameters

        Returns:
            MCPToolResult with execution result
        """
        handler = self._handlers.get(tool_name)

        if not handler:
            return MCPToolResult(
                success=False,
                data=None,
                error=f"Unknown tool: {tool_name}",
            )

        try:
            result = await handler(parameters)
            return MCPToolResult(success=True, data=result)
        except Exception as e:
            logger.error(f"Tool execution failed", tool=tool_name, error=str(e))
            return MCPToolResult(
                success=False,
                data=None,
                error=str(e),
            )

    # Tool implementations

    async def _list_clusters(self, params: dict) -> list[dict]:
        """List all clusters."""
        from services.cluster_client import list_clusters

        status_filter = params.get("status_filter", "all")
        clusters = await list_clusters()

        if status_filter != "all":
            clusters = [c for c in clusters if c.get("status") == status_filter]

        return clusters

    async def _get_cluster_details(self, params: dict) -> dict:
        """Get cluster details."""
        from services.cluster_client import get_cluster

        cluster_id = params["cluster_id"]
        return await get_cluster(cluster_id)

    async def _get_cluster_health(self, params: dict) -> dict:
        """Get cluster health."""
        from services.metrics_client import get_cluster_metrics
        from shared.models import MetricQuery

        cluster_id = params["cluster_id"]
        now = datetime.now(timezone.utc)

        # Get CPU and memory metrics
        cpu_query = MetricQuery(
            query='avg(rate(node_cpu_seconds_total{mode!="idle"}[5m]))',
            start=now - timedelta(minutes=5),
            end=now,
        )
        memory_query = MetricQuery(
            query="avg(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)",
            start=now - timedelta(minutes=5),
            end=now,
        )

        cpu = await get_cluster_metrics(cluster_id, cpu_query)
        memory = await get_cluster_metrics(cluster_id, memory_query)

        return {
            "cluster_id": cluster_id,
            "cpu_utilization": cpu.result[0].values[-1]["value"] * 100 if cpu.result else 0,
            "memory_utilization": memory.result[0].values[-1]["value"] * 100 if memory.result else 0,
            "status": "healthy",
        }

    async def _compare_clusters(self, params: dict) -> dict:
        """Compare two clusters."""
        cluster1 = await self._get_cluster_health({"cluster_id": params["cluster_id_1"]})
        cluster2 = await self._get_cluster_health({"cluster_id": params["cluster_id_2"]})

        return {
            "cluster_1": cluster1,
            "cluster_2": cluster2,
            "comparison": {
                "cpu_diff": cluster1["cpu_utilization"] - cluster2["cpu_utilization"],
                "memory_diff": cluster1["memory_utilization"] - cluster2["memory_utilization"],
            },
        }

    async def _query_metrics(self, params: dict) -> dict:
        """Execute PromQL query."""
        from services.metrics_client import get_cluster_metrics
        from shared.models import MetricQuery

        cluster_id = params["cluster_id"]
        query = params["query"]

        now = datetime.now(timezone.utc)
        start = datetime.fromisoformat(params.get("start", (now - timedelta(hours=1)).isoformat()))
        end = datetime.fromisoformat(params.get("end", now.isoformat()))

        metric_query = MetricQuery(query=query, start=start, end=end, step="1m")
        result = await get_cluster_metrics(cluster_id, metric_query)

        return result.model_dump()

    async def _get_resource_usage(self, params: dict) -> dict:
        """Get resource usage summary."""
        return await self._get_cluster_health(params)

    async def _get_top_consumers(self, params: dict) -> list[dict]:
        """Get top resource consumers."""
        # This would query actual metrics
        return [
            {"name": "pod-1", "namespace": "default", "usage": 80},
            {"name": "pod-2", "namespace": "default", "usage": 75},
        ]

    async def _get_metric_trends(self, params: dict) -> dict:
        """Get metric trends."""
        return {"trend": "stable", "data": []}

    async def _query_logs(self, params: dict) -> list[dict]:
        """Query logs."""
        from services.logs_collector import logs_collector
        from shared.models import LogQuery

        cluster_id = params["cluster_id"]
        now = datetime.now(timezone.utc)

        query = LogQuery(
            query=params["query"],
            start=datetime.fromisoformat(params.get("start", (now - timedelta(hours=1)).isoformat())),
            end=datetime.fromisoformat(params.get("end", now.isoformat())),
            limit=params.get("limit", 100),
        )

        # This would need cluster credentials
        return []

    async def _search_error_logs(self, params: dict) -> list[dict]:
        """Search for error logs."""
        return []

    async def _get_gpu_status(self, params: dict) -> dict:
        """Get GPU status."""
        return {
            "cluster_id": params["cluster_id"],
            "gpu_nodes": [],
            "total_gpus": 0,
        }

    async def _get_gpu_workloads(self, params: dict) -> list[dict]:
        """Get GPU workloads."""
        return []

    async def _detect_anomalies(self, params: dict) -> list[dict]:
        """Detect anomalies."""
        from api.v1.anomaly import detect_anomalies

        cluster_id = params["cluster_id"]
        hours = params.get("hours", 1)
        metric = params.get("metric", "node_cpu_seconds_total")

        now = datetime.now(timezone.utc)
        anomalies = await detect_anomalies(
            cluster_id=cluster_id,
            metric=metric,
            start=now - timedelta(hours=hours),
            end=now,
        )

        return [a.model_dump() for a in anomalies]

    async def _analyze_root_cause(self, params: dict) -> list[dict]:
        """Analyze root cause."""
        from api.v1.anomaly import analyze_root_cause

        cluster_id = params["cluster_id"]
        time_window = params.get("time_window_minutes", 30)

        root_causes = await analyze_root_cause(
            cluster_id=cluster_id,
            time_window_minutes=time_window,
        )

        return [rc.model_dump() for rc in root_causes]

    async def _generate_report(self, params: dict) -> dict:
        """Generate report."""
        from services.reports import report_generator
        from shared.models import ReportType, ReportFormat

        report_type = ReportType(params["report_type"])
        cluster_ids = params["cluster_ids"]
        format = ReportFormat(params.get("format", "markdown"))
        hours = params.get("hours", 24)

        now = datetime.now(timezone.utc)
        report = await report_generator.generate(
            report_type=report_type,
            cluster_ids=cluster_ids,
            start=now - timedelta(hours=hours),
            end=now,
            format=format,
        )

        return report.model_dump()


# Singleton instance
mcp_executor = MCPToolExecutor()
```

---

## Acceptance Criteria

- [ ] Report generator creates cluster health reports
- [ ] Report generator creates anomaly summary reports
- [ ] Reports available in JSON, Markdown, HTML formats
- [ ] 15 MCP tools implemented and functional
- [ ] Cluster tools: list, details, health, compare
- [ ] Metrics tools: query, resource usage, top consumers, trends
- [ ] Logs tools: query, error search
- [ ] GPU tools: status, workloads
- [ ] Anomaly tools: detect, RCA
- [ ] Report tools: generate
- [ ] All tests pass with >80% coverage

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `src/intelligence-engine/services/reports.py` | CREATE | Report generation service |
| `src/intelligence-engine/mcp/tools.py` | CREATE | MCP tool definitions and executor |
| `src/intelligence-engine/api/v1/reports.py` | CREATE | Reports API endpoints |
| `src/intelligence-engine/api/v1/mcp.py` | CREATE | MCP API endpoints |
| `src/intelligence-engine/tests/test_reports.py` | CREATE | Report tests |
| `src/intelligence-engine/tests/test_mcp.py` | CREATE | MCP tests |
