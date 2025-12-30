"""Cluster Registry client for service-to-service communication.

Spec Reference: specs/08-integration-matrix.md Section 4.2
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx

from shared.observability import get_logger

logger = get_logger(__name__)


class ClusterRegistryClient:
    """Client for Cluster Registry API.

    Spec Reference: specs/08-integration-matrix.md Section 4.2
    """

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(10.0, connect=5.0),
        )

    async def get_cluster(self, cluster_id: UUID) -> dict[str, Any] | None:
        """Get cluster by ID.

        Spec Reference: specs/02-cluster-registry.md Section 4.1
        """
        try:
            response = await self.client.get(f"/api/v1/clusters/{cluster_id}")

            if response.status_code == 404:
                return None

            if response.status_code != 200:
                logger.warning(
                    "Failed to get cluster",
                    cluster_id=str(cluster_id),
                    status_code=response.status_code,
                )
                return None

            return response.json()

        except Exception as e:
            logger.error(
                "Error getting cluster",
                cluster_id=str(cluster_id),
                error=str(e),
            )
            return None

    async def list_clusters(
        self,
        state: str | None = None,
        cluster_type: str | None = None,
        has_gpu: bool | None = None,
    ) -> list[dict[str, Any]]:
        """List clusters with optional filters.

        Spec Reference: specs/02-cluster-registry.md Section 4.1
        """
        try:
            params = {}
            if state:
                params["state"] = state
            if cluster_type:
                params["cluster_type"] = cluster_type
            if has_gpu is not None:
                params["has_gpu"] = str(has_gpu).lower()

            response = await self.client.get("/api/v1/clusters", params=params)

            if response.status_code != 200:
                logger.warning(
                    "Failed to list clusters",
                    status_code=response.status_code,
                )
                return []

            data = response.json()
            return data.get("items", [])

        except Exception as e:
            logger.error("Error listing clusters", error=str(e))
            return []

    async def list_online_clusters(self) -> list[dict[str, Any]]:
        """List only online clusters.

        Spec Reference: specs/02-cluster-registry.md Section 4.1
        """
        return await self.list_clusters(state="ONLINE")

    async def get_cluster_credentials(self, cluster_id: UUID) -> dict[str, Any] | None:
        """Get cluster credentials.

        Note: This would be used for authenticated access to cluster endpoints.
        For sandbox testing, returns None.

        Spec Reference: specs/02-cluster-registry.md Section 4.1
        """
        # In production, this would fetch credentials
        # For sandbox, we don't have real credentials
        return None

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
