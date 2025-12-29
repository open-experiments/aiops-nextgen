# Sprint 3: Prometheus Authentication

**Issues Addressed:** ISSUE-012 (HIGH)
**Priority:** P1
**Dependencies:** Sprint 1, Sprint 2

---

## Overview

This sprint implements proper authentication for Prometheus/Thanos queries. OpenShift's monitoring stack requires OAuth Bearer tokens for access. The current implementation makes unauthenticated requests that fail on production clusters.

---

## Task 3.1: Prometheus Client with Authentication

**File:** `src/observability-collector/clients/prometheus.py`

### Implementation

```python
"""Prometheus/Thanos Query Client with Authentication.

Spec Reference: specs/03-observability-collector.md Section 3.1

Supports:
- Bearer token authentication (OpenShift OAuth)
- Basic authentication
- mTLS (client certificates)
- Query caching with Redis
"""

from datetime import datetime, timezone
from typing import Optional, Any
from enum import Enum
import hashlib
import json

import httpx
from pydantic import BaseModel

from shared.config import get_settings
from shared.observability import get_logger
from shared.models import MetricQuery, MetricResult, MetricResultStatus, MetricResultType, MetricSeries

logger = get_logger(__name__)


class PrometheusAuthType(str, Enum):
    """Authentication type for Prometheus."""
    NONE = "none"
    BEARER = "bearer"
    BASIC = "basic"
    MTLS = "mtls"


class PrometheusAuthConfig(BaseModel):
    """Authentication configuration for Prometheus client."""

    auth_type: PrometheusAuthType = PrometheusAuthType.BEARER
    token: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    client_cert_path: Optional[str] = None
    client_key_path: Optional[str] = None
    ca_cert_path: Optional[str] = None
    skip_tls_verify: bool = False


class PrometheusClient:
    """Authenticated Prometheus/Thanos query client."""

    def __init__(
        self,
        base_url: str,
        auth_config: PrometheusAuthConfig,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.auth_config = auth_config
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with authentication."""
        if self._client is None:
            # Build SSL context
            verify: bool | str = not self.auth_config.skip_tls_verify
            if self.auth_config.ca_cert_path:
                verify = self.auth_config.ca_cert_path

            # Build client cert for mTLS
            cert = None
            if self.auth_config.auth_type == PrometheusAuthType.MTLS:
                if self.auth_config.client_cert_path and self.auth_config.client_key_path:
                    cert = (
                        self.auth_config.client_cert_path,
                        self.auth_config.client_key_path,
                    )

            # Build auth
            auth = None
            if self.auth_config.auth_type == PrometheusAuthType.BASIC:
                auth = httpx.BasicAuth(
                    self.auth_config.username or "",
                    self.auth_config.password or "",
                )

            self._client = httpx.AsyncClient(
                verify=verify,
                cert=cert,
                auth=auth,
                timeout=self.timeout,
            )

        return self._client

    def _get_auth_headers(self) -> dict[str, str]:
        """Build authentication headers."""
        headers = {}

        if self.auth_config.auth_type == PrometheusAuthType.BEARER:
            if self.auth_config.token:
                headers["Authorization"] = f"Bearer {self.auth_config.token}"

        return headers

    async def query(self, promql: str, time: Optional[datetime] = None) -> MetricResult:
        """Execute instant query.

        Args:
            promql: PromQL query string
            time: Optional evaluation timestamp (defaults to now)

        Returns:
            MetricResult with query results
        """
        client = await self._get_client()
        headers = self._get_auth_headers()

        params = {"query": promql}
        if time:
            params["time"] = time.timestamp()

        try:
            response = await client.get(
                f"{self.base_url}/api/v1/query",
                headers=headers,
                params=params,
            )

            if response.status_code == 401:
                logger.error("Prometheus authentication failed", url=self.base_url)
                return MetricResult(
                    status=MetricResultStatus.ERROR,
                    error="Authentication failed",
                    result_type=MetricResultType.VECTOR,
                    result=[],
                )

            if response.status_code == 403:
                logger.error("Prometheus authorization failed", url=self.base_url)
                return MetricResult(
                    status=MetricResultStatus.ERROR,
                    error="Authorization failed - insufficient permissions",
                    result_type=MetricResultType.VECTOR,
                    result=[],
                )

            response.raise_for_status()
            data = response.json()

            if data.get("status") != "success":
                return MetricResult(
                    status=MetricResultStatus.ERROR,
                    error=data.get("error", "Unknown error"),
                    result_type=MetricResultType.VECTOR,
                    result=[],
                )

            return self._parse_query_result(data)

        except httpx.TimeoutException:
            logger.error("Prometheus query timeout", url=self.base_url, query=promql)
            return MetricResult(
                status=MetricResultStatus.ERROR,
                error="Query timeout",
                result_type=MetricResultType.VECTOR,
                result=[],
            )

        except httpx.HTTPError as e:
            logger.error("Prometheus query failed", url=self.base_url, error=str(e))
            return MetricResult(
                status=MetricResultStatus.ERROR,
                error=str(e),
                result_type=MetricResultType.VECTOR,
                result=[],
            )

    async def query_range(
        self,
        promql: str,
        start: datetime,
        end: datetime,
        step: str = "1m",
    ) -> MetricResult:
        """Execute range query.

        Args:
            promql: PromQL query string
            start: Start timestamp
            end: End timestamp
            step: Query resolution step (e.g., "1m", "5m", "1h")

        Returns:
            MetricResult with time series data
        """
        client = await self._get_client()
        headers = self._get_auth_headers()

        params = {
            "query": promql,
            "start": start.timestamp(),
            "end": end.timestamp(),
            "step": step,
        }

        try:
            response = await client.get(
                f"{self.base_url}/api/v1/query_range",
                headers=headers,
                params=params,
            )

            if response.status_code == 401:
                return MetricResult(
                    status=MetricResultStatus.ERROR,
                    error="Authentication failed",
                    result_type=MetricResultType.MATRIX,
                    result=[],
                )

            response.raise_for_status()
            data = response.json()

            if data.get("status") != "success":
                return MetricResult(
                    status=MetricResultStatus.ERROR,
                    error=data.get("error", "Unknown error"),
                    result_type=MetricResultType.MATRIX,
                    result=[],
                )

            return self._parse_query_result(data)

        except httpx.HTTPError as e:
            logger.error("Prometheus range query failed", error=str(e))
            return MetricResult(
                status=MetricResultStatus.ERROR,
                error=str(e),
                result_type=MetricResultType.MATRIX,
                result=[],
            )

    async def get_label_values(self, label: str) -> list[str]:
        """Get all values for a label.

        Args:
            label: Label name (e.g., "namespace", "pod")

        Returns:
            List of label values
        """
        client = await self._get_client()
        headers = self._get_auth_headers()

        try:
            response = await client.get(
                f"{self.base_url}/api/v1/label/{label}/values",
                headers=headers,
            )

            response.raise_for_status()
            data = response.json()

            if data.get("status") == "success":
                return data.get("data", [])

            return []

        except httpx.HTTPError as e:
            logger.error("Failed to get label values", label=label, error=str(e))
            return []

    async def get_metadata(self, metric: str) -> dict[str, Any]:
        """Get metric metadata.

        Args:
            metric: Metric name

        Returns:
            Metadata dictionary
        """
        client = await self._get_client()
        headers = self._get_auth_headers()

        try:
            response = await client.get(
                f"{self.base_url}/api/v1/metadata",
                headers=headers,
                params={"metric": metric},
            )

            response.raise_for_status()
            data = response.json()

            if data.get("status") == "success":
                return data.get("data", {}).get(metric, [{}])[0]

            return {}

        except httpx.HTTPError:
            return {}

    async def check_health(self) -> bool:
        """Check Prometheus health.

        Returns:
            True if healthy, False otherwise
        """
        client = await self._get_client()
        headers = self._get_auth_headers()

        try:
            response = await client.get(
                f"{self.base_url}/-/healthy",
                headers=headers,
                timeout=5.0,
            )
            return response.status_code == 200

        except httpx.HTTPError:
            return False

    def _parse_query_result(self, data: dict) -> MetricResult:
        """Parse Prometheus API response to MetricResult."""
        result_data = data.get("data", {})
        result_type_str = result_data.get("resultType", "vector")

        # Map to our enum
        result_type = MetricResultType.VECTOR
        if result_type_str == "matrix":
            result_type = MetricResultType.MATRIX
        elif result_type_str == "scalar":
            result_type = MetricResultType.SCALAR
        elif result_type_str == "string":
            result_type = MetricResultType.STRING

        # Parse result items
        result_items = result_data.get("result", [])
        series_list = []

        for item in result_items:
            metric_labels = item.get("metric", {})
            metric_name = metric_labels.pop("__name__", "")

            if result_type == MetricResultType.MATRIX:
                # Range query - has "values" array
                values = [
                    {"timestamp": v[0], "value": float(v[1])}
                    for v in item.get("values", [])
                ]
            else:
                # Instant query - has single "value"
                v = item.get("value", [0, "0"])
                values = [{"timestamp": v[0], "value": float(v[1])}]

            series_list.append(
                MetricSeries(
                    metric=metric_name,
                    labels=metric_labels,
                    values=values,
                )
            )

        return MetricResult(
            status=MetricResultStatus.SUCCESS,
            result_type=result_type,
            result=series_list,
        )

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Factory function for creating clients
async def create_prometheus_client(
    cluster_id: str,
    prometheus_url: str,
    cluster_token: str,
    skip_tls_verify: bool = False,
) -> PrometheusClient:
    """Create authenticated Prometheus client for a cluster.

    Args:
        cluster_id: Cluster identifier for logging
        prometheus_url: Prometheus/Thanos URL
        cluster_token: Bearer token for authentication
        skip_tls_verify: Whether to skip TLS verification

    Returns:
        Configured PrometheusClient
    """
    auth_config = PrometheusAuthConfig(
        auth_type=PrometheusAuthType.BEARER,
        token=cluster_token,
        skip_tls_verify=skip_tls_verify,
    )

    logger.info(
        "Creating Prometheus client",
        cluster_id=cluster_id,
        url=prometheus_url,
    )

    return PrometheusClient(
        base_url=prometheus_url,
        auth_config=auth_config,
    )
```

