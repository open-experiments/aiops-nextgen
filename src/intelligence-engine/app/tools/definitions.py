"""MCP Tool definitions.

Spec Reference: specs/04-intelligence-engine.md Section 6.1

Complete tool suite for LLM function calling:
- Cluster tools (4)
- Metrics tools (4)
- Logs tools (2)
- GPU tools (2)
- Anomaly tools (2)
- Report tools (1)
"""

from __future__ import annotations

# Tool definitions in OpenAI function calling format
CLUSTER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_clusters",
            "description": "List all managed clusters with their status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "environment": {
                        "type": "string",
                        "enum": ["PRODUCTION", "STAGING", "DEVELOPMENT", "LAB"],
                        "description": "Filter by environment",
                    },
                    "cluster_type": {
                        "type": "string",
                        "enum": ["HUB", "SPOKE", "EDGE", "FAR_EDGE"],
                        "description": "Filter by cluster type",
                    },
                    "state": {
                        "type": "string",
                        "enum": ["ONLINE", "OFFLINE", "DEGRADED", "UNKNOWN"],
                        "description": "Filter by cluster state",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cluster_details",
            "description": "Get detailed cluster info including metadata and capabilities.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cluster_id": {
                        "type": "string",
                        "description": "The cluster ID to get details for",
                    },
                },
                "required": ["cluster_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cluster_health",
            "description": "Get cluster health status including CPU, memory, and pods.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cluster_id": {
                        "type": "string",
                        "description": "The cluster ID to check health for",
                    },
                },
                "required": ["cluster_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_clusters",
            "description": "Compare metrics between two clusters to identify differences.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cluster_id_1": {
                        "type": "string",
                        "description": "First cluster ID",
                    },
                    "cluster_id_2": {
                        "type": "string",
                        "description": "Second cluster ID",
                    },
                    "metrics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Metrics to compare (e.g., cpu_usage, memory_usage)",
                    },
                },
                "required": ["cluster_id_1", "cluster_id_2"],
            },
        },
    },
]

METRICS_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_metrics",
            "description": (
                "Execute a PromQL query across clusters. "
                "Use for CPU, memory, network, or any Prometheus metrics."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "PromQL query (e.g., 'up', 'container_cpu_usage')",
                    },
                    "cluster_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Cluster IDs to query. Empty = all.",
                    },
                    "start": {
                        "type": "string",
                        "description": "Start time (ISO format, defaults to 1 hour ago)",
                    },
                    "end": {
                        "type": "string",
                        "description": "End time (ISO format, defaults to now)",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_resource_usage",
            "description": "Get CPU, memory, and disk usage summary for a cluster or namespace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cluster_id": {
                        "type": "string",
                        "description": "The cluster ID",
                    },
                    "namespace": {
                        "type": "string",
                        "description": "Optional namespace filter",
                    },
                },
                "required": ["cluster_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_consumers",
            "description": "Get top resource consuming pods or workloads.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cluster_id": {
                        "type": "string",
                        "description": "The cluster ID",
                    },
                    "resource": {
                        "type": "string",
                        "enum": ["cpu", "memory", "gpu"],
                        "description": "Resource type to rank by",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of results (default 10)",
                        "default": 10,
                    },
                },
                "required": ["cluster_id", "resource"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_metric_trends",
            "description": "Get trends for a metric over time with basic analysis.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cluster_id": {
                        "type": "string",
                        "description": "The cluster ID",
                    },
                    "metric": {
                        "type": "string",
                        "description": "Metric name or PromQL query",
                    },
                    "period": {
                        "type": "string",
                        "enum": ["1h", "6h", "24h", "7d", "30d"],
                        "description": "Time period to analyze",
                    },
                },
                "required": ["cluster_id", "metric"],
            },
        },
    },
]

ALERT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_alerts",
            "description": "List active alerts across clusters for ongoing issues.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cluster_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Cluster IDs to check. Empty = all.",
                    },
                    "state": {
                        "type": "string",
                        "enum": ["FIRING", "RESOLVED", "PENDING"],
                        "description": "Filter by alert state",
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["CRITICAL", "WARNING", "INFO"],
                        "description": "Filter by severity level",
                    },
                },
                "required": [],
            },
        },
    },
]

