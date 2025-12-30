"""Prometheus/Thanos Query Client with Authentication.

Spec Reference: specs/03-observability-collector.md Section 3.1

Supports:
- Bearer token authentication (OpenShift OAuth)
- Basic authentication
- mTLS (client certificates)
- Query caching with Redis
"""

from datetime import datetime
from enum import Enum
from typing import Any

import httpx
from pydantic import BaseModel

from shared.models import (
    MetricResult,
    MetricResultStatus,
    MetricResultType,
    MetricSeries,
)
from shared.observability import get_logger

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
    token: str | None = None
    username: str | None = None
    password: str | None = None
    client_cert_path: str | None = None
    client_key_path: str | None = None
    ca_cert_path: str | None = None
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
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with authentication."""
        if self._client is None:
            # Build SSL context
            verify: bool | str = not self.auth_config.skip_tls_verify
            if self.auth_config.ca_cert_path:
                verify = self.auth_config.ca_cert_path

            # Build client cert for mTLS
            cert = None
            if (
                self.auth_config.auth_type == PrometheusAuthType.MTLS
                and self.auth_config.client_cert_path
                and self.auth_config.client_key_path
            ):
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

        if self.auth_config.auth_type == PrometheusAuthType.BEARER and self.auth_config.token:
            headers["Authorization"] = f"Bearer {self.auth_config.token}"

        return headers

    async def query(self, promql: str, time: datetime | None = None) -> MetricResult:
        """Execute instant query.

        Args:
            promql: PromQL query string
            time: Optional evaluation timestamp (defaults to now)

        Returns:
            MetricResult with query results
        """
        client = await self._get_client()
        headers = self._get_auth_headers()

        params: dict[str, Any] = {"query": promql}
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
                values = [{"timestamp": v[0], "value": float(v[1])} for v in item.get("values", [])]
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
