"""GPU service for GPU telemetry collection.

Spec Reference: specs/03-observability-collector.md Section 5.5
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from shared.observability import get_logger
from shared.redis_client import RedisClient

from ..clients.cluster_registry import ClusterRegistryClient
from ..collectors.gpu_collector import GPUCollector

logger = get_logger(__name__)


class GPUService:
    """Service for GPU telemetry.

    Spec Reference: specs/03-observability-collector.md Section 5.5
    """

    GPU_CACHE_TTL = 5  # 5 seconds as per spec

    def __init__(
        self,
        cluster_registry: ClusterRegistryClient,
        redis: RedisClient,
    ):
        self.cluster_registry = cluster_registry
        self.redis = redis
        self.gpu_collector = GPUCollector()

    async def get_nodes(
        self,
        cluster_ids: list[UUID] | None = None,
    ) -> dict[str, Any]:
        """Get GPU nodes from clusters.

        Spec Reference: specs/03-observability-collector.md Section 5.5
        """
        # Get target clusters with GPU capability
        clusters = await self._get_gpu_clusters(cluster_ids)

        nodes = []
        for cluster in clusters:
            cluster_nodes = await self._get_cluster_gpu_nodes(cluster)
            nodes.extend(cluster_nodes)

        return {
            "nodes": nodes,
            "total": len(nodes),
        }

    async def get_node_details(
        self,
        cluster_id: UUID,
        node_name: str,
    ) -> dict[str, Any] | None:
        """Get detailed GPU info for specific node.

        Spec Reference: specs/03-observability-collector.md Section 5.5
        """
        # Check cache first
        cache_key = f"{cluster_id}:{node_name}"
        cached = await self.redis.cache_get_json("gpu", cache_key)
        if cached:
            return cached

        # Get cluster info
        cluster = await self.cluster_registry.get_cluster(cluster_id)
        if not cluster:
            return None

        # Collect from node
        try:
            node_data = await self.gpu_collector.collect_from_node(cluster, node_name)

            if node_data:
                # Cache result
                await self.redis.cache_set("gpu", cache_key, node_data, self.GPU_CACHE_TTL)

            return node_data

        except Exception as e:
            logger.warning(
                "Failed to collect GPU data from node",
                cluster_id=str(cluster_id),
                node_name=node_name,
                error=str(e),
            )
            return None

    async def get_summary(self) -> dict[str, Any]:
        """Get fleet-wide GPU summary.

        Spec Reference: specs/03-observability-collector.md Section 5.5
        """
        # Get all GPU nodes
        result = await self.get_nodes()
        nodes = result.get("nodes", [])

        total_gpus = 0
        total_memory_mb = 0
        used_memory_mb = 0
        total_utilization = 0
        gpu_types: dict[str, int] = {}
        clusters_with_gpu = set()

        for node in nodes:
            clusters_with_gpu.add(node.get("cluster_id"))

            for gpu in node.get("gpus", []):
                total_gpus += 1
                total_memory_mb += gpu.get("memory_total_mb", 0)
                used_memory_mb += gpu.get("memory_used_mb", 0)
                total_utilization += gpu.get("utilization_gpu_percent", 0)

                gpu_name = gpu.get("name", "Unknown")
                gpu_types[gpu_name] = gpu_types.get(gpu_name, 0) + 1

        avg_utilization = total_utilization / total_gpus if total_gpus > 0 else 0

        return {
            "total_nodes": len(nodes),
            "total_gpus": total_gpus,
            "total_memory_gb": round(total_memory_mb / 1024, 2),
            "used_memory_gb": round(used_memory_mb / 1024, 2),
            "avg_utilization_percent": round(avg_utilization, 1),
            "gpu_types": gpu_types,
            "clusters_with_gpu": len(clusters_with_gpu),
        }

    async def get_processes(
        self,
        cluster_ids: list[UUID] | None = None,
    ) -> list[dict[str, Any]]:
        """Get running GPU processes.

        Spec Reference: specs/03-observability-collector.md Section 5.5
        """
        # Get all GPU nodes
        result = await self.get_nodes(cluster_ids)
        nodes = result.get("nodes", [])

        processes = []
        for node in nodes:
            for gpu in node.get("gpus", []):
                for proc in gpu.get("processes", []):
                    processes.append({
                        "cluster_id": node.get("cluster_id"),
                        "cluster_name": node.get("cluster_name"),
                        "node_name": node.get("node_name"),
                        "gpu_index": gpu.get("index"),
                        "gpu_name": gpu.get("name"),
                        **proc,
                    })

        return processes

    async def _get_gpu_clusters(
        self, cluster_ids: list[UUID] | None = None
    ) -> list[dict]:
        """Get clusters with GPU capability."""
        try:
            if cluster_ids:
                clusters = []
                for cid in cluster_ids:
                    cluster = await self.cluster_registry.get_cluster(cid)
                    if cluster and cluster.get("capabilities", {}).get("has_gpu_nodes"):
                        clusters.append(cluster)
                return clusters
            else:
                # Get all clusters with GPU
                all_clusters = await self.cluster_registry.list_online_clusters()
                return [
                    c
                    for c in all_clusters
                    if c.get("capabilities", {}).get("has_gpu_nodes")
                ]
        except Exception as e:
            logger.error("Failed to get GPU clusters", error=str(e))
            return []

    async def _get_cluster_gpu_nodes(self, cluster: dict) -> list[dict]:
        """Get GPU nodes from a specific cluster."""
        try:
            # In a real implementation, this would query the K8s API
            # to list nodes with GPU labels
            nodes = await self.gpu_collector.list_gpu_nodes(cluster)
            return nodes
        except Exception as e:
            logger.warning(
                "Failed to get GPU nodes from cluster",
                cluster_id=cluster.get("id"),
                error=str(e),
            )
            return []
