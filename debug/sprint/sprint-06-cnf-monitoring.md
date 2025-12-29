# Sprint 6: CNF Monitoring

**Issues Addressed:** ISSUE-013 (HIGH)
**Priority:** P1
**Dependencies:** Sprint 1, Sprint 2, Sprint 3

---

## Overview

This sprint implements Cloud-Native Function (CNF) monitoring for telecom workloads. Specifically: PTP (Precision Time Protocol), SR-IOV (Single Root I/O Virtualization), and DPDK (Data Plane Development Kit). These are critical for 5G RAN workloads.

---

## Task 6.1: PTP Collector

**File:** `src/observability-collector/collectors/ptp.py`

### Implementation

```python
"""PTP (Precision Time Protocol) Collector.

Spec Reference: specs/03-observability-collector.md Section 3.5.1

Collects PTP synchronization metrics from OpenShift PTP Operator.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional

from kubernetes import client
from kubernetes.client.rest import ApiException
from pydantic import BaseModel

from shared.observability import get_logger

logger = get_logger(__name__)

PTP_NAMESPACE = "openshift-ptp"


class PTPConfig(BaseModel):
    """PTP configuration from PtpConfig CRD."""

    name: str
    namespace: str
    profile: str
    interface: str
    ptp4l_opts: Optional[str] = None
    phc2sys_opts: Optional[str] = None


class PTPStatus(BaseModel):
    """PTP synchronization status."""

    node_name: str
    clock_state: str  # LOCKED, HOLDOVER, FREERUN
    clock_class: int
    offset_from_master_ns: float
    mean_path_delay_ns: float
    steps_removed: int
    gm_identity: str
    port_state: str  # MASTER, SLAVE, PASSIVE
    interface: str
    last_update: datetime


class PTPMetrics(BaseModel):
    """Aggregated PTP metrics for a cluster."""

    configs: list[PTPConfig]
    node_statuses: list[PTPStatus]
    healthy_nodes: int
    total_nodes: int
    average_offset_ns: float
    max_offset_ns: float


class PTPCollector:
    """Collects PTP metrics from OpenShift clusters."""

    def __init__(self):
        self._clients: dict[str, client.CustomObjectsApi] = {}

    def _get_client(
        self,
        api_url: str,
        token: str,
        skip_tls_verify: bool = False,
    ) -> tuple[client.CustomObjectsApi, client.CoreV1Api]:
        """Get Kubernetes clients for a cluster."""
        cache_key = f"{api_url}:{token[:20]}"

        configuration = client.Configuration()
        configuration.host = api_url
        configuration.api_key = {"authorization": f"Bearer {token}"}
        configuration.verify_ssl = not skip_tls_verify

        api_client = client.ApiClient(configuration)

        return (
            client.CustomObjectsApi(api_client),
            client.CoreV1Api(api_client),
        )

    async def get_ptp_configs(
        self,
        api_url: str,
        token: str,
        skip_tls_verify: bool = False,
    ) -> list[PTPConfig]:
        """Get all PTP configurations.

        Args:
            api_url: Kubernetes API URL
            token: Bearer token
            skip_tls_verify: Skip TLS verification

        Returns:
            List of PTPConfig objects
        """
        custom_api, _ = self._get_client(api_url, token, skip_tls_verify)

        try:
            result = await asyncio.to_thread(
                custom_api.list_namespaced_custom_object,
                group="ptp.openshift.io",
                version="v1",
                namespace=PTP_NAMESPACE,
                plural="ptpconfigs",
            )

            configs = []
            for item in result.get("items", []):
                spec = item.get("spec", {})
                profile = spec.get("profile", [{}])[0] if spec.get("profile") else {}

                configs.append(
                    PTPConfig(
                        name=item["metadata"]["name"],
                        namespace=item["metadata"]["namespace"],
                        profile=profile.get("name", "default"),
                        interface=profile.get("interface", ""),
                        ptp4l_opts=profile.get("ptp4lOpts"),
                        phc2sys_opts=profile.get("phc2sysOpts"),
                    )
                )

            return configs

        except ApiException as e:
            logger.error("Failed to get PTP configs", error=str(e))
            return []

    async def get_ptp_status(
        self,
        api_url: str,
        token: str,
        skip_tls_verify: bool = False,
    ) -> list[PTPStatus]:
        """Get PTP synchronization status from all nodes.

        Args:
            api_url: Kubernetes API URL
            token: Bearer token
            skip_tls_verify: Skip TLS verification

        Returns:
            List of PTPStatus objects
        """
        custom_api, core_api = self._get_client(api_url, token, skip_tls_verify)

        try:
            # Get NodePtpDevice resources
            result = await asyncio.to_thread(
                custom_api.list_cluster_custom_object,
                group="ptp.openshift.io",
                version="v1",
                plural="nodeptpdevices",
            )

            statuses = []
            for item in result.get("items", []):
                node_name = item["metadata"]["name"]
                status = item.get("status", {})

                for device in status.get("devices", []):
                    # Get metrics from PTP daemon pod
                    ptp_metrics = await self._get_ptp_daemon_metrics(
                        core_api, node_name
                    )

                    if ptp_metrics:
                        statuses.append(
                            PTPStatus(
                                node_name=node_name,
                                clock_state=ptp_metrics.get("clock_state", "UNKNOWN"),
                                clock_class=ptp_metrics.get("clock_class", 248),
                                offset_from_master_ns=ptp_metrics.get("offset", 0.0),
                                mean_path_delay_ns=ptp_metrics.get("delay", 0.0),
                                steps_removed=ptp_metrics.get("steps_removed", 0),
                                gm_identity=ptp_metrics.get("gm_identity", ""),
                                port_state=ptp_metrics.get("port_state", "UNKNOWN"),
                                interface=device.get("name", ""),
                                last_update=datetime.now(timezone.utc),
                            )
                        )

            return statuses

        except ApiException as e:
            logger.error("Failed to get PTP status", error=str(e))
            return []

    async def _get_ptp_daemon_metrics(
        self,
        core_api: client.CoreV1Api,
        node_name: str,
    ) -> Optional[dict]:
        """Get PTP metrics from linuxptp-daemon pod on a node.

        Parses prometheus metrics exposed by the PTP daemon.
        """
        try:
            # Find the linuxptp-daemon pod on this node
            pods = await asyncio.to_thread(
                core_api.list_namespaced_pod,
                namespace=PTP_NAMESPACE,
                field_selector=f"spec.nodeName={node_name}",
                label_selector="app=linuxptp-daemon",
            )

            if not pods.items:
                return None

            pod = pods.items[0]
            pod_ip = pod.status.pod_ip

            # The daemon exposes metrics on port 9091
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"http://{pod_ip}:9091/metrics")
                if response.status_code == 200:
                    return self._parse_ptp_metrics(response.text)

            return None

        except Exception as e:
            logger.debug("Failed to get PTP daemon metrics", node=node_name, error=str(e))
            return None

    def _parse_ptp_metrics(self, metrics_text: str) -> dict:
        """Parse Prometheus metrics from PTP daemon."""
        metrics = {}

        for line in metrics_text.split("\n"):
            if line.startswith("#") or not line:
                continue

            # Parse metric lines like: openshift_ptp_offset_ns{...} 123.45
            if "openshift_ptp_offset_ns" in line:
                try:
                    value = float(line.split()[-1])
                    metrics["offset"] = value
                except ValueError:
                    pass

            elif "openshift_ptp_delay_ns" in line:
                try:
                    value = float(line.split()[-1])
                    metrics["delay"] = value
                except ValueError:
                    pass

            elif "openshift_ptp_clock_state" in line:
                if "{" in line:
                    # Extract state from label
                    import re
                    match = re.search(r'state="(\w+)"', line)
                    if match:
                        metrics["clock_state"] = match.group(1)

        return metrics

    async def get_ptp_metrics(
        self,
        cluster_id: str,
        api_url: str,
        token: str,
        skip_tls_verify: bool = False,
    ) -> PTPMetrics:
        """Get complete PTP metrics for a cluster.

        Args:
            cluster_id: Cluster identifier
            api_url: Kubernetes API URL
            token: Bearer token
            skip_tls_verify: Skip TLS verification

        Returns:
            PTPMetrics with configs and statuses
        """
        configs = await self.get_ptp_configs(api_url, token, skip_tls_verify)
        statuses = await self.get_ptp_status(api_url, token, skip_tls_verify)

        # Calculate aggregates
        healthy_nodes = sum(1 for s in statuses if s.clock_state == "LOCKED")
        offsets = [abs(s.offset_from_master_ns) for s in statuses]

        return PTPMetrics(
            configs=configs,
            node_statuses=statuses,
            healthy_nodes=healthy_nodes,
            total_nodes=len(statuses),
            average_offset_ns=sum(offsets) / len(offsets) if offsets else 0,
            max_offset_ns=max(offsets) if offsets else 0,
        )


# Singleton instance
ptp_collector = PTPCollector()
```