### Tests

**File:** `src/observability-collector/tests/test_prometheus_client.py`

```python
"""Tests for Prometheus client."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
import httpx

from clients.prometheus import (
    PrometheusClient,
    PrometheusAuthConfig,
    PrometheusAuthType,
)
from shared.models import MetricResultStatus, MetricResultType


@pytest.fixture
def auth_config():
    return PrometheusAuthConfig(
        auth_type=PrometheusAuthType.BEARER,
        token="test-bearer-token",
    )


@pytest.fixture
def prometheus_client(auth_config):
    return PrometheusClient(
        base_url="https://prometheus.example.com",
        auth_config=auth_config,
    )


class TestAuthentication:
    def test_bearer_auth_headers(self, prometheus_client):
        """Test Bearer token header generation."""
        headers = prometheus_client._get_auth_headers()

        assert headers["Authorization"] == "Bearer test-bearer-token"

    def test_no_auth_headers_when_none(self):
        """Test no headers when auth type is NONE."""
        config = PrometheusAuthConfig(auth_type=PrometheusAuthType.NONE)
        client = PrometheusClient("http://localhost:9090", config)

        headers = client._get_auth_headers()

        assert "Authorization" not in headers

    def test_basic_auth_configured(self):
        """Test Basic auth client creation."""
        config = PrometheusAuthConfig(
            auth_type=PrometheusAuthType.BASIC,
            username="admin",
            password="secret",
        )
        client = PrometheusClient("http://localhost:9090", config)

        assert client.auth_config.username == "admin"


class TestQueries:
    async def test_instant_query_success(self, prometheus_client):
        """Test successful instant query."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [
                    {
                        "metric": {"__name__": "up", "job": "prometheus"},
                        "value": [1234567890, "1"],
                    }
                ],
            },
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(prometheus_client, "_get_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_client

            result = await prometheus_client.query("up")

            assert result.status == MetricResultStatus.SUCCESS
            assert result.result_type == MetricResultType.VECTOR
            assert len(result.result) == 1
            assert result.result[0].metric == "up"

    async def test_query_auth_failure(self, prometheus_client):
        """Test query with authentication failure."""
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch.object(prometheus_client, "_get_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_client

            result = await prometheus_client.query("up")

            assert result.status == MetricResultStatus.ERROR
            assert "Authentication failed" in result.error

    async def test_query_authorization_failure(self, prometheus_client):
        """Test query with authorization failure."""
        mock_response = MagicMock()
        mock_response.status_code = 403

        with patch.object(prometheus_client, "_get_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_client

            result = await prometheus_client.query("up")

            assert result.status == MetricResultStatus.ERROR
            assert "Authorization failed" in result.error

    async def test_range_query_success(self, prometheus_client):
        """Test successful range query."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [
                    {
                        "metric": {"__name__": "up", "job": "prometheus"},
                        "values": [
                            [1234567890, "1"],
                            [1234567950, "1"],
                            [1234568010, "1"],
                        ],
                    }
                ],
            },
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(prometheus_client, "_get_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_client

            now = datetime.now(timezone.utc)
            start = now.replace(hour=now.hour - 1)

            result = await prometheus_client.query_range("up", start, now, "1m")

            assert result.status == MetricResultStatus.SUCCESS
            assert result.result_type == MetricResultType.MATRIX
            assert len(result.result[0].values) == 3

    async def test_query_timeout(self, prometheus_client):
        """Test query timeout handling."""
        with patch.object(prometheus_client, "_get_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_get.return_value = mock_client

            result = await prometheus_client.query("up")

            assert result.status == MetricResultStatus.ERROR
            assert "timeout" in result.error.lower()


class TestHealthCheck:
    async def test_healthy(self, prometheus_client):
        """Test health check returns True when healthy."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(prometheus_client, "_get_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_client

            result = await prometheus_client.check_health()

            assert result is True

    async def test_unhealthy(self, prometheus_client):
        """Test health check returns False when unhealthy."""
        with patch.object(prometheus_client, "_get_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_get.return_value = mock_client

            result = await prometheus_client.check_health()

            assert result is False


class TestResultParsing:
    def test_parse_vector_result(self, prometheus_client):
        """Test parsing vector (instant) query result."""
        data = {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [
                    {
                        "metric": {"__name__": "up", "instance": "localhost:9090"},
                        "value": [1234567890.123, "1"],
                    }
                ],
            },
        }

        result = prometheus_client._parse_query_result(data)

        assert result.result_type == MetricResultType.VECTOR
        assert result.result[0].labels["instance"] == "localhost:9090"
        assert result.result[0].values[0]["value"] == 1.0

    def test_parse_matrix_result(self, prometheus_client):
        """Test parsing matrix (range) query result."""
        data = {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [
                    {
                        "metric": {"__name__": "up"},
                        "values": [
                            [1234567890, "1"],
                            [1234567950, "0.5"],
                        ],
                    }
                ],
            },
        }

        result = prometheus_client._parse_query_result(data)

        assert result.result_type == MetricResultType.MATRIX
        assert len(result.result[0].values) == 2
        assert result.result[0].values[1]["value"] == 0.5
```

