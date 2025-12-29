"""CNF service for CNF telemetry collection.

Spec Reference: specs/03-observability-collector.md Section 5.6
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from shared.observability import get_logger
from shared.redis_client import RedisClient

from ..clients.cluster_registry import ClusterRegistryClient
from ..collectors.cnf_collector import CNFCollector

logger = get_logger(__name__)


class CNFService:
    """Service for CNF telemetry.

    Spec Reference: specs/03-observability-collector.md Section 5.6

    Provides federated access to CNF workload information, PTP status,
    SR-IOV configuration, and DPDK statistics across clusters.
    """

    CACHE_TTL = 10  # 10 seconds cache

    def __init__(
        self,
        cluster_registry: ClusterRegistryClient,
        redis: RedisClient,
    ):
        self.cluster_registry = cluster_registry
        self.redis = redis
        self.cnf_collector = CNFCollector()

    async def get_workloads(
        self,
        cluster_ids: list[UUID] | None = None,
        workload_type: str | None = None,
    ) -> dict[str, Any]:
        """Get CNF workloads from clusters.

        Spec Reference: specs/03-observability-collector.md Section 5.6

        Args:
            cluster_ids: Optional list of cluster IDs to query
            workload_type: Optional filter by CNF type (vDU, vCU, UPF, etc.)

        Returns:
            Dictionary with workloads list and metadata
        """
        clusters = await self._get_cnf_clusters(cluster_ids)

        # Query clusters in parallel
        tasks = [
            self._get_cluster_workloads(cluster) for cluster in clusters
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        workloads = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning("Failed to get workloads from cluster", error=str(result))
                continue
            workloads.extend(result)

        # Filter by type if specified
        if workload_type:
            workloads = [
                w for w in workloads
                if w.get("type", "").lower() == workload_type.lower()
            ]

        return {
            "workloads": workloads,
            "total": len(workloads),
            "clusters_queried": len(clusters),
        }

    async def get_ptp_status(
        self,
        cluster_ids: list[UUID] | None = None,
    ) -> dict[str, Any]:
        """Get PTP synchronization status from clusters.

        Spec Reference: specs/03-observability-collector.md Section 5.6

        Returns:
            Dictionary with PTP status list and summary
        """
        clusters = await self._get_ptp_clusters(cluster_ids)

        tasks = [
            self._get_cluster_ptp_status(cluster) for cluster in clusters
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        statuses = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning("Failed to get PTP status", error=str(result))
                continue
            statuses.extend(result)

        # Calculate summary
        locked_count = sum(1 for s in statuses if s.get("state") == "LOCKED")
        freerun_count = sum(1 for s in statuses if s.get("state") == "FREERUN")
        avg_offset = (
            sum(abs(s.get("offset_ns", 0)) for s in statuses) / len(statuses)
            if statuses
            else 0
        )

        return {
            "statuses": statuses,
            "total": len(statuses),
            "summary": {
                "locked": locked_count,
                "freerun": freerun_count,
                "avg_offset_ns": round(avg_offset, 2),
            },
            "clusters_queried": len(clusters),
        }

    async def get_sriov_status(
        self,
        cluster_ids: list[UUID] | None = None,
    ) -> dict[str, Any]:
        """Get SR-IOV VF allocation status from clusters.

        Spec Reference: specs/03-observability-collector.md Section 5.6

        Returns:
            Dictionary with SR-IOV status list and summary
        """
        clusters = await self._get_sriov_clusters(cluster_ids)

        tasks = [
            self._get_cluster_sriov_status(cluster) for cluster in clusters
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        statuses = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning("Failed to get SR-IOV status", error=str(result))
                continue
            statuses.extend(result)

        # Calculate summary
        total_vfs = sum(s.get("total_vfs", 0) for s in statuses)
        configured_vfs = sum(s.get("configured_vfs", 0) for s in statuses)

        return {
            "statuses": statuses,
            "total": len(statuses),
            "summary": {
                "total_vfs_capacity": total_vfs,
                "configured_vfs": configured_vfs,
                "utilization_percent": (
                    round(configured_vfs / total_vfs * 100, 1)
                    if total_vfs > 0
                    else 0
                ),
            },
            "clusters_queried": len(clusters),
        }

    async def get_dpdk_stats(
        self,
        cluster_id: UUID,
        namespace: str,
        pod_name: str,
    ) -> dict[str, Any] | None:
        """Get DPDK statistics for a specific pod.

        Spec Reference: specs/03-observability-collector.md Section 5.6

        Args:
            cluster_id: Cluster ID
            namespace: Pod namespace
            pod_name: Pod name

        Returns:
            DPDK statistics or None if not available
        """
        # Check cache first
        cache_key = f"{cluster_id}:{namespace}:{pod_name}"
        cached = await self.redis.cache_get_json("dpdk", cache_key)
        if cached:
            return cached

        cluster = await self.cluster_registry.get_cluster(cluster_id)
        if not cluster:
            return None

        try:
            stats = await self.cnf_collector.get_dpdk_stats(
                cluster, namespace, pod_name
            )

            if stats:
                await self.redis.cache_set("dpdk", cache_key, stats, self.CACHE_TTL)

            return stats

        except Exception as e:
            logger.warning(
                "Failed to get DPDK stats",
                cluster_id=str(cluster_id),
                pod_name=pod_name,
                error=str(e),
            )
            return None

    async def get_summary(self) -> dict[str, Any]:
        """Get fleet-wide CNF summary.

        Returns summary of CNF workloads, PTP status, and SR-IOV usage.
        """
        # Get all data in parallel
        workloads_task = self.get_workloads()
        ptp_task = self.get_ptp_status()
        sriov_task = self.get_sriov_status()

        workloads_result, ptp_result, sriov_result = await asyncio.gather(
            workloads_task, ptp_task, sriov_task,
            return_exceptions=True,
        )

        # Process workloads
        workloads = (
            workloads_result.get("workloads", [])
            if isinstance(workloads_result, dict)
            else []
        )
        workload_types: dict[str, int] = {}
        for w in workloads:
            wtype = w.get("type", "Unknown")
            workload_types[wtype] = workload_types.get(wtype, 0) + 1

        # Process PTP
        ptp_summary = (
            ptp_result.get("summary", {})
            if isinstance(ptp_result, dict)
            else {}
        )

        # Process SR-IOV
        sriov_summary = (
            sriov_result.get("summary", {})
            if isinstance(sriov_result, dict)
            else {}
        )

        return {
            "workloads": {
                "total": len(workloads),
                "by_type": workload_types,
            },
            "ptp": ptp_summary,
            "sriov": sriov_summary,
        }

    # ==========================================================================
    # Internal helpers
    # ==========================================================================

    async def _get_cnf_clusters(
        self, cluster_ids: list[UUID] | None = None
    ) -> list[dict]:
        """Get clusters with CNF capability."""
        try:
            if cluster_ids:
                clusters = []
                for cid in cluster_ids:
                    cluster = await self.cluster_registry.get_cluster(cid)
                    if cluster and cluster.get("capabilities", {}).get("cnf_types"):
                        clusters.append(cluster)
                return clusters
            else:
                all_clusters = await self.cluster_registry.list_online_clusters()
                return [
                    c for c in all_clusters
                    if c.get("capabilities", {}).get("cnf_types")
                ]
        except Exception as e:
            logger.error("Failed to get CNF clusters", error=str(e))
            return []

    async def _get_ptp_clusters(
        self, cluster_ids: list[UUID] | None = None
    ) -> list[dict]:
        """Get clusters with PTP capability."""
        try:
            if cluster_ids:
                clusters = []
                for cid in cluster_ids:
                    cluster = await self.cluster_registry.get_cluster(cid)
                    if cluster and cluster.get("capabilities", {}).get("has_ptp"):
                        clusters.append(cluster)
                return clusters
            else:
                all_clusters = await self.cluster_registry.list_online_clusters()
                return [
                    c for c in all_clusters
                    if c.get("capabilities", {}).get("has_ptp")
                ]
        except Exception as e:
            logger.error("Failed to get PTP clusters", error=str(e))
            return []

    async def _get_sriov_clusters(
        self, cluster_ids: list[UUID] | None = None
    ) -> list[dict]:
        """Get clusters with SR-IOV capability."""
        try:
            if cluster_ids:
                clusters = []
                for cid in cluster_ids:
                    cluster = await self.cluster_registry.get_cluster(cid)
                    if cluster and cluster.get("capabilities", {}).get("has_sriov"):
                        clusters.append(cluster)
                return clusters
            else:
                all_clusters = await self.cluster_registry.list_online_clusters()
                return [
                    c for c in all_clusters
                    if c.get("capabilities", {}).get("has_sriov")
                ]
        except Exception as e:
            logger.error("Failed to get SR-IOV clusters", error=str(e))
            return []

    async def _get_cluster_workloads(self, cluster: dict) -> list[dict]:
        """Get CNF workloads from a specific cluster."""
        try:
            return await self.cnf_collector.get_cnf_workloads(cluster)
        except Exception as e:
            logger.warning(
                "Failed to get CNF workloads",
                cluster_id=cluster.get("id"),
                error=str(e),
            )
            return []

    async def _get_cluster_ptp_status(self, cluster: dict) -> list[dict]:
        """Get PTP status from a specific cluster."""
        try:
            return await self.cnf_collector.get_ptp_status(cluster)
        except Exception as e:
            logger.warning(
                "Failed to get PTP status",
                cluster_id=cluster.get("id"),
                error=str(e),
            )
            return []

    async def _get_cluster_sriov_status(self, cluster: dict) -> list[dict]:
        """Get SR-IOV status from a specific cluster."""
        try:
            return await self.cnf_collector.get_sriov_status(cluster)
        except Exception as e:
            logger.warning(
                "Failed to get SR-IOV status",
                cluster_id=cluster.get("id"),
                error=str(e),
            )
            return []