---

## Task 6.2: SR-IOV Collector

**File:** `src/observability-collector/collectors/sriov.py`

### Implementation

```python
"""SR-IOV (Single Root I/O Virtualization) Collector.

Spec Reference: specs/03-observability-collector.md Section 3.5.2

Collects SR-IOV network configuration and VF allocation metrics.
"""

import asyncio
from typing import Optional

from kubernetes import client
from kubernetes.client.rest import ApiException
from pydantic import BaseModel

from shared.observability import get_logger

logger = get_logger(__name__)

SRIOV_NAMESPACE = "openshift-sriov-network-operator"


class SRIOVDevice(BaseModel):
    """SR-IOV device (PF) on a node."""

    name: str
    vendor: str
    device_id: str
    driver: str
    pf_name: str
    mtu: int
    num_vfs: int
    link_speed: str
    link_type: str  # Ethernet, InfiniBand


class SRIOVNodeState(BaseModel):
    """SR-IOV state for a node."""

    node_name: str
    sync_status: str  # Succeeded, InProgress, Failed
    devices: list[SRIOVDevice]
    total_vfs: int
    allocated_vfs: int


class SRIOVNetwork(BaseModel):
    """SR-IOV network configuration."""

    name: str
    namespace: str
    resource_name: str
    network_namespace: str
    vlan: Optional[int] = None
    ipam: Optional[dict] = None
    spoofchk: bool = True
    trust: bool = False


class SRIOVMetrics(BaseModel):
    """Aggregated SR-IOV metrics."""

    node_states: list[SRIOVNodeState]
    networks: list[SRIOVNetwork]
    total_vfs_available: int
    total_vfs_allocated: int
    nodes_in_sync: int
    nodes_out_of_sync: int


class SRIOVCollector:
    """Collects SR-IOV metrics from OpenShift clusters."""

    def _get_client(
        self,
        api_url: str,
        token: str,
        skip_tls_verify: bool = False,
    ) -> client.CustomObjectsApi:
        """Get Kubernetes custom objects client."""
        configuration = client.Configuration()
        configuration.host = api_url
        configuration.api_key = {"authorization": f"Bearer {token}"}
        configuration.verify_ssl = not skip_tls_verify

        api_client = client.ApiClient(configuration)
        return client.CustomObjectsApi(api_client)

    async def get_node_states(
        self,
        api_url: str,
        token: str,
        skip_tls_verify: bool = False,
    ) -> list[SRIOVNodeState]:
        """Get SR-IOV state for all nodes.

        Args:
            api_url: Kubernetes API URL
            token: Bearer token
            skip_tls_verify: Skip TLS verification

        Returns:
            List of SRIOVNodeState objects
        """
        custom_api = self._get_client(api_url, token, skip_tls_verify)

        try:
            result = await asyncio.to_thread(
                custom_api.list_cluster_custom_object,
                group="sriovnetwork.openshift.io",
                version="v1",
                plural="sriovnetworknodestates",
            )

            states = []
            for item in result.get("items", []):
                node_name = item["metadata"]["name"]
                status = item.get("status", {})
                sync_status = status.get("syncStatus", "Unknown")

                devices = []
                total_vfs = 0
                allocated_vfs = 0

                for iface in status.get("interfaces", []):
                    num_vfs = iface.get("numVfs", 0)
                    total_vfs += iface.get("totalvfs", 0)
                    allocated_vfs += num_vfs

                    devices.append(
                        SRIOVDevice(
                            name=iface.get("name", ""),
                            vendor=iface.get("vendor", ""),
                            device_id=iface.get("deviceID", ""),
                            driver=iface.get("driver", ""),
                            pf_name=iface.get("name", ""),
                            mtu=iface.get("mtu", 1500),
                            num_vfs=num_vfs,
                            link_speed=iface.get("linkSpeed", ""),
                            link_type=iface.get("linkType", "Ethernet"),
                        )
                    )

                states.append(
                    SRIOVNodeState(
                        node_name=node_name,
                        sync_status=sync_status,
                        devices=devices,
                        total_vfs=total_vfs,
                        allocated_vfs=allocated_vfs,
                    )
                )

            return states

        except ApiException as e:
            logger.error("Failed to get SR-IOV node states", error=str(e))
            return []

    async def get_networks(
        self,
        api_url: str,
        token: str,
        skip_tls_verify: bool = False,
    ) -> list[SRIOVNetwork]:
        """Get SR-IOV network configurations.

        Args:
            api_url: Kubernetes API URL
            token: Bearer token
            skip_tls_verify: Skip TLS verification

        Returns:
            List of SRIOVNetwork objects
        """
        custom_api = self._get_client(api_url, token, skip_tls_verify)

        try:
            result = await asyncio.to_thread(
                custom_api.list_cluster_custom_object,
                group="sriovnetwork.openshift.io",
                version="v1",
                plural="sriovnetworks",
            )

            networks = []
            for item in result.get("items", []):
                spec = item.get("spec", {})

                networks.append(
                    SRIOVNetwork(
                        name=item["metadata"]["name"],
                        namespace=item["metadata"]["namespace"],
                        resource_name=spec.get("resourceName", ""),
                        network_namespace=spec.get("networkNamespace", ""),
                        vlan=spec.get("vlan"),
                        ipam=spec.get("ipam"),
                        spoofchk=spec.get("spoofChk", "on") == "on",
                        trust=spec.get("trust", "off") == "on",
                    )
                )

            return networks

        except ApiException as e:
            logger.error("Failed to get SR-IOV networks", error=str(e))
            return []

    async def get_sriov_metrics(
        self,
        cluster_id: str,
        api_url: str,
        token: str,
        skip_tls_verify: bool = False,
    ) -> SRIOVMetrics:
        """Get complete SR-IOV metrics for a cluster.

        Args:
            cluster_id: Cluster identifier
            api_url: Kubernetes API URL
            token: Bearer token
            skip_tls_verify: Skip TLS verification

        Returns:
            SRIOVMetrics with node states and networks
        """
        node_states = await self.get_node_states(api_url, token, skip_tls_verify)
        networks = await self.get_networks(api_url, token, skip_tls_verify)

        # Calculate aggregates
        total_vfs = sum(s.total_vfs for s in node_states)
        allocated_vfs = sum(s.allocated_vfs for s in node_states)
        in_sync = sum(1 for s in node_states if s.sync_status == "Succeeded")

        return SRIOVMetrics(
            node_states=node_states,
            networks=networks,
            total_vfs_available=total_vfs,
            total_vfs_allocated=allocated_vfs,
            nodes_in_sync=in_sync,
            nodes_out_of_sync=len(node_states) - in_sync,
        )


# Singleton instance
sriov_collector = SRIOVCollector()
```