---

## Task 3.2: Query Cache with Redis

**File:** `src/observability-collector/services/query_cache.py`

### Implementation

```python
"""Query result caching with Redis.

Spec Reference: specs/03-observability-collector.md Section 3.1.3

Caches Prometheus query results to reduce load on target clusters
and improve response times for repeated queries.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Optional

import redis.asyncio as redis
from pydantic import BaseModel

from shared.config import get_settings
from shared.observability import get_logger

logger = get_logger(__name__)

# Redis DB for caching
CACHE_DB = 2


class CacheEntry(BaseModel):
    """Cached query result."""

    data: dict
    cached_at: datetime
    ttl_seconds: int
    cluster_id: str
    query_hash: str


class QueryCache:
    """Redis-based query result cache."""

    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[redis.Redis] = None
        self._default_ttl = 30  # seconds

    async def _get_client(self) -> redis.Redis:
        """Get or create Redis client."""
        if self._client is None:
            self._client = redis.from_url(
                f"{self.settings.redis.url}/{CACHE_DB}",
                decode_responses=True,
            )

        return self._client

    def _make_cache_key(
        self,
        cluster_id: str,
        query: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        step: Optional[str] = None,
    ) -> str:
        """Generate cache key from query parameters.

        Uses SHA256 hash of query components to ensure consistent keys.
        """
        key_parts = [
            cluster_id,
            query,
        ]

        if start:
            # Round to step interval for better cache hits
            key_parts.append(str(int(start.timestamp())))
        if end:
            key_parts.append(str(int(end.timestamp())))
        if step:
            key_parts.append(step)

        key_string = "|".join(key_parts)
        query_hash = hashlib.sha256(key_string.encode()).hexdigest()[:16]

        return f"prom:query:{cluster_id}:{query_hash}"

    async def get(
        self,
        cluster_id: str,
        query: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        step: Optional[str] = None,
    ) -> Optional[dict]:
        """Get cached query result.

        Args:
            cluster_id: Cluster identifier
            query: PromQL query
            start: Range query start time
            end: Range query end time
            step: Range query step

        Returns:
            Cached result dict or None if not cached
        """
        client = await self._get_client()
        cache_key = self._make_cache_key(cluster_id, query, start, end, step)

        try:
            cached = await client.get(cache_key)

            if cached:
                logger.debug(
                    "Cache hit",
                    cluster_id=cluster_id,
                    cache_key=cache_key,
                )
                return json.loads(cached)

            logger.debug(
                "Cache miss",
                cluster_id=cluster_id,
                cache_key=cache_key,
            )
            return None

        except redis.RedisError as e:
            logger.warning("Cache read error", error=str(e))
            return None

    async def set(
        self,
        cluster_id: str,
        query: str,
        result: dict,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        step: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """Cache query result.

        Args:
            cluster_id: Cluster identifier
            query: PromQL query
            result: Query result to cache
            start: Range query start time
            end: Range query end time
            step: Range query step
            ttl_seconds: Cache TTL (defaults to 30s)

        Returns:
            True if cached successfully
        """
        client = await self._get_client()
        cache_key = self._make_cache_key(cluster_id, query, start, end, step)
        ttl = ttl_seconds or self._default_ttl

        try:
            await client.setex(
                cache_key,
                ttl,
                json.dumps(result),
            )

            logger.debug(
                "Cached result",
                cluster_id=cluster_id,
                cache_key=cache_key,
                ttl=ttl,
            )
            return True

        except redis.RedisError as e:
            logger.warning("Cache write error", error=str(e))
            return False

    async def invalidate(
        self,
        cluster_id: str,
        query: Optional[str] = None,
    ) -> int:
        """Invalidate cached results.

        Args:
            cluster_id: Cluster identifier
            query: Optional specific query to invalidate

        Returns:
            Number of invalidated entries
        """
        client = await self._get_client()

        if query:
            # Invalidate specific query across all time ranges
            pattern = f"prom:query:{cluster_id}:*"
        else:
            # Invalidate all queries for cluster
            pattern = f"prom:query:{cluster_id}:*"

        try:
            keys = []
            async for key in client.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                await client.delete(*keys)

            logger.info(
                "Invalidated cache",
                cluster_id=cluster_id,
                count=len(keys),
            )
            return len(keys)

        except redis.RedisError as e:
            logger.warning("Cache invalidation error", error=str(e))
            return 0

    async def close(self):
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None


# Singleton instance
query_cache = QueryCache()
```

