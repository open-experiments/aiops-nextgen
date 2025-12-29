"""Loki collector for federated log queries.

Spec Reference: specs/03-observability-collector.md Section 4.3
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import httpx

from shared.config import get_settings
from shared.observability import get_logger

logger = get_logger(__name__)


class LokiCollector:
    """Collector for Loki/LogQL queries.

    Spec Reference: specs/03-observability-collector.md Section 4.3
    """

    def __init__(self):
        self.settings = get_settings()
        # Skip TLS verification in development mode
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
        limit: int = 100,
        time: datetime | None = None,
        direction: str = "backward",
        timeout: int = 30,
    ) -> dict[str, Any]:
        """Execute instant LogQL query on single cluster.

        Args:
            cluster: Cluster configuration with Loki URL
            query: LogQL query string
            limit: Maximum number of entries to return
            time: Evaluation timestamp (defaults to now)
            direction: Log direction (forward/backward)
            timeout: Query timeout in seconds

        Returns:
            Query result with log entries
        """
        loki_url = cluster.get("endpoints", {}).get("loki_url")

        if not loki_url:
            return {
                "cluster_id": str(cluster["id"]),
                "cluster_name": cluster["name"],
                "status": "ERROR",
                "error": "No Loki URL configured",
                "result_type": None,
                "data": [],
            }

        url = f"{loki_url}/loki/api/v1/query"
        params: dict[str, Any] = {
            "query": query,
            "limit": limit,
            "direction": direction,
        }

        if time:
            params["time"] = int(time.timestamp() * 1e9)  # nanoseconds

        try:
            headers = self._get_auth_headers(cluster)

            response = await asyncio.wait_for(
                self.client.get(url, params=params, headers=headers),
                timeout=timeout,
            )

            if response.status_code == 401:
                return {
                    "cluster_id": str(cluster["id"]),
                    "cluster_name": cluster["name"],
                    "status": "ERROR",
                    "error": "Authentication failed",
                    "result_type": None,
                    "data": [],
                }

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
                "result_type": result.get("resultType", "streams"),
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
                "Loki query failed",
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
        limit: int = 1000,
        step: str | None = None,
        direction: str = "backward",
        timeout: int = 30,
    ) -> dict[str, Any]:
        """Execute range LogQL query on single cluster.

        Args:
            cluster: Cluster configuration with Loki URL
            query: LogQL query string
            start_time: Query start time
            end_time: Query end time
            limit: Maximum number of entries
            step: Query step (for metric queries)
            direction: Log direction
            timeout: Query timeout

        Returns:
            Query result with log entries or metrics
        """
        loki_url = cluster.get("endpoints", {}).get("loki_url")

        if not loki_url:
            return {
                "cluster_id": str(cluster["id"]),
                "cluster_name": cluster["name"],
                "status": "ERROR",
                "error": "No Loki URL configured",
                "result_type": None,
                "data": [],
            }

        url = f"{loki_url}/loki/api/v1/query_range"
        params: dict[str, Any] = {
            "query": query,
            "start": int(start_time.timestamp() * 1e9),
            "end": int(end_time.timestamp() * 1e9),
            "limit": limit,
            "direction": direction,
        }

        if step:
            params["step"] = step

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
                "result_type": result.get("resultType", "streams"),
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
                "Loki range query failed",
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
        """Get available label names from Loki.

        Args:
            cluster: Cluster configuration

        Returns:
            List of label names
        """
        loki_url = cluster.get("endpoints", {}).get("loki_url")

        if not loki_url:
            return []

        url = f"{loki_url}/loki/api/v1/labels"

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
                "Failed to get Loki labels",
                cluster_id=cluster.get("id"),
                error=str(e),
            )
            return []

    async def get_label_values(self, cluster: dict, label: str) -> list[str]:
        """Get values for a specific label.

        Args:
            cluster: Cluster configuration
            label: Label name

        Returns:
            List of label values
        """
        loki_url = cluster.get("endpoints", {}).get("loki_url")

        if not loki_url:
            return []

        url = f"{loki_url}/loki/api/v1/label/{label}/values"

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
                "Failed to get Loki label values",
                cluster_id=cluster.get("id"),
                label=label,
                error=str(e),
            )
            return []

    async def get_series(
        self,
        cluster: dict,
        match: list[str],
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[dict]:
        """Get series matching label selectors.

        Args:
            cluster: Cluster configuration
            match: List of label matchers
            start_time: Optional start time
            end_time: Optional end time

        Returns:
            List of matching series
        """
        loki_url = cluster.get("endpoints", {}).get("loki_url")

        if not loki_url:
            return []

        url = f"{loki_url}/loki/api/v1/series"
        params: dict[str, Any] = {"match[]": match}

        if start_time:
            params["start"] = int(start_time.timestamp() * 1e9)
        if end_time:
            params["end"] = int(end_time.timestamp() * 1e9)

        try:
            headers = self._get_auth_headers(cluster)
            response = await self.client.get(url, params=params, headers=headers)

            if response.status_code != 200:
                return []

            data = response.json()
            if data.get("status") == "success":
                return data.get("data", [])
            return []

        except Exception as e:
            logger.warning(
                "Failed to get Loki series",
                cluster_id=cluster.get("id"),
                error=str(e),
            )
            return []

    def _get_auth_headers(self, cluster: dict) -> dict[str, str]:
        """Get authentication headers for cluster."""
        headers = {}

        # Check if cluster has credentials
        credentials = cluster.get("credentials", {})
        token = credentials.get("token")

        # For development, use pod's service account token
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
        """Parse Loki result into standard format."""
        result_type = result.get("resultType", "")
        raw_result = result.get("result", [])

        if result_type == "streams":
            # Log streams
            return [
                {
                    "stream": entry.get("stream", {}),
                    "values": [
                        {"timestamp": v[0], "line": v[1]}
                        for v in entry.get("values", [])
                    ],
                }
                for entry in raw_result
            ]
        elif result_type == "matrix":
            # Metric result (from metric queries like rate())
            return [
                {
                    "metric": entry.get("metric", {}),
                    "values": [
                        {"timestamp": v[0], "value": float(v[1])}
                        for v in entry.get("values", [])
                    ],
                }
                for entry in raw_result
            ]
        elif result_type == "vector":
            # Instant metric result
            return [
                {
                    "metric": entry.get("metric", {}),
                    "value": {
                        "timestamp": entry.get("value", [0, "0"])[0],
                        "value": float(entry.get("value", [0, "0"])[1]),
                    },
                }
                for entry in raw_result
            ]
        else:
            return raw_result

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