---

## Task 6.3: CNF API Endpoints

**File:** `src/observability-collector/api/v1/cnf.py`

### Implementation

```python
"""CNF (Cloud-Native Functions) API endpoints.

Spec Reference: specs/03-observability-collector.md Section 5.5
"""

from fastapi import APIRouter, HTTPException, status

from collectors.ptp import ptp_collector, PTPMetrics
from collectors.sriov import sriov_collector, SRIOVMetrics
from services.cluster_client import get_cluster_credentials
from shared.models import CNFType

router = APIRouter(prefix="/cnf", tags=["cnf"])


@router.get("/ptp")
async def get_ptp_metrics(cluster_id: str) -> PTPMetrics:
    """Get PTP synchronization metrics for a cluster.

    Args:
        cluster_id: Target cluster ID

    Returns:
        PTPMetrics with configs and node statuses
    """
    cluster = await get_cluster_credentials(cluster_id)

    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cluster {cluster_id} not found",
        )

    if CNFType.PTP not in cluster.capabilities.cnf_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cluster {cluster_id} does not have PTP configured",
        )

    return await ptp_collector.get_ptp_metrics(
        cluster_id=cluster_id,
        api_url=cluster.api_url,
        token=cluster.credentials.token,
        skip_tls_verify=cluster.credentials.skip_tls_verify,
    )


@router.get("/sriov")
async def get_sriov_metrics(cluster_id: str) -> SRIOVMetrics:
    """Get SR-IOV metrics for a cluster.

    Args:
        cluster_id: Target cluster ID

    Returns:
        SRIOVMetrics with node states and networks
    """
    cluster = await get_cluster_credentials(cluster_id)

    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cluster {cluster_id} not found",
        )

    if CNFType.SRIOV not in cluster.capabilities.cnf_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cluster {cluster_id} does not have SR-IOV configured",
        )

    return await sriov_collector.get_sriov_metrics(
        cluster_id=cluster_id,
        api_url=cluster.api_url,
        token=cluster.credentials.token,
        skip_tls_verify=cluster.credentials.skip_tls_verify,
    )


@router.get("/summary")
async def get_cnf_summary(cluster_id: str) -> dict:
    """Get CNF capabilities summary for a cluster.

    Args:
        cluster_id: Target cluster ID

    Returns:
        Summary dict with CNF status
    """
    cluster = await get_cluster_credentials(cluster_id)

    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cluster {cluster_id} not found",
        )

    summary = {
        "cluster_id": cluster_id,
        "cnf_types": [t.value for t in cluster.capabilities.cnf_types],
        "ptp": None,
        "sriov": None,
    }

    # Get PTP summary if available
    if CNFType.PTP in cluster.capabilities.cnf_types:
        ptp = await ptp_collector.get_ptp_metrics(
            cluster_id=cluster_id,
            api_url=cluster.api_url,
            token=cluster.credentials.token,
            skip_tls_verify=cluster.credentials.skip_tls_verify,
        )
        summary["ptp"] = {
            "healthy_nodes": ptp.healthy_nodes,
            "total_nodes": ptp.total_nodes,
            "average_offset_ns": round(ptp.average_offset_ns, 2),
            "configs": len(ptp.configs),
        }

    # Get SR-IOV summary if available
    if CNFType.SRIOV in cluster.capabilities.cnf_types:
        sriov = await sriov_collector.get_sriov_metrics(
            cluster_id=cluster_id,
            api_url=cluster.api_url,
            token=cluster.credentials.token,
            skip_tls_verify=cluster.credentials.skip_tls_verify,
        )
        summary["sriov"] = {
            "total_vfs": sriov.total_vfs_available,
            "allocated_vfs": sriov.total_vfs_allocated,
            "nodes_in_sync": sriov.nodes_in_sync,
            "networks": len(sriov.networks),
        }

    return summary
```