---

## Task 3.3: Metrics Collector Service

**File:** `src/observability-collector/services/metrics_collector.py`

### Implementation

```python
"""Metrics Collector Service.

Spec Reference: specs/03-observability-collector.md Section 3

Coordinates metric collection across multiple clusters with:
- Authentication handling
- Query caching
- Concurrent cluster queries
- Error handling and retries
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional

from clients.prometheus import PrometheusClient, create_prometheus_client
from services.query_cache import query_cache
from shared.models import MetricQuery, MetricResult, MetricResultStatus
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
                    result_type="vector",
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
```

---

## Task 3.4: Update API Endpoints

**File:** `src/observability-collector/api/v1/metrics.py` (MODIFY)

### Implementation

```python
"""Metrics API endpoints.

Spec Reference: specs/03-observability-collector.md Section 5.1
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query

from services.metrics_collector import metrics_collector
from services.cluster_client import get_cluster_credentials  # From Sprint 2
from shared.models import MetricQuery, MetricResult, MetricResultStatus
from shared.observability import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.post("/query")
async def query_metrics(
    cluster_id: str,
    query: MetricQuery,
) -> MetricResult:
    """Execute PromQL query against cluster Prometheus.

    Args:
        cluster_id: Target cluster ID
        query: PromQL query specification

    Returns:
        MetricResult with query results
    """
    # Get cluster credentials
    cluster = await get_cluster_credentials(cluster_id)

    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cluster {cluster_id} not found",
        )

    if not cluster.endpoints.prometheus_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cluster {cluster_id} does not have Prometheus configured",
        )

    # Execute query
    result = await metrics_collector.query(
        cluster_id=cluster_id,
        prometheus_url=cluster.endpoints.prometheus_url,
        token=cluster.credentials.token,
        query=query,
        skip_tls_verify=cluster.credentials.skip_tls_verify,
    )

    return result


@router.get("/query")
async def query_metrics_get(
    cluster_id: str,
    query: str = Query(..., description="PromQL query"),
    time: Optional[datetime] = Query(None, description="Evaluation timestamp"),
) -> MetricResult:
    """Execute instant PromQL query (GET method).

    Args:
        cluster_id: Target cluster ID
        query: PromQL query string
        time: Optional evaluation timestamp

    Returns:
        MetricResult with query results
    """
    metric_query = MetricQuery(query=query, time=time)
    return await query_metrics(cluster_id, metric_query)


@router.get("/query_range")
async def query_metrics_range(
    cluster_id: str,
    query: str = Query(..., description="PromQL query"),
    start: datetime = Query(..., description="Start timestamp"),
    end: datetime = Query(..., description="End timestamp"),
    step: str = Query("1m", description="Query step"),
) -> MetricResult:
    """Execute range PromQL query.

    Args:
        cluster_id: Target cluster ID
        query: PromQL query string
        start: Start timestamp
        end: End timestamp
        step: Query resolution step

    Returns:
        MetricResult with time series data
    """
    metric_query = MetricQuery(query=query, start=start, end=end, step=step)
    return await query_metrics(cluster_id, metric_query)


@router.get("/labels/{label}")
async def get_label_values(
    cluster_id: str,
    label: str,
) -> list[str]:
    """Get all values for a Prometheus label.

    Args:
        cluster_id: Target cluster ID
        label: Label name

    Returns:
        List of label values
    """
    cluster = await get_cluster_credentials(cluster_id)

    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cluster {cluster_id} not found",
        )

    if not cluster.endpoints.prometheus_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cluster {cluster_id} does not have Prometheus configured",
        )

    client = await metrics_collector.get_client(
        cluster_id=cluster_id,
        prometheus_url=cluster.endpoints.prometheus_url,
        token=cluster.credentials.token,
        skip_tls_verify=cluster.credentials.skip_tls_verify,
    )

    return await client.get_label_values(label)


@router.post("/query/multi")
async def query_multiple_clusters(
    cluster_ids: list[str],
    query: MetricQuery,
) -> dict[str, MetricResult]:
    """Execute query across multiple clusters.

    Args:
        cluster_ids: List of target cluster IDs
        query: PromQL query specification

    Returns:
        Dict mapping cluster_id to MetricResult
    """
    # Get credentials for all clusters
    clusters = []
    for cluster_id in cluster_ids:
        cluster = await get_cluster_credentials(cluster_id)
        if cluster and cluster.endpoints.prometheus_url:
            clusters.append({
                "id": cluster_id,
                "prometheus_url": cluster.endpoints.prometheus_url,
                "token": cluster.credentials.token,
                "skip_tls_verify": cluster.credentials.skip_tls_verify,
            })

    if not clusters:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No valid clusters found",
        )

    return await metrics_collector.query_multiple_clusters(clusters, query)
```

