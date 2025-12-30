"""Logs Service for federated log queries.

Spec Reference: specs/03-observability-collector.md Section 4.3
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from app.clients.cluster_registry import ClusterRegistryClient
from app.collectors.loki_collector import LokiCollector
from shared.config import get_settings
from shared.observability import get_logger

logger = get_logger(__name__)


class LogsService:
    """Service for federated log queries across clusters.

    Spec Reference: specs/03-observability-collector.md Section 4.3
    """

    def __init__(self):
        self.settings = get_settings()
        self.cluster_registry = ClusterRegistryClient(
            base_url=self.settings.services.cluster_registry_url
        )
        self.collector = LokiCollector()

    async def query(
        self,
        query: str,
        cluster_id: str | None = None,
        limit: int = 100,
        time: datetime | None = None,
        direction: str = "backward",
    ) -> list[dict[str, Any]]:
        """Execute instant LogQL query across clusters.

        Args:
            query: LogQL query string
            cluster_id: Optional specific cluster
            limit: Maximum entries per cluster
            time: Evaluation timestamp
            direction: Log direction

        Returns:
            List of results per cluster
        """
        if cluster_id:
            cluster = await self.cluster_registry.get_cluster(cluster_id)
            if not cluster:
                return [
                    {
                        "cluster_id": cluster_id,
                        "cluster_name": "unknown",
                        "status": "ERROR",
                        "error": "Cluster not found",
                        "result_type": None,
                        "data": [],
                    }
                ]
            clusters = [cluster]
        else:
            clusters = await self.cluster_registry.list_online_clusters()

        # Filter to clusters with Loki configured
        loki_clusters = [c for c in clusters if c.get("endpoints", {}).get("loki_url")]

        if not loki_clusters:
            return [
                {
                    "cluster_id": cluster_id or "all",
                    "cluster_name": "N/A",
                    "status": "ERROR",
                    "error": "No clusters with Loki configured",
                    "result_type": None,
                    "data": [],
                }
            ]

        # Execute queries concurrently
        tasks = [
            self.collector.query(
                cluster=c,
                query=query,
                limit=limit,
                time=time,
                direction=direction,
            )
            for c in loki_clusters
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        processed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed.append(
                    {
                        "cluster_id": str(loki_clusters[i]["id"]),
                        "cluster_name": loki_clusters[i]["name"],
                        "status": "ERROR",
                        "error": str(result),
                        "result_type": None,
                        "data": [],
                    }
                )
            else:
                processed.append(result)

        return processed

    async def query_range(
        self,
        query: str,
        start_time: datetime,
        end_time: datetime,
        cluster_id: str | None = None,
        limit: int = 1000,
        step: str | None = None,
        direction: str = "backward",
    ) -> list[dict[str, Any]]:
        """Execute range LogQL query across clusters.

        Args:
            query: LogQL query string
            start_time: Query start time
            end_time: Query end time
            cluster_id: Optional specific cluster
            limit: Maximum entries
            step: Query step for metric queries
            direction: Log direction

        Returns:
            List of results per cluster
        """
        if cluster_id:
            cluster = await self.cluster_registry.get_cluster(cluster_id)
            if not cluster:
                return [
                    {
                        "cluster_id": cluster_id,
                        "cluster_name": "unknown",
                        "status": "ERROR",
                        "error": "Cluster not found",
                        "result_type": None,
                        "data": [],
                    }
                ]
            clusters = [cluster]
        else:
            clusters = await self.cluster_registry.list_online_clusters()

        loki_clusters = [c for c in clusters if c.get("endpoints", {}).get("loki_url")]

        if not loki_clusters:
            return [
                {
                    "cluster_id": cluster_id or "all",
                    "cluster_name": "N/A",
                    "status": "ERROR",
                    "error": "No clusters with Loki configured",
                    "result_type": None,
                    "data": [],
                }
            ]

        tasks = [
            self.collector.query_range(
                cluster=c,
                query=query,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
                step=step,
                direction=direction,
            )
            for c in loki_clusters
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed.append(
                    {
                        "cluster_id": str(loki_clusters[i]["id"]),
                        "cluster_name": loki_clusters[i]["name"],
                        "status": "ERROR",
                        "error": str(result),
                        "result_type": None,
                        "data": [],
                    }
                )
            else:
                processed.append(result)

        return processed

    async def get_labels(self, cluster_id: str | None = None) -> list[str]:
        """Get available log labels.

        Args:
            cluster_id: Optional specific cluster

        Returns:
            List of label names (merged from all clusters)
        """
        if cluster_id:
            cluster = await self.cluster_registry.get_cluster(cluster_id)
            if not cluster:
                return []
            clusters = [cluster]
        else:
            clusters = await self.cluster_registry.list_online_clusters()

        loki_clusters = [c for c in clusters if c.get("endpoints", {}).get("loki_url")]

        if not loki_clusters:
            return []

        tasks = [self.collector.get_labels(c) for c in loki_clusters]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge labels from all clusters
        all_labels: set[str] = set()
        for result in results:
            if isinstance(result, list):
                all_labels.update(result)

        return sorted(all_labels)

    async def get_label_values(
        self,
        label: str,
        cluster_id: str | None = None,
    ) -> list[str]:
        """Get values for a specific label.

        Args:
            label: Label name
            cluster_id: Optional specific cluster

        Returns:
            List of label values (merged from all clusters)
        """
        if cluster_id:
            cluster = await self.cluster_registry.get_cluster(cluster_id)
            if not cluster:
                return []
            clusters = [cluster]
        else:
            clusters = await self.cluster_registry.list_online_clusters()

        loki_clusters = [c for c in clusters if c.get("endpoints", {}).get("loki_url")]

        if not loki_clusters:
            return []

        tasks = [self.collector.get_label_values(c, label) for c in loki_clusters]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge values from all clusters
        all_values: set[str] = set()
        for result in results:
            if isinstance(result, list):
                all_values.update(result)

        return sorted(all_values)

    async def close(self):
        """Close service resources."""
        await self.collector.close()
        await self.cluster_registry.close()