---

## Acceptance Criteria

- [x] PTP configs read from PtpConfig CRDs
- [x] PTP sync status includes offset and clock state
- [x] PTP metrics parsed from linuxptp-daemon
- [x] SR-IOV node states show VF allocation
- [x] SR-IOV network configs listed
- [x] CNF summary endpoint aggregates status
- [x] Graceful handling when operators not present
- [x] All tests pass with >80% coverage

---

## Implementation Status: COMPLETED

**Completed Date:** 2025-12-29

### Actual Implementation

Created a comprehensive CNF monitoring solution with collectors and federated services:

#### Files Created:
| File | Description |
|------|-------------|
| `src/observability-collector/app/collectors/cnf_collector.py` | CNF collector for PTP, SR-IOV, DPDK |
| `src/observability-collector/app/services/cnf_service.py` | Federated CNF telemetry service |
| `src/observability-collector/app/api/cnf.py` | CNF API endpoints |

#### API Endpoints Implemented:
- `GET /api/v1/cnf/workloads` - List CNF workloads (vDU, vCU, UPF, AMF, SMF, NRF)
- `GET /api/v1/cnf/ptp/status` - PTP synchronization status
- `GET /api/v1/cnf/sriov/status` - SR-IOV VF allocation status
- `GET /api/v1/cnf/dpdk/stats/{cluster}/{ns}/{pod}` - DPDK statistics
- `GET /api/v1/cnf/summary` - Fleet-wide CNF summary

