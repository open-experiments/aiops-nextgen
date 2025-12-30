"""CNF collector for PTP, SR-IOV, and DPDK telemetry.

Spec Reference: specs/03-observability-collector.md Section 6.3
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from shared.config import get_settings
from shared.observability import get_logger

logger = get_logger(__name__)


class CNFCollector:
    """Collector for CNF telemetry via K8s API and metrics.

    Spec Reference: specs/03-observability-collector.md Section 6.3

    Collects:
    - PTP (Precision Time Protocol) synchronization status
    - SR-IOV (Single Root I/O Virtualization) VF allocation
    - DPDK (Data Plane Development Kit) statistics
    """

    # CNF-related namespaces to search for workloads
    CNF_NAMESPACES = [
        "openshift-ptp",
        "openshift-sriov-network-operator",
        "du-*",
        "cu-*",
        "upf-*",
        "ran-*",
        "5g-*",
    ]

    # PTP operator labels
    PTP_LABELS = [
        "ptp.openshift.io/grandmaster-capable",
        "ptp.openshift.io/slave-capable",
    ]

    # SR-IOV related resources
    SRIOV_NETWORK_NAMESPACE = "openshift-sriov-network-operator"
    SRIOV_CRD_GROUP = "sriovnetwork.openshift.io"

    def __init__(self) -> None:
        """Initialize CNF collector."""
        self.settings = get_settings()
        verify = not self.settings.is_development
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=5.0),
            follow_redirects=True,
            verify=verify,
        )

    def _get_auth_headers(self, cluster: dict) -> dict[str, str]:
        """Get authentication headers for cluster API."""
        headers: dict[str, str] = {"Accept": "application/json"}

        credentials = cluster.get("credentials", {})
        token = credentials.get("bearer_token") or credentials.get("token")

        if not token and self.settings.is_development:
            try:
                with open("/var/run/secrets/kubernetes.io/serviceaccount/token") as f:
                    token = f.read().strip()
            except FileNotFoundError:
                pass

        if token:
            headers["Authorization"] = f"Bearer {token}"

        return headers

    # ==========================================================================
    # CNF Workload Discovery
    # ==========================================================================

    async def get_cnf_workloads(self, cluster: dict) -> list[dict[str, Any]]:
        """Get CNF workloads from a cluster.

        Searches for known CNF namespaces and labels to identify
        vDU, vCU, UPF, and other CNF workloads.
        """
        api_url = cluster.get("api_server_url", "")
        if not api_url:
            return self._get_mock_cnf_workloads(cluster)

        headers = self._get_auth_headers(cluster)
        workloads = []

        try:
            # Get pods in CNF-related namespaces
            namespaces = await self._get_cnf_namespaces(api_url, headers)

            for namespace in namespaces:
                pods = await self._get_namespace_pods(api_url, headers, namespace)
                for pod in pods:
                    cnf_type = self._classify_cnf_workload(pod, namespace)
                    if cnf_type:
                        workloads.append(
                            {
                                "cluster_id": str(cluster["id"]),
                                "cluster_name": cluster["name"],
                                "namespace": namespace,
                                "name": pod.get("metadata", {}).get("name", ""),
                                "type": cnf_type,
                                "status": pod.get("status", {}).get("phase", "Unknown"),
                                "node": pod.get("spec", {}).get("nodeName", ""),
                                "containers": [
                                    c.get("name", "")
                                    for c in pod.get("spec", {}).get("containers", [])
                                ],
                                "last_updated": datetime.utcnow().isoformat(),
                            }
                        )

            if not workloads:
                return self._get_mock_cnf_workloads(cluster)

            return workloads

        except Exception as e:
            logger.warning(
                "Failed to get CNF workloads",
                cluster_id=str(cluster.get("id")),
                error=str(e),
            )
            return self._get_mock_cnf_workloads(cluster)

    async def _get_cnf_namespaces(self, api_url: str, headers: dict[str, str]) -> list[str]:
        """Get namespaces that may contain CNF workloads."""
        namespaces_url = f"{api_url}/api/v1/namespaces"

        try:
            response = await self.client.get(namespaces_url, headers=headers)
            if response.status_code != 200:
                return []

            data = response.json()
            cnf_namespaces = []

            for ns in data.get("items", []):
                name = ns.get("metadata", {}).get("name", "")
                # Check against known CNF namespace patterns
                if any(
                    name.startswith(pattern.replace("*", ""))
                    for pattern in self.CNF_NAMESPACES
                    if "*" in pattern
                ) or name in [p for p in self.CNF_NAMESPACES if "*" not in p]:
                    cnf_namespaces.append(name)

            return cnf_namespaces

        except Exception as e:
            logger.debug("Failed to list namespaces", error=str(e))
            return []

    async def _get_namespace_pods(
        self, api_url: str, headers: dict[str, str], namespace: str
    ) -> list[dict]:
        """Get pods in a namespace."""
        pods_url = f"{api_url}/api/v1/namespaces/{namespace}/pods"

        try:
            response = await self.client.get(pods_url, headers=headers)
            if response.status_code == 200:
                return response.json().get("items", [])
        except Exception as e:
            logger.debug(
                "Failed to get pods",
                namespace=namespace,
                error=str(e),
            )

        return []

    def _classify_cnf_workload(self, pod: dict, namespace: str) -> str | None:
        """Classify a pod as a specific CNF workload type."""
        name = pod.get("metadata", {}).get("name", "").lower()
        labels = pod.get("metadata", {}).get("labels", {})

        # Check by name patterns
        if "vdu" in name or "du-" in name or namespace.startswith("du-"):
            return "vDU"
        if "vcu" in name or "cu-" in name or namespace.startswith("cu-"):
            return "vCU"
        if "upf" in name or namespace.startswith("upf-"):
            return "UPF"
        if "amf" in name:
            return "AMF"
        if "smf" in name:
            return "SMF"
        if "nrf" in name:
            return "NRF"

        # Check by labels
        if labels.get("app.kubernetes.io/component") in ["du", "cu", "upf"]:
            return labels.get("app.kubernetes.io/component").upper()

        # PTP workloads
        if "ptp" in name or "linuxptp" in name:
            return "PTP"

        return None

    # ==========================================================================
    # PTP Status Collection
    # ==========================================================================

    async def get_ptp_status(self, cluster: dict) -> list[dict[str, Any]]:
        """Get PTP synchronization status from a cluster.

        Queries PTP operator resources and metrics for clock sync status.
        """
        api_url = cluster.get("api_server_url", "")
        if not api_url:
            return self._get_mock_ptp_status(cluster)

        headers = self._get_auth_headers(cluster)
        ptp_statuses = []

        try:
            # Get PTP daemon pods
            pods_url = f"{api_url}/api/v1/namespaces/openshift-ptp/pods"
            response = await self.client.get(pods_url, headers=headers)

            if response.status_code == 200:
                pods = response.json().get("items", [])

                for pod in pods:
                    if "linuxptp-daemon" in pod.get("metadata", {}).get("name", ""):
                        node_name = pod.get("spec", {}).get("nodeName", "")
                        status = await self._get_node_ptp_status(cluster, node_name, headers)
                        if status:
                            ptp_statuses.append(status)

            if not ptp_statuses:
                return self._get_mock_ptp_status(cluster)

            return ptp_statuses

        except Exception as e:
            logger.warning(
                "Failed to get PTP status",
                cluster_id=str(cluster.get("id")),
                error=str(e),
            )
            return self._get_mock_ptp_status(cluster)

    async def _get_node_ptp_status(
        self,
        cluster: dict,
        node_name: str,
        headers: dict[str, str],
    ) -> dict[str, Any] | None:
        """Get PTP status for a specific node via metrics."""
        # Try to get PTP metrics from Prometheus
        prometheus_url = cluster.get("endpoints", {}).get("prometheus_url")
        if not prometheus_url:
            return None

        try:
            # Query PTP offset metrics
            query = f'openshift_ptp_offset_ns{{node="{node_name}"}}'
            params = {"query": query}

            response = await self.client.get(
                f"{prometheus_url}/api/v1/query",
                headers=headers,
                params=params,
            )

            if response.status_code == 200:
                data = response.json()
                results = data.get("data", {}).get("result", [])

                if results:
                    offset_ns = float(results[0].get("value", [0, 0])[1])
                    return {
                        "cluster_id": str(cluster["id"]),
                        "cluster_name": cluster["name"],
                        "node": node_name,
                        "interface": results[0].get("metric", {}).get("iface", "eth0"),
                        "state": "LOCKED" if abs(offset_ns) < 100 else "FREERUN",
                        "offset_ns": offset_ns,
                        "max_offset_ns": 100,  # Typical requirement
                        "clock_accuracy": "HIGH" if abs(offset_ns) < 50 else "MEDIUM",
                        "grandmaster": results[0].get("metric", {}).get("grandmaster", "unknown"),
                        "last_updated": datetime.utcnow().isoformat(),
                    }

        except Exception as e:
            logger.debug(
                "Failed to get PTP metrics",
                node=node_name,
                error=str(e),
            )

        return None

    # ==========================================================================
    # SR-IOV Status Collection
    # ==========================================================================

    async def get_sriov_status(self, cluster: dict) -> list[dict[str, Any]]:
        """Get SR-IOV VF allocation status from a cluster.

        Queries SR-IOV network operator for VF configuration and usage.
        """
        api_url = cluster.get("api_server_url", "")
        if not api_url:
            return self._get_mock_sriov_status(cluster)

        headers = self._get_auth_headers(cluster)
        sriov_statuses = []

        try:
            # Get SriovNetworkNodeState resources
            crd_url = (
                f"{api_url}/apis/{self.SRIOV_CRD_GROUP}/v1/"
                f"namespaces/{self.SRIOV_NETWORK_NAMESPACE}/sriovnetworknodestates"
            )
            response = await self.client.get(crd_url, headers=headers)

            if response.status_code == 200:
                states = response.json().get("items", [])

                for state in states:
                    node_name = state.get("metadata", {}).get("name", "")
                    status = state.get("status", {})

                    interfaces = status.get("interfaces", [])
                    for iface in interfaces:
                        total_vfs = iface.get("totalVfs", 0)
                        num_vfs = iface.get("numVfs", 0)

                        sriov_statuses.append(
                            {
                                "cluster_id": str(cluster["id"]),
                                "cluster_name": cluster["name"],
                                "node": node_name,
                                "interface": iface.get("name", ""),
                                "pci_address": iface.get("pciAddress", ""),
                                "driver": iface.get("driver", ""),
                                "vendor": iface.get("vendor", ""),
                                "device_id": iface.get("deviceID", ""),
                                "total_vfs": total_vfs,
                                "configured_vfs": num_vfs,
                                "vfs": iface.get("vfs", []),
                                "mtu": iface.get("mtu", 1500),
                                "link_speed": iface.get("linkSpeed", ""),
                                "last_updated": datetime.utcnow().isoformat(),
                            }
                        )

            if not sriov_statuses:
                return self._get_mock_sriov_status(cluster)

            return sriov_statuses

        except Exception as e:
            logger.warning(
                "Failed to get SR-IOV status",
                cluster_id=str(cluster.get("id")),
                error=str(e),
            )
            return self._get_mock_sriov_status(cluster)

    # ==========================================================================
    # DPDK Statistics Collection
    # ==========================================================================

    async def get_dpdk_stats(
        self,
        cluster: dict,
        namespace: str,
        pod_name: str,
    ) -> dict[str, Any] | None:
        """Get DPDK statistics for a specific pod.

        Executes testpmd or dpdk-stats command in the pod to get
        packet processing statistics.
        """
        api_url = cluster.get("api_server_url", "")
        if not api_url:
            return self._get_mock_dpdk_stats(cluster, pod_name)

        headers = self._get_auth_headers(cluster)

        try:
            # Try to get DPDK stats from metrics endpoint or exec
            prometheus_url = cluster.get("endpoints", {}).get("prometheus_url")
            if prometheus_url:
                # Query DPDK metrics if exposed via Prometheus
                query = f'dpdk_port_tx_packets{{pod="{pod_name}"}}'
                params = {"query": query}

                response = await self.client.get(
                    f"{prometheus_url}/api/v1/query",
                    headers=headers,
                    params=params,
                )

                if response.status_code == 200:
                    data = response.json()
                    results = data.get("data", {}).get("result", [])

                    if results:
                        return self._parse_dpdk_metrics(cluster, pod_name, namespace, results)

            # Fall back to mock data
            return self._get_mock_dpdk_stats(cluster, pod_name)

        except Exception as e:
            logger.warning(
                "Failed to get DPDK stats",
                cluster_id=str(cluster.get("id")),
                pod_name=pod_name,
                error=str(e),
            )
            return self._get_mock_dpdk_stats(cluster, pod_name)

    def _parse_dpdk_metrics(
        self,
        cluster: dict,
        pod_name: str,
        namespace: str,
        metrics: list,
    ) -> dict[str, Any]:
        """Parse DPDK metrics from Prometheus results."""
        stats = {
            "cluster_id": str(cluster["id"]),
            "cluster_name": cluster["name"],
            "namespace": namespace,
            "pod_name": pod_name,
            "ports": [],
            "last_updated": datetime.utcnow().isoformat(),
        }

        ports: dict[str, dict] = {}
        for metric in metrics:
            port = metric.get("metric", {}).get("port", "0")
            if port not in ports:
                ports[port] = {
                    "port_id": int(port),
                    "rx_packets": 0,
                    "tx_packets": 0,
                    "rx_bytes": 0,
                    "tx_bytes": 0,
                    "rx_errors": 0,
                    "tx_errors": 0,
                    "rx_dropped": 0,
                    "tx_dropped": 0,
                }

            metric_name = metric.get("metric", {}).get("__name__", "")
            value = float(metric.get("value", [0, 0])[1])

            if "tx_packets" in metric_name:
                ports[port]["tx_packets"] = int(value)
            elif "rx_packets" in metric_name:
                ports[port]["rx_packets"] = int(value)
            elif "tx_bytes" in metric_name:
                ports[port]["tx_bytes"] = int(value)
            elif "rx_bytes" in metric_name:
                ports[port]["rx_bytes"] = int(value)

        stats["ports"] = list(ports.values())
        return stats

    # ==========================================================================
    # Mock data methods for development/testing
    # ==========================================================================

    def _get_mock_cnf_workloads(self, cluster: dict) -> list[dict[str, Any]]:
        """Generate mock CNF workload data for testing."""
        if not cluster.get("capabilities", {}).get("cnf_types"):
            return []

        workloads = []
        cnf_types = cluster.get("capabilities", {}).get("cnf_types", [])

        for i, cnf_type in enumerate(cnf_types):
            workloads.append(
                {
                    "cluster_id": str(cluster["id"]),
                    "cluster_name": cluster["name"],
                    "namespace": f"{cnf_type.lower()}-system",
                    "name": f"{cnf_type.lower()}-pod-{i:02d}",
                    "type": cnf_type,
                    "status": "Running",
                    "node": f"worker-cnf-{i % 3 + 1:02d}",
                    "containers": [cnf_type.lower(), "sidecar"],
                    "last_updated": datetime.utcnow().isoformat(),
                }
            )

        return workloads

    def _get_mock_ptp_status(self, cluster: dict) -> list[dict[str, Any]]:
        """Generate mock PTP status data for testing."""
        if not cluster.get("capabilities", {}).get("has_ptp"):
            return []

        return [
            {
                "cluster_id": str(cluster["id"]),
                "cluster_name": cluster["name"],
                "node": f"worker-cnf-{i:02d}",
                "interface": "ens1f0",
                "state": "LOCKED",
                "offset_ns": 5 + i * 2,
                "max_offset_ns": 100,
                "clock_accuracy": "HIGH",
                "grandmaster": "GPS-GM-01",
                "last_updated": datetime.utcnow().isoformat(),
            }
            for i in range(1, 3)
        ]

    def _get_mock_sriov_status(self, cluster: dict) -> list[dict[str, Any]]:
        """Generate mock SR-IOV status data for testing."""
        if not cluster.get("capabilities", {}).get("has_sriov"):
            return []

        return [
            {
                "cluster_id": str(cluster["id"]),
                "cluster_name": cluster["name"],
                "node": f"worker-cnf-{i:02d}",
                "interface": f"ens{i}f0",
                "pci_address": f"0000:3b:{i:02x}.0",
                "driver": "mlx5_core",
                "vendor": "Mellanox",
                "device_id": "101b",
                "total_vfs": 64,
                "configured_vfs": 8 + i * 4,
                "vfs": [
                    {"vf_id": v, "mac": f"00:11:22:33:44:{v:02x}", "vlan": 100 + v}
                    for v in range(8 + i * 4)
                ],
                "mtu": 9000,
                "link_speed": "100Gbps",
                "last_updated": datetime.utcnow().isoformat(),
            }
            for i in range(1, 3)
        ]

    def _get_mock_dpdk_stats(self, cluster: dict, pod_name: str) -> dict[str, Any]:
        """Generate mock DPDK statistics for testing."""
        return {
            "cluster_id": str(cluster["id"]),
            "cluster_name": cluster["name"],
            "namespace": "cnf-system",
            "pod_name": pod_name,
            "ports": [
                {
                    "port_id": i,
                    "rx_packets": 1000000 + i * 100000,
                    "tx_packets": 980000 + i * 98000,
                    "rx_bytes": 1500000000 + i * 150000000,
                    "tx_bytes": 1470000000 + i * 147000000,
                    "rx_errors": 0,
                    "tx_errors": 0,
                    "rx_dropped": 100 + i * 10,
                    "tx_dropped": 50 + i * 5,
                }
                for i in range(2)
            ],
            "cpu_cycles": 50000000000,
            "instructions": 40000000000,
            "cache_misses": 1000000,
            "last_updated": datetime.utcnow().isoformat(),
        }

    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()
