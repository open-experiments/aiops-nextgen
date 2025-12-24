"""MCP Tool definitions.

Spec Reference: specs/04-intelligence-engine.md Section 6.1

These tools are made available to the LLM for calling during chat.
"""

from __future__ import annotations

# Tool definitions in OpenAI function calling format
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_clusters",
            "description": "List all managed clusters with their status. Use this to get an overview of the fleet.",
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
            "name": "query_metrics",
            "description": "Execute a PromQL query across clusters to get metric data. Use this to check CPU, memory, network, or any Prometheus metrics.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "PromQL query to execute (e.g., 'up', 'container_cpu_usage_seconds_total')",
                    },
                    "cluster_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of cluster IDs to query. If empty, queries all clusters.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_alerts",
            "description": "List active alerts across clusters. Use this to check for any ongoing issues or warnings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cluster_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of cluster IDs to check. If empty, checks all clusters.",
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
    {
        "type": "function",
        "function": {
            "name": "get_gpu_nodes",
            "description": "Get GPU nodes and their current metrics including utilization, memory, and temperature.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cluster_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of cluster IDs to check. If empty, checks all clusters.",
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
            "description": "Get a fleet-wide summary of GPU utilization, total GPUs, and memory usage.",
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
            "name": "get_fleet_summary",
            "description": "Get a summary of the entire fleet including cluster counts by type, status, and environment.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]


def get_tools_for_persona(capabilities: list[str]) -> list[dict]:
    """Get tools available for a persona based on its capabilities.

    Spec Reference: specs/04-intelligence-engine.md Section 5.1
    """
    tool_name_map = {
        "list_clusters": "list_clusters",
        "query_metrics": "query_metrics",
        "list_alerts": "list_alerts",
        "get_gpu_nodes": "get_gpu_nodes",
        "get_gpu_summary": "get_gpu_summary",
        "get_fleet_summary": "get_fleet_summary",
    }

    return [
        tool
        for tool in TOOLS
        if tool["function"]["name"] in capabilities
        or tool["function"]["name"] in tool_name_map.values()
    ]
