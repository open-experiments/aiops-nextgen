"""Cluster Component Discovery Service.

Spec Reference: specs/02-cluster-registry.md Section 4

Automatically discovers cluster components:
- Prometheus endpoints
- Loki endpoints
- Tempo endpoints
- GPU nodes
- CNF components (PTP, SR-IOV, DPDK)
"""

import asyncio
from enum import Enum

import httpx
from pydantic import BaseModel

from shared.models import ClusterCapabilities, ClusterEndpoints, CNFType
from shared.observability import get_logger

logger = get_logger(__name__)


class ComponentStatus(str, Enum):
    """Discovery status for a component."""

    DISCOVERED = "discovered"
    NOT_FOUND = "not_found"
    ERROR = "error"


class DiscoveredComponent(BaseModel):
    """Discovered component details."""

    name: str
    status: ComponentStatus
    endpoint: str | None = None
    version: str | None = None
    namespace: str | None = None
    error: str | None = None


class DiscoveryResult(BaseModel):
    """Complete discovery results for a cluster."""

    prometheus: DiscoveredComponent | None = None
    loki: DiscoveredComponent | None = None
    tempo: DiscoveredComponent | None = None
    gpu_operator: DiscoveredComponent | None = None
    cnf_components: list[DiscoveredComponent] = []
    endpoints: ClusterEndpoints
    capabilities: ClusterCapabilities


