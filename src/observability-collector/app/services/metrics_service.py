"""Metrics service for federated PromQL queries.

Spec Reference: specs/03-observability-collector.md Section 5.1
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from datetime import datetime
from typing import Any
from uuid import UUID

from shared.observability import get_logger
from shared.redis_client import RedisClient

from ..clients.cluster_registry import ClusterRegistryClient
from ..collectors.prometheus_collector import PrometheusCollector

logger = get_logger(__name__)


class MetricsService:
    """Service for federated metric queries.

    Spec Reference: specs/03-observability-collector.md Section 5.1
    """

    # Cache TTLs from spec Section 7.3
    INSTANT_QUERY_CACHE_TTL = 30  # seconds
    RANGE_QUERY_SHORT_CACHE_TTL = 60  # for queries < 1h
    RANGE_QUERY_LONG_CACHE_TTL = 300  # for queries > 1h
    LABELS_CACHE_TTL = 300  # 5 minutes

    def __init__(
        self,
        cluster_registry: ClusterRegistryClient,
        redis: RedisClient,
    ):
        self.cluster_registry = cluster_registry
        self.redis = redis
        self.prometheus_collector = PrometheusCollector()

    async def query(
        self,
        query: str,
        cluster_ids: list[UUID] | None = None,
        time: datetime | None = None,
        timeout: int = 30,
    ) -> dict[str, Any]:
        """Execute instant PromQL query across clusters.

        Spec Reference: specs/03-observability-collector.md Section 5.1
        """
        start_time = asyncio.get_event_loop().time()

        # Get target clusters
        clusters = await self._get_target_clusters(cluster_ids)

        if not clusters:
            return {
                "results": [],
                "total_query_time_ms": 0,
                "clusters_queried": 0,
                "clusters_succeeded": 0,
            }

        # Execute queries in parallel
        tasks = []
        for cluster in clusters:
            task = self._query_cluster(cluster, query, time, timeout)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        processed_results = []
        succeeded = 0

        for cluster, result in zip(clusters, results):
            if isinstance(result, Exception):
                processed_results.append({
                    "cluster_id": str(cluster["id"]),
                    "cluster_name": cluster["name"],
                    "status": "ERROR",
                    "error": str(result),
                    "data": [],
                    "query_time_ms": 0,
                })
            else:
                processed_results.append(result)
                if result.get("status") == "SUCCESS":
                    succeeded += 1

        total_time = int((asyncio.get_event_loop().time() - start_time) * 1000)

        return {
            "results": processed_results,
            "total_query_time_ms": total_time,
            "clusters_queried": len(clusters),
            "clusters_succeeded": succeeded,
        }

    async def query_range(
        self,
        query: str,
        cluster_ids: list[UUID] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        step: str = "1m",
        timeout: int = 30,
    ) -> dict[str, Any]:
        """Execute range PromQL query across clusters.

        Spec Reference: specs/03-observability-collector.md Section 5.1
        """
        query_start = asyncio.get_event_loop().time()

        # Get target clusters
        clusters = await self._get_target_clusters(cluster_ids)

        if not clusters:
            return {
                "results": [],
                "total_query_time_ms": 0,
                "clusters_queried": 0,
                "clusters_succeeded": 0,
            }

        # Execute queries in parallel
        tasks = []
        for cluster in clusters:
            task = self._query_range_cluster(
                cluster, query, start_time, end_time, step, timeout
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        processed_results = []
        succeeded = 0

        for cluster, result in zip(clusters, results):
            if isinstance(result, Exception):
                processed_results.append({
                    "cluster_id": str(cluster["id"]),
                    "cluster_name": cluster["name"],
                    "status": "ERROR",
                    "error": str(result),
                    "data": [],
                    "query_time_ms": 0,
                })
            else:
                processed_results.append(result)
                if result.get("status") == "SUCCESS":
                    succeeded += 1

        total_time = int((asyncio.get_event_loop().time() - query_start) * 1000)

        return {
            "results": processed_results,
            "total_query_time_ms": total_time,
            "clusters_queried": len(clusters),
            "clusters_succeeded": succeeded,
        }

    async def get_labels(
        self,
        cluster_ids: list[UUID] | None = None,
    ) -> dict[str, list[str]]:
        """Get label names from clusters.

        Spec Reference: specs/03-observability-collector.md Section 5.1
        """
        clusters = await self._get_target_clusters(cluster_ids)

        labels_by_cluster = {}

        for cluster in clusters:
            cache_key = f"labels:{cluster['id']}"

            # Check cache
            cached = await self.redis.cache_get_json("metrics", cache_key)
            if cached:
                labels_by_cluster[cluster["name"]] = cached
                continue

            # Fetch from Prometheus
            try:
                labels = await self.prometheus_collector.get_labels(cluster)
                labels_by_cluster[cluster["name"]] = labels

                # Cache result
                await self.redis.cache_set("metrics", cache_key, labels, self.LABELS_CACHE_TTL)
            except Exception as e:
                logger.warning(
                    "Failed to get labels from cluster",
                    cluster_id=cluster["id"],
                    error=str(e),
                )
                labels_by_cluster[cluster["name"]] = []

        return labels_by_cluster

    async def _get_target_clusters(
        self, cluster_ids: list[UUID] | None = None
    ) -> list[dict]:
        """Get target clusters for query."""
        try:
            if cluster_ids:
                clusters = []
                for cid in cluster_ids:
                    cluster = await self.cluster_registry.get_cluster(cid)
                    if cluster:
                        clusters.append(cluster)
                return clusters
            else:
                return await self.cluster_registry.list_online_clusters()
        except Exception as e:
            logger.error("Failed to get clusters", error=str(e))
            return []

    async def _query_cluster(
        self,
        cluster: dict,
        query: str,
        time: datetime | None,
        timeout: int,
    ) -> dict[str, Any]:
        """Execute instant query on single cluster."""
        start = asyncio.get_event_loop().time()

        # Check cache
        cache_key = self._get_cache_key("instant", query, cluster["id"], time)
        cached = await self.redis.cache_get_json("metrics", cache_key)
        if cached:
            return cached

        try:
            result = await self.prometheus_collector.query(
                cluster=cluster,
                query=query,
                time=time,
                timeout=timeout,
            )

            query_time = int((asyncio.get_event_loop().time() - start) * 1000)
            result["query_time_ms"] = query_time

            # Cache successful results
            if result.get("status") == "SUCCESS":
                await self.redis.cache_set(
                    "metrics", cache_key, result, self.INSTANT_QUERY_CACHE_TTL
                )

            return result

        except Exception as e:
            query_time = int((asyncio.get_event_loop().time() - start) * 1000)
            return {
                "cluster_id": str(cluster["id"]),
                "cluster_name": cluster["name"],
                "status": "ERROR",
                "error": str(e),
                "data": [],
                "query_time_ms": query_time,
            }

    async def _query_range_cluster(
        self,
        cluster: dict,
        query: str,
        start_time: datetime,
        end_time: datetime,
        step: str,
        timeout: int,
    ) -> dict[str, Any]:
        """Execute range query on single cluster."""
        start = asyncio.get_event_loop().time()

        # Determine cache TTL based on range duration
        duration = (end_time - start_time).total_seconds()
        cache_ttl = (
            self.RANGE_QUERY_SHORT_CACHE_TTL
            if duration < 3600
            else self.RANGE_QUERY_LONG_CACHE_TTL
        )

        # Check cache
        cache_key = self._get_range_cache_key(
            query, cluster["id"], start_time, end_time, step
        )
        cached = await self.redis.cache_get_json("metrics", cache_key)
        if cached:
            return cached

        try:
            result = await self.prometheus_collector.query_range(
                cluster=cluster,
                query=query,
                start_time=start_time,
                end_time=end_time,
                step=step,
                timeout=timeout,
            )

            query_time = int((asyncio.get_event_loop().time() - start) * 1000)
            result["query_time_ms"] = query_time

            # Cache successful results
            if result.get("status") == "SUCCESS":
                await self.redis.cache_set("metrics", cache_key, result, cache_ttl)

            return result

        except Exception as e:
            query_time = int((asyncio.get_event_loop().time() - start) * 1000)
            return {
                "cluster_id": str(cluster["id"]),
                "cluster_name": cluster["name"],
                "status": "ERROR",
                "error": str(e),
                "data": [],
                "query_time_ms": query_time,
            }

    def _get_cache_key(
        self,
        query_type: str,
        query: str,
        cluster_id: str,
        time: datetime | None,
    ) -> str:
        """Generate cache key for instant query."""
        query_hash = hashlib.md5(query.encode()).hexdigest()[:16]
        time_str = time.isoformat() if time else "now"
        return f"metrics:{query_type}:{query_hash}:{cluster_id}:{time_str}"

    def _get_range_cache_key(
        self,
        query: str,
        cluster_id: str,
        start_time: datetime,
        end_time: datetime,
        step: str,
    ) -> str:
        """Generate cache key for range query."""
        query_hash = hashlib.md5(query.encode()).hexdigest()[:16]
        return (
            f"metrics:range:{query_hash}:{cluster_id}:"
            f"{start_time.isoformat()}:{end_time.isoformat()}:{step}"
        )
