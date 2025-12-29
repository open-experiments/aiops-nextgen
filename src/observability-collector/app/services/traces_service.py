"""Traces Service for distributed trace queries.

Spec Reference: specs/03-observability-collector.md Section 4.2
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from app.clients.cluster_registry import ClusterRegistryClient
from app.collectors.tempo_collector import TempoCollector
from shared.config import get_settings
from shared.observability import get_logger

logger = get_logger(__name__)


class TracesService:
    """Service for distributed trace queries across clusters.

    Spec Reference: specs/03-observability-collector.md Section 4.2
    """

    def __init__(self):
        self.settings = get_settings()
        self.cluster_registry = ClusterRegistryClient(
            base_url=self.settings.services.cluster_registry_url
        )
        self.collector = TempoCollector()

    async def search(
        self,
        cluster_id: str | None = None,
        service_name: str | None = None,
        operation: str | None = None,
        tags: dict[str, str] | None = None,
        min_duration: str | None = None,
        max_duration: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search traces across clusters.

        Args:
            cluster_id: Optional specific cluster
            service_name: Filter by service
            operation: Filter by operation
            tags: Filter by tags
            min_duration: Minimum duration
            max_duration: Maximum duration
            start_time: Search start time
            end_time: Search end time
            limit: Max traces per cluster

        Returns:
            List of results per cluster
        """
        if cluster_id:
            cluster = await self.cluster_registry.get_cluster(cluster_id)
            if not cluster:
                return [{
                    "cluster_id": cluster_id,
                    "cluster_name": "unknown",
                    "status": "ERROR",
                    "error": "Cluster not found",
                    "traces": [],
                }]
            clusters = [cluster]
        else:
            clusters = await self.cluster_registry.list_online_clusters()

        # Filter to clusters with Tempo configured
        tempo_clusters = [
            c for c in clusters
            if c.get("endpoints", {}).get("tempo_url")
        ]

        if not tempo_clusters:
            return [{
                "cluster_id": cluster_id or "all",
                "cluster_name": "N/A",
                "status": "ERROR",
                "error": "No clusters with Tempo configured",
                "traces": [],
            }]

        # Execute searches concurrently
        tasks = [
            self.collector.search_traces(
                cluster=c,
                service_name=service_name,
                operation=operation,
                tags=tags,
                min_duration=min_duration,
                max_duration=max_duration,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
            )
            for c in tempo_clusters
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed.append({
                    "cluster_id": str(tempo_clusters[i]["id"]),
                    "cluster_name": tempo_clusters[i]["name"],
                    "status": "ERROR",
                    "error": str(result),
                    "traces": [],
                })
            else:
                processed.append(result)

        return processed

    async def get_trace(
        self,
        trace_id: str,
        cluster_id: str | None = None,
    ) -> dict[str, Any]:
        """Get a specific trace by ID.

        If cluster_id is not specified, searches all clusters.

        Args:
            trace_id: Trace ID
            cluster_id: Optional specific cluster

        Returns:
            Trace result from first cluster that has it
        """
        if cluster_id:
            cluster = await self.cluster_registry.get_cluster(cluster_id)
            if not cluster:
                return {
                    "cluster_id": cluster_id,
                    "cluster_name": "unknown",
                    "status": "ERROR",
                    "error": "Cluster not found",
                    "trace": None,
                }
            return await self.collector.get_trace(cluster, trace_id)

        # Search all clusters for the trace
        clusters = await self.cluster_registry.list_online_clusters()
        tempo_clusters = [
            c for c in clusters
            if c.get("endpoints", {}).get("tempo_url")
        ]

        if not tempo_clusters:
            return {
                "cluster_id": "all",
                "cluster_name": "N/A",
                "status": "ERROR",
                "error": "No clusters with Tempo configured",
                "trace": None,
            }

        # Try each cluster until we find the trace
        for cluster in tempo_clusters:
            result = await self.collector.get_trace(cluster, trace_id)
            if result.get("status") == "SUCCESS":
                return result

        # Not found in any cluster
        return {
            "cluster_id": "all",
            "cluster_name": "N/A",
            "status": "NOT_FOUND",
            "error": f"Trace {trace_id} not found in any cluster",
            "trace": None,
        }

    async def get_services(self, cluster_id: str | None = None) -> list[str]:
        """Get list of services with traces.

        Args:
            cluster_id: Optional specific cluster

        Returns:
            List of service names (merged from all clusters)
        """
        if cluster_id:
            cluster = await self.cluster_registry.get_cluster(cluster_id)
            if not cluster:
                return []
            clusters = [cluster]
        else:
            clusters = await self.cluster_registry.list_online_clusters()

        tempo_clusters = [
            c for c in clusters
            if c.get("endpoints", {}).get("tempo_url")
        ]

        if not tempo_clusters:
            return []

        tasks = [self.collector.get_services(c) for c in tempo_clusters]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge services from all clusters
        all_services: set[str] = set()
        for result in results:
            if isinstance(result, list):
                all_services.update(result)

        return sorted(all_services)

    async def get_operations(
        self,
        service_name: str,
        cluster_id: str | None = None,
    ) -> list[str]:
        """Get operations for a service.

        Args:
            service_name: Service name
            cluster_id: Optional specific cluster

        Returns:
            List of operation names (merged from all clusters)
        """
        if cluster_id:
            cluster = await self.cluster_registry.get_cluster(cluster_id)
            if not cluster:
                return []
            clusters = [cluster]
        else:
            clusters = await self.cluster_registry.list_online_clusters()

        tempo_clusters = [
            c for c in clusters
            if c.get("endpoints", {}).get("tempo_url")
        ]

        if not tempo_clusters:
            return []

        tasks = [
            self.collector.get_operations(c, service_name)
            for c in tempo_clusters
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge operations from all clusters
        all_ops: set[str] = set()
        for result in results:
            if isinstance(result, list):
                all_ops.update(result)

        return sorted(all_ops)

    async def get_service_graph(
        self,
        cluster_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Get service dependency graph.

        Args:
            cluster_id: Optional specific cluster
            start_time: Optional start time
            end_time: Optional end time

        Returns:
            Service graph with nodes and edges
        """
        if cluster_id:
            cluster = await self.cluster_registry.get_cluster(cluster_id)
            if not cluster:
                return {"nodes": [], "edges": []}
            return await self.collector.get_service_graph(
                cluster, start_time, end_time
            )

        # Merge graphs from all clusters
        clusters = await self.cluster_registry.list_online_clusters()
        tempo_clusters = [
            c for c in clusters
            if c.get("endpoints", {}).get("tempo_url")
        ]

        if not tempo_clusters:
            return {"nodes": [], "edges": []}

        tasks = [
            self.collector.get_service_graph(c, start_time, end_time)
            for c in tempo_clusters
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge all graphs
        all_nodes: dict[str, dict] = {}
        all_edges: dict[tuple[str, str], int] = {}

        for result in results:
            if isinstance(result, dict):
                for node in result.get("nodes", []):
                    node_id = node.get("id")
                    if node_id:
                        all_nodes[node_id] = node
                for edge in result.get("edges", []):
                    key = (edge.get("source"), edge.get("target"))
                    current_weight = all_edges.get(key, 0)
                    all_edges[key] = current_weight + edge.get("weight", 1)

        return {
            "nodes": list(all_nodes.values()),
            "edges": [
                {"source": src, "target": tgt, "weight": weight}
                for (src, tgt), weight in all_edges.items()
            ],
        }

    async def close(self):
        """Close service resources."""
        await self.collector.close()
        await self.cluster_registry.close()