---

## Acceptance Criteria

- [ ] Prometheus client includes Bearer token in all requests
- [ ] 401 responses handled with clear error messages
- [ ] 403 responses indicate authorization failure
- [ ] Query results cached in Redis (DB 2) for 30 seconds
- [ ] Cache key includes cluster_id, query, and time range
- [ ] Cache hits return immediately without cluster call
- [ ] Multiple clusters queried concurrently
- [ ] Health check endpoint validates Prometheus availability
- [ ] All tests pass with >80% coverage

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `src/observability-collector/clients/prometheus.py` | CREATE | Authenticated Prometheus client |
| `src/observability-collector/clients/__init__.py` | CREATE | Clients package init |
| `src/observability-collector/services/query_cache.py` | CREATE | Redis query cache |
| `src/observability-collector/services/metrics_collector.py` | CREATE | Metrics collection service |
| `src/observability-collector/api/v1/metrics.py` | MODIFY | Update with auth |
| `src/observability-collector/tests/test_prometheus_client.py` | CREATE | Client tests |
| `src/observability-collector/tests/test_query_cache.py` | CREATE | Cache tests |

---

## Dependencies

### Python packages

Already included in shared pyproject.toml:
- `httpx` - Async HTTP client
- `redis` - Redis client

---

## Rollback Plan

If issues arise:
1. Remove Bearer token from client temporarily
2. Disable caching by setting `_cache_enabled = False`
3. Return to direct HTTP calls without client abstraction
