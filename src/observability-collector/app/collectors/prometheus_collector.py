"""Prometheus collector for federated queries.

Spec Reference: specs/03-observability-collector.md Section 6.1
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import httpx

from shared.config import get_settings
from shared.observability import get_logger

logger = get_logger(__name__)


class PrometheusCollector:
    """Collector for Prometheus/Thanos queries.

    Spec Reference: specs/03-observability-collector.md Section 6.1
    """

    def __init__(self):
        self.settings = get_settings()
        # Create client with SSL verification based on settings
        # In sandbox/development mode, we may skip TLS verification
        verify = not self.settings.is_development
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=5.0),
            follow_redirects=True,
            verify=verify,
        )

    async def query(
        self,
        cluster: dict,
        query: str,
        time: datetime | None = None,
        timeout: int = 30,
    ) -> dict[str, Any]:
        """Execute instant PromQL query on single cluster.

        Spec Reference: specs/03-observability-collector.md Section 6.1
        """
        prometheus_url = cluster.get("endpoints", {}).get("prometheus_url")

        if not prometheus_url:
            return {
                "cluster_id": str(cluster["id"]),
                "cluster_name": cluster["name"],
                "status": "ERROR",
                "error": "No Prometheus URL configured",
                "result_type": None,
                "data": [],
            }

        url = f"{prometheus_url}/api/v1/query"
        params = {"query": query}

        if time:
            params["time"] = time.isoformat()

        try:
            # Get auth token if available
            headers = self._get_auth_headers(cluster)

            response = await asyncio.wait_for(
                self.client.get(url, params=params, headers=headers),
                timeout=timeout,
            )

            if response.status_code != 200:
                return {
                    "cluster_id": str(cluster["id"]),
                    "cluster_name": cluster["name"],
                    "status": "ERROR",
                    "error": f"HTTP {response.status_code}: {response.text[:200]}",
                    "result_type": None,
                    "data": [],
                }

            data = response.json()

            if data.get("status") != "success":
                return {
                    "cluster_id": str(cluster["id"]),
                    "cluster_name": cluster["name"],
                    "status": "ERROR",
                    "error": data.get("error", "Unknown error"),
                    "result_type": None,
                    "data": [],
                }

            result = data.get("data", {})
            return {
                "cluster_id": str(cluster["id"]),
                "cluster_name": cluster["name"],
                "status": "SUCCESS",
                "result_type": result.get("resultType", "").upper(),
                "data": self._parse_result(result),
            }

        except TimeoutError:
            return {
                "cluster_id": str(cluster["id"]),
                "cluster_name": cluster["name"],
                "status": "TIMEOUT",
                "error": f"Query timed out after {timeout}s",
                "result_type": None,
                "data": [],
            }
        except Exception as e:
            logger.error(
                "Prometheus query failed",
                cluster_id=cluster["id"],
                error=str(e),
            )
            return {
                "cluster_id": str(cluster["id"]),
                "cluster_name": cluster["name"],
                "status": "ERROR",
                "error": str(e),
                "result_type": None,
                "data": [],
            }

    async def query_range(
        self,
        cluster: dict,
        query: str,
        start_time: datetime,
        end_time: datetime,
        step: str = "1m",
        timeout: int = 30,
    ) -> dict[str, Any]:
        """Execute range PromQL query on single cluster.

        Spec Reference: specs/03-observability-collector.md Section 6.1
        """
        prometheus_url = cluster.get("endpoints", {}).get("prometheus_url")

        if not prometheus_url:
            return {
                "cluster_id": str(cluster["id"]),
                "cluster_name": cluster["name"],
                "status": "ERROR",
                "error": "No Prometheus URL configured",
                "result_type": None,
                "data": [],
            }

        url = f"{prometheus_url}/api/v1/query_range"
        params = {
            "query": query,
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "step": step,
        }

        try:
            headers = self._get_auth_headers(cluster)

            response = await asyncio.wait_for(
                self.client.get(url, params=params, headers=headers),
                timeout=timeout,
            )

            if response.status_code != 200:
                return {
                    "cluster_id": str(cluster["id"]),
                    "cluster_name": cluster["name"],
                    "status": "ERROR",
                    "error": f"HTTP {response.status_code}: {response.text[:200]}",
                    "result_type": None,
                    "data": [],
                }

            data = response.json()

            if data.get("status") != "success":
                return {
                    "cluster_id": str(cluster["id"]),
                    "cluster_name": cluster["name"],
                    "status": "ERROR",
                    "error": data.get("error", "Unknown error"),
                    "result_type": None,
                    "data": [],
                }

            result = data.get("data", {})
            return {
                "cluster_id": str(cluster["id"]),
                "cluster_name": cluster["name"],
                "status": "SUCCESS",
                "result_type": result.get("resultType", "").upper(),
                "data": self._parse_result(result),
            }

        except TimeoutError:
            return {
                "cluster_id": str(cluster["id"]),
                "cluster_name": cluster["name"],
                "status": "TIMEOUT",
                "error": f"Query timed out after {timeout}s",
                "result_type": None,
                "data": [],
            }
        except Exception as e:
            logger.error(
                "Prometheus range query failed",
                cluster_id=cluster["id"],
                error=str(e),
            )
            return {
                "cluster_id": str(cluster["id"]),
                "cluster_name": cluster["name"],
                "status": "ERROR",
                "error": str(e),
                "result_type": None,
                "data": [],
            }

    async def get_labels(self, cluster: dict) -> list[str]:
        """Get label names from Prometheus.

        Spec Reference: specs/03-observability-collector.md Section 5.1
        """
        prometheus_url = cluster.get("endpoints", {}).get("prometheus_url")

        if not prometheus_url:
            return []

        url = f"{prometheus_url}/api/v1/labels"

        try:
            headers = self._get_auth_headers(cluster)
            response = await self.client.get(url, headers=headers)

            if response.status_code != 200:
                return []

            data = response.json()
            if data.get("status") == "success":
                return data.get("data", [])
            return []

        except Exception as e:
            logger.warning(
                "Failed to get labels from Prometheus",
                cluster_id=cluster.get("id"),
                error=str(e),
            )
            return []

    def _get_auth_headers(self, cluster: dict) -> dict[str, str]:
        """Get authentication headers for cluster."""
        headers = {}

        # First check if cluster has a token in credentials
        credentials = cluster.get("credentials", {})
        token = credentials.get("token")

        # For sandbox/development, use the pod's service account token
        # if querying the same cluster
        if not token and self.settings.is_development:
            try:
                with open("/var/run/secrets/kubernetes.io/serviceaccount/token") as f:
                    token = f.read().strip()
            except FileNotFoundError:
                pass

        if token:
            headers["Authorization"] = f"Bearer {token}"

        return headers

    def _parse_result(self, result: dict) -> list[dict]:
        """Parse Prometheus result into standard format."""
        result_type = result.get("resultType", "")
        raw_result = result.get("result", [])

        parsed = []
        for item in raw_result:
            metric = item.get("metric", {})

            if result_type == "matrix":
                values = item.get("values", [])
            elif result_type == "vector":
                value = item.get("value", [])
                values = [value] if value else []
            else:
                values = []

            parsed.append({
                "metric": metric,
                "values": values,
            })

        return parsed