#### CNF Workload Discovery:
- Searches CNF-related namespaces (openshift-ptp, du-*, cu-*, upf-*, ran-*, 5g-*)
- Classifies workloads by name patterns and labels
- Identifies vDU, vCU, UPF, AMF, SMF, NRF types

#### PTP Metrics:
- Sync state (LOCKED, FREERUN, HOLDOVER)
- Offset from grandmaster (nanoseconds)
- Clock accuracy rating
- Grandmaster identification

#### SR-IOV Metrics:
- VF allocation per interface
- PCI address, driver, vendor
- MTU, link speed
- Total/configured VF counts

#### DPDK Metrics:
- Per-port packet/byte counters
- Error and drop statistics
- CPU performance counters (when available)

#### Sandbox Testing:
- Deployed to sandbox01.narlabs.io
- All endpoints tested and working
- Returns empty data (expected - no CNF-capable clusters registered)

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `src/observability-collector/collectors/ptp.py` | CREATE | PTP collector |
| `src/observability-collector/collectors/sriov.py` | CREATE | SR-IOV collector |
| `src/observability-collector/api/v1/cnf.py` | CREATE | CNF API endpoints |
| `src/observability-collector/tests/test_ptp_collector.py` | CREATE | PTP tests |
| `src/observability-collector/tests/test_sriov_collector.py` | CREATE | SR-IOV tests |