class DiscoveryService:
    """Discovers cluster components and capabilities."""

    def __init__(self):
        self.timeout = 15.0

    async def discover(
        self,
        api_url: str,
        auth_headers: dict[str, str],
        verify_ssl: bool = True,
    ) -> DiscoveryResult:
        """Run full cluster discovery.

        Args:
            api_url: Kubernetes API URL
            auth_headers: Authentication headers
            verify_ssl: Whether to verify SSL certificates

        Returns:
            DiscoveryResult with all discovered components
        """
        async with httpx.AsyncClient(
            verify=verify_ssl,
            timeout=self.timeout,
        ) as client:
            # Discover each component in parallel
            prometheus, loki, tempo, gpu, cnf = await asyncio.gather(
                self._discover_prometheus(client, api_url, auth_headers),
                self._discover_loki(client, api_url, auth_headers),
                self._discover_tempo(client, api_url, auth_headers),
                self._discover_gpu_operator(client, api_url, auth_headers),
                self._discover_cnf_components(client, api_url, auth_headers),
            )

            # Build endpoints from discovered components
            endpoints = self._build_endpoints(prometheus, loki, tempo)

            # Build capabilities from discovery
            capabilities = self._build_capabilities(prometheus, loki, tempo, gpu, cnf)

            return DiscoveryResult(
                prometheus=prometheus,
                loki=loki,
                tempo=tempo,
                gpu_operator=gpu,
                cnf_components=cnf,
                endpoints=endpoints,
                capabilities=capabilities,
            )

    async def _discover_prometheus(
        self,
        client: httpx.AsyncClient,
        api_url: str,
        headers: dict[str, str],
    ) -> DiscoveredComponent:
        """Discover Prometheus/Thanos in the cluster."""
        # Check for OpenShift monitoring stack
        namespaces_to_check = [
            "openshift-monitoring",
            "monitoring",
            "prometheus",
        ]
        service_names = [
            "prometheus-k8s",
            "thanos-querier",
            "prometheus",
        ]

        for namespace in namespaces_to_check:
            for service_name in service_names:
                try:
                    url = f"{api_url}/api/v1/namespaces/{namespace}/services/{service_name}"
                    response = await client.get(url, headers=headers)

                    if response.status_code == 200:
                        svc = response.json()
                        # Build service URL
                        port = 9090
                        for p in svc.get("spec", {}).get("ports", []):
                            if p.get("name") in ["web", "http", "prometheus"]:
                                port = p.get("port", 9090)
                                break

                        endpoint = f"http://{service_name}.{namespace}.svc:{port}"

                        # Try to get version
                        version = await self._get_prometheus_version(
                            client, endpoint, headers
                        )

                        return DiscoveredComponent(
                            name="prometheus",
                            status=ComponentStatus.DISCOVERED,
                            endpoint=endpoint,
                            version=version,
                            namespace=namespace,
                        )

                except Exception as e:
                    logger.debug(
                        "Prometheus check failed",
                        namespace=namespace,
                        service=service_name,
                        error=str(e),
                    )

        return DiscoveredComponent(
            name="prometheus",
            status=ComponentStatus.NOT_FOUND,
            error="No Prometheus instance found",
        )

    async def _get_prometheus_version(
        self,
        client: httpx.AsyncClient,
        endpoint: str,
        headers: dict[str, str],
    ) -> str | None:
        """Get Prometheus version from build info endpoint."""
        try:
            response = await client.get(
                f"{endpoint}/api/v1/status/buildinfo",
                headers=headers,
                timeout=5.0,
            )
            if response.status_code == 200:
                return response.json().get("data", {}).get("version")
        except Exception:
            pass
        return None

    async def _discover_loki(
        self,
        client: httpx.AsyncClient,
        api_url: str,
        headers: dict[str, str],
    ) -> DiscoveredComponent:
        """Discover Loki in the cluster."""
        namespaces = ["openshift-logging", "logging", "loki"]
        services = ["loki", "loki-gateway", "loki-distributor"]

        for namespace in namespaces:
            for service in services:
                try:
                    url = f"{api_url}/api/v1/namespaces/{namespace}/services/{service}"
                    response = await client.get(url, headers=headers)

                    if response.status_code == 200:
                        svc = response.json()
                        port = 3100
                        for p in svc.get("spec", {}).get("ports", []):
                            if p.get("name") in ["http", "http-metrics"]:
                                port = p.get("port", 3100)
                                break

                        endpoint = f"http://{service}.{namespace}.svc:{port}"

                        return DiscoveredComponent(
                            name="loki",
                            status=ComponentStatus.DISCOVERED,
                            endpoint=endpoint,
                            namespace=namespace,
                        )

                except Exception as e:
                    logger.debug("Loki check failed", error=str(e))

        return DiscoveredComponent(
            name="loki",
            status=ComponentStatus.NOT_FOUND,
            error="No Loki instance found",
        )

    async def _discover_tempo(
        self,
        client: httpx.AsyncClient,
        api_url: str,
        headers: dict[str, str],
    ) -> DiscoveredComponent:
        """Discover Tempo in the cluster."""
        namespaces = ["openshift-distributed-tracing", "tracing", "tempo"]
        services = ["tempo", "tempo-query", "tempo-distributor"]

        for namespace in namespaces:
            for service in services:
                try:
                    url = f"{api_url}/api/v1/namespaces/{namespace}/services/{service}"
                    response = await client.get(url, headers=headers)

                    if response.status_code == 200:
                        svc = response.json()
                        port = 3200
                        for p in svc.get("spec", {}).get("ports", []):
                            if p.get("name") in ["http", "tempo"]:
                                port = p.get("port", 3200)
                                break

                        endpoint = f"http://{service}.{namespace}.svc:{port}"

                        return DiscoveredComponent(
                            name="tempo",
                            status=ComponentStatus.DISCOVERED,
                            endpoint=endpoint,
                            namespace=namespace,
                        )

                except Exception as e:
                    logger.debug("Tempo check failed", error=str(e))

        return DiscoveredComponent(
            name="tempo",
            status=ComponentStatus.NOT_FOUND,
            error="No Tempo instance found",
        )

    async def _discover_gpu_operator(
        self,
        client: httpx.AsyncClient,
        api_url: str,
        headers: dict[str, str],
    ) -> DiscoveredComponent:
        """Discover NVIDIA GPU Operator."""
        try:
            # Check for GPU operator namespace
            url = f"{api_url}/api/v1/namespaces/gpu-operator"
            response = await client.get(url, headers=headers)

            if response.status_code == 200:
                # Check for nvidia-driver-daemonset
                ds_url = f"{api_url}/apis/apps/v1/namespaces/gpu-operator/daemonsets/nvidia-driver-daemonset"
                ds_response = await client.get(ds_url, headers=headers)

                if ds_response.status_code == 200:
                    return DiscoveredComponent(
                        name="gpu-operator",
                        status=ComponentStatus.DISCOVERED,
                        namespace="gpu-operator",
                    )

            # Also check nvidia-gpu-operator namespace
            url = f"{api_url}/api/v1/namespaces/nvidia-gpu-operator"
            response = await client.get(url, headers=headers)

            if response.status_code == 200:
                return DiscoveredComponent(
                    name="gpu-operator",
                    status=ComponentStatus.DISCOVERED,
                    namespace="nvidia-gpu-operator",
                )

        except Exception as e:
            logger.debug("GPU operator check failed", error=str(e))

        return DiscoveredComponent(
            name="gpu-operator",
            status=ComponentStatus.NOT_FOUND,
            error="No GPU Operator found",
        )

    async def _discover_cnf_components(
        self,
        client: httpx.AsyncClient,
        api_url: str,
        headers: dict[str, str],
    ) -> list[DiscoveredComponent]:
        """Discover CNF components (PTP, SR-IOV, DPDK)."""
        components = []

        # Check for PTP operator
        try:
            url = f"{api_url}/apis/ptp.openshift.io/v1/ptpconfigs"
            response = await client.get(url, headers=headers)

            if response.status_code == 200:
                items = response.json().get("items", [])
                if items:
                    components.append(
                        DiscoveredComponent(
                            name="ptp",
                            status=ComponentStatus.DISCOVERED,
                            namespace="openshift-ptp",
                        )
                    )
        except Exception:
            pass

        # Check for SR-IOV operator
        try:
            url = f"{api_url}/apis/sriovnetwork.openshift.io/v1/sriovnetworknodestates"
            response = await client.get(url, headers=headers)

            if response.status_code == 200:
                items = response.json().get("items", [])
                if items:
                    components.append(
                        DiscoveredComponent(
                            name="sriov",
                            status=ComponentStatus.DISCOVERED,
                            namespace="openshift-sriov-network-operator",
                        )
                    )
        except Exception:
            pass

        return components

    def _build_endpoints(
        self,
        prometheus: DiscoveredComponent,
        loki: DiscoveredComponent,
        tempo: DiscoveredComponent,
    ) -> ClusterEndpoints:
        """Build ClusterEndpoints from discovered components."""
        return ClusterEndpoints(
            prometheus_url=prometheus.endpoint if prometheus.status == ComponentStatus.DISCOVERED else None,
            loki_url=loki.endpoint if loki.status == ComponentStatus.DISCOVERED else None,
            tempo_url=tempo.endpoint if tempo.status == ComponentStatus.DISCOVERED else None,
        )

    def _build_capabilities(
        self,
        prometheus: DiscoveredComponent,
        loki: DiscoveredComponent,
        tempo: DiscoveredComponent,
        gpu: DiscoveredComponent,
        cnf: list[DiscoveredComponent],
    ) -> ClusterCapabilities:
        """Build ClusterCapabilities from discovery results."""
        cnf_types = []
        for c in cnf:
            if c.status == ComponentStatus.DISCOVERED:
                if c.name == "ptp":
                    cnf_types.append(CNFType.VDU)  # PTP often used with VDU
                elif c.name == "sriov":
                    cnf_types.append(CNFType.UPF)  # SR-IOV often used with UPF

        has_gpu = gpu.status == ComponentStatus.DISCOVERED

        return ClusterCapabilities(
            has_gpu=has_gpu,
            has_gpu_nodes=has_gpu,
            has_prometheus=prometheus.status == ComponentStatus.DISCOVERED,
            has_loki=loki.status == ComponentStatus.DISCOVERED,
            has_tempo=tempo.status == ComponentStatus.DISCOVERED,
            has_cnf_workloads=len(cnf_types) > 0,
            cnf_types=cnf_types,
        )


# Singleton instance
discovery_service = DiscoveryService()


async def discover_cluster_components(
    api_url: str,
    auth_headers: dict[str, str],
    verify_ssl: bool = True,
) -> DiscoveryResult:
    """Discover all cluster components."""
    return await discovery_service.discover(api_url, auth_headers, verify_ssl)
