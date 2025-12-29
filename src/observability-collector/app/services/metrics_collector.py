"""Metrics Collector Service.

Spec Reference: specs/03-observability-collector.md Section 3

Coordinates metric collection across multiple clusters with:
- Authentication handling
- Query caching
- Concurrent cluster queries
- Error handling and retries
"""

import asyncio

from app.clients.prometheus import PrometheusClient, create_prometheus_client
from app.services.query_cache import query_cache
from shared.models import MetricQuery, MetricResult, MetricResultStatus, MetricResultType
from shared.observability import get_logger

logger = get_logger(__name__)


class MetricsCollector:
    """Collects metrics from Prometheus instances across clusters."""

    def __init__(self):
        self._clients: dict[str, PrometheusClient] = {}
        self._cache_enabled = True
        self._cache_ttl = 30  # seconds

    async def get_client(
        self,
        cluster_id: str,
        prometheus_url: str,
        token: str,
        skip_tls_verify: bool = False,
    ) -> PrometheusClient:
        """Get or create Prometheus client for cluster."""
        cache_key = f"{cluster_id}:{prometheus_url}"

        if cache_key not in self._clients:
            self._clients[cache_key] = await create_prometheus_client(
                cluster_id=cluster_id,
                prometheus_url=prometheus_url,
                cluster_token=token,
                skip_tls_verify=skip_tls_verify,
            )

        return self._clients[cache_key]

    async def query(
        self,
        cluster_id: str,
        prometheus_url: str,
        token: str,
        query: MetricQuery,
        skip_tls_verify: bool = False,
    ) -> MetricResult:
        """Execute metric query against a cluster.

        Args:
            cluster_id: Cluster identifier
            prometheus_url: Prometheus/Thanos URL
            token: Bearer token for authentication
            query: Metric query specification
            skip_tls_verify: Skip TLS verification

        Returns:
            MetricResult with query results
        """
        # Check cache first
        if self._cache_enabled:
            cached = await query_cache.get(
                cluster_id=cluster_id,
                query=query.query,
                start=query.start,
                end=query.end,
                step=query.step,
            )

            if cached:
                return MetricResult(**cached)

        # Get client
        client = await self.get_client(
            cluster_id, prometheus_url, token, skip_tls_verify
        )

        # Execute query
        if query.start and query.end:
            result = await client.query_range(
                promql=query.query,
                start=query.start,
                end=query.end,
                step=query.step or "1m",
            )
        else:
            result = await client.query(
                promql=query.query,
                time=query.time,
            )

        # Cache successful results
        if result.status == MetricResultStatus.SUCCESS and self._cache_enabled:
            await query_cache.set(
                cluster_id=cluster_id,
                query=query.query,
                result=result.model_dump(),
                start=query.start,
                end=query.end,
                step=query.step,
                ttl_seconds=self._cache_ttl,
            )

        return result

    async def query_multiple_clusters(
        self,
        clusters: list[dict],
        query: MetricQuery,
    ) -> dict[str, MetricResult]:
        """Query multiple clusters concurrently.

        Args:
            clusters: List of cluster configs with id, prometheus_url, token
            query: Metric query to execute on all clusters

        Returns:
            Dict mapping cluster_id to MetricResult
        """
        async def query_cluster(cluster: dict) -> tuple[str, MetricResult]:
            result = await self.query(
                cluster_id=cluster["id"],
                prometheus_url=cluster["prometheus_url"],
                token=cluster["token"],
                query=query,
                skip_tls_verify=cluster.get("skip_tls_verify", False),
            )
            return cluster["id"], result

        # Execute all queries concurrently
        tasks = [query_cluster(c) for c in clusters]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Build result dict
        result_map = {}
        for i, result in enumerate(results):
            cluster_id = clusters[i]["id"]

            if isinstance(result, Exception):
                logger.error(
                    "Cluster query failed",
                    cluster_id=cluster_id,
                    error=str(result),
                )
                result_map[cluster_id] = MetricResult(
                    status=MetricResultStatus.ERROR,
                    error=str(result),
                    result_type=MetricResultType.VECTOR,
                    result=[],
                )
            else:
                result_map[result[0]] = result[1]

        return result_map

    async def check_cluster_health(
        self,
        cluster_id: str,
        prometheus_url: str,
        token: str,
        skip_tls_verify: bool = False,
    ) -> bool:
        """Check if Prometheus is healthy on a cluster."""
        client = await self.get_client(
            cluster_id, prometheus_url, token, skip_tls_verify
        )
        return await client.check_health()

    async def close(self):
        """Close all clients."""
        for client in self._clients.values():
            await client.close()
        self._clients.clear()

        await query_cache.close()


# Singleton instance
metrics_collector = MetricsCollector()