LOGS_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_logs",
            "description": "Query logs using LogQL from Loki.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cluster_id": {
                        "type": "string",
                        "description": "The cluster ID",
                    },
                    "query": {
                        "type": "string",
                        "description": "LogQL query (e.g., '{namespace=\"default\"}')",
                    },
                    "start": {
                        "type": "string",
                        "description": "Start time (ISO format)",
                    },
                    "end": {
                        "type": "string",
                        "description": "End time (ISO format)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default 100)",
                        "default": 100,
                    },
                },
                "required": ["cluster_id", "query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_error_logs",
            "description": "Search for error logs across pods/services.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cluster_id": {
                        "type": "string",
                        "description": "The cluster ID",
                    },
                    "namespace": {
                        "type": "string",
                        "description": "Namespace to search",
                    },
                    "service": {
                        "type": "string",
                        "description": "Service name to filter",
                    },
                    "error_pattern": {
                        "type": "string",
                        "description": "Error pattern to match",
                    },
                    "hours": {
                        "type": "integer",
                        "description": "Hours of logs to search (default 1)",
                        "default": 1,
                    },
                },
                "required": ["cluster_id"],
            },
        },
    },
]

GPU_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_gpu_nodes",
            "description": "Get GPU nodes with utilization, memory, and temperature.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cluster_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Cluster IDs to check. Empty = all.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_gpu_summary",
            "description": "Get fleet-wide GPU utilization summary.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_gpu_workloads",
            "description": "Get GPU workloads and their resource usage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cluster_id": {
                        "type": "string",
                        "description": "The cluster ID",
                    },
                    "namespace": {
                        "type": "string",
                        "description": "Optional namespace filter",
                    },
                },
                "required": ["cluster_id"],
            },
        },
    },
]

ANOMALY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "detect_anomalies",
            "description": "Detect anomalies in cluster metrics using statistical and ML methods.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cluster_id": {
                        "type": "string",
                        "description": "The cluster ID",
                    },
                    "metric": {
                        "type": "string",
                        "description": "Metric to analyze for anomalies",
                    },
                    "hours": {
                        "type": "integer",
                        "description": "Hours of data to analyze (default 1)",
                        "default": 1,
                    },
                    "methods": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["zscore", "iqr", "isolation_forest", "seasonal", "lof"],
                        },
                        "description": "Detection methods to use",
                    },
                },
                "required": ["cluster_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_root_cause",
            "description": "Perform RCA on anomalies to identify causes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cluster_id": {
                        "type": "string",
                        "description": "The cluster ID",
                    },
                    "time_window_minutes": {
                        "type": "integer",
                        "description": "Time window to analyze (default 30)",
                        "default": 30,
                    },
                },
                "required": ["cluster_id"],
            },
        },
    },
]

REPORT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "generate_report",
            "description": "Generate a comprehensive report for clusters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "report_type": {
                        "type": "string",
                        "enum": [
                            "executive_summary",
                            "detailed_analysis",
                            "incident_report",
                            "capacity_plan",
                        ],
                        "description": "Type of report to generate",
                    },
                    "cluster_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Clusters to include in report",
                    },
                    "format": {
                        "type": "string",
                        "enum": ["json", "markdown", "html"],
                        "description": "Output format (default markdown)",
                        "default": "markdown",
                    },
                    "hours": {
                        "type": "integer",
                        "description": "Hours of data to include (default 24)",
                        "default": 24,
                    },
                },
                "required": ["report_type", "cluster_ids"],
            },
        },
    },
]

FLEET_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_fleet_summary",
            "description": "Get fleet summary with cluster counts by type and status.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]

# All tools combined
TOOLS = (
    CLUSTER_TOOLS
    + METRICS_TOOLS
    + ALERT_TOOLS
    + LOGS_TOOLS
    + GPU_TOOLS
    + ANOMALY_TOOLS
    + REPORT_TOOLS
    + FLEET_TOOLS
)

# Tool count summary
TOOL_COUNTS = {
    "cluster": len(CLUSTER_TOOLS),
    "metrics": len(METRICS_TOOLS),
    "alerts": len(ALERT_TOOLS),
    "logs": len(LOGS_TOOLS),
    "gpu": len(GPU_TOOLS),
    "anomaly": len(ANOMALY_TOOLS),
    "report": len(REPORT_TOOLS),
    "fleet": len(FLEET_TOOLS),
    "total": len(TOOLS),
}


def get_tools_for_persona(capabilities: list[str]) -> list[dict]:
    """Get tools available for a persona based on its capabilities.

    Spec Reference: specs/04-intelligence-engine.md Section 5.1
    """
    if not capabilities:
        return TOOLS

    tool_names = {tool["function"]["name"] for tool in TOOLS}

    return [
        tool
        for tool in TOOLS
        if tool["function"]["name"] in capabilities or tool["function"]["name"] in tool_names
    ]


def get_tool_summary() -> dict:
    """Get summary of available tools."""
    return {
        "total_tools": len(TOOLS),
        "categories": TOOL_COUNTS,
        "tools": [t["function"]["name"] for t in TOOLS],
    }
