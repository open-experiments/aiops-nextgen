"""Tool execution service.

Spec Reference: specs/04-intelligence-engine.md Section 6

Executes MCP tool calls against backend services.
"""

from __future__ import annotations

from typing import Any

import httpx

from shared.config import ServiceURLSettings
from shared.observability import get_logger

logger = get_logger(__name__)


class ToolExecutor:
    """Executes tool calls against backend services.

    Spec Reference: specs/04-intelligence-engine.md Section 6
    """

    def __init__(self, service_urls: ServiceURLSettings):
        self.cluster_registry_url = service_urls.cluster_registry_url
        self.observability_collector_url = service_urls.observability_collector_url
        self.timeout = 30.0

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a tool call and return the result.

        Spec Reference: specs/04-intelligence-engine.md Section 6.1
        """
        logger.info("Executing tool", tool=tool_name, arguments=arguments)

        try:
            if tool_name == "list_clusters":
                return await self._list_clusters(arguments)
            elif tool_name == "query_metrics":
                return await self._query_metrics(arguments)
            elif tool_name == "list_alerts":
                return await self._list_alerts(arguments)
            elif tool_name == "get_gpu_nodes":
                return await self._get_gpu_nodes(arguments)
            elif tool_name == "get_gpu_summary":
                return await self._get_gpu_summary()
            elif tool_name == "get_fleet_summary":
                return await self._get_fleet_summary()
            else:
                return {"error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            logger.error("Tool execution failed", tool=tool_name, error=str(e))
            return {"error": str(e)}

    async def _list_clusters(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """List clusters from Cluster Registry.

        Spec Reference: specs/02-cluster-registry.md Section 4.1
        """
        params = {}
        if arguments.get("environment"):
            params["environment"] = arguments["environment"]
        if arguments.get("cluster_type"):
            params["cluster_type"] = arguments["cluster_type"]
        if arguments.get("state"):
            params["state"] = arguments["state"]

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.cluster_registry_url}/api/v1/clusters",
                params=params,
            )
            response.raise_for_status()
            return response.json()

    async def _query_metrics(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute PromQL query via Observability Collector.

        Spec Reference: specs/03-observability-collector.md Section 4.1
        """
        payload = {"query": arguments.get("query", "up")}
        if arguments.get("cluster_ids"):
            payload["cluster_ids"] = arguments["cluster_ids"]

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.observability_collector_url}/api/v1/metrics/query",
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def _list_alerts(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """List alerts from Observability Collector.

        Spec Reference: specs/03-observability-collector.md Section 4.4
        """
        params = {}
        if arguments.get("cluster_ids"):
            params["cluster_ids"] = ",".join(arguments["cluster_ids"])
        if arguments.get("state"):
            params["state"] = arguments["state"]
        if arguments.get("severity"):
            params["severity"] = arguments["severity"]

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.observability_collector_url}/api/v1/alerts",
                params=params,
            )
            response.raise_for_status()
            return response.json()

    async def _get_gpu_nodes(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Get GPU nodes from Observability Collector.

        Spec Reference: specs/03-observability-collector.md Section 4.5
        """
        params = {}
        if arguments.get("cluster_ids"):
            params["cluster_ids"] = ",".join(arguments["cluster_ids"])

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.observability_collector_url}/api/v1/gpu/nodes",
                params=params,
            )
            response.raise_for_status()
            return response.json()

    async def _get_gpu_summary(self) -> dict[str, Any]:
        """Get GPU summary from Observability Collector.

        Spec Reference: specs/03-observability-collector.md Section 4.5
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.observability_collector_url}/api/v1/gpu/summary",
            )
            response.raise_for_status()
            return response.json()

    async def _get_fleet_summary(self) -> dict[str, Any]:
        """Get fleet summary from Cluster Registry.

        Spec Reference: specs/02-cluster-registry.md Section 4.1
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.cluster_registry_url}/api/v1/fleet/summary",
            )
            response.raise_for_status()
            return response.json()
