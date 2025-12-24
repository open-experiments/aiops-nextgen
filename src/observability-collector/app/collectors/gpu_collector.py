"""GPU collector for nvidia-smi telemetry.

Spec Reference: specs/03-observability-collector.md Section 6.2
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from shared.observability import get_logger

logger = get_logger(__name__)


class GPUCollector:
    """Collector for GPU telemetry via kubectl exec nvidia-smi.

    Spec Reference: specs/03-observability-collector.md Section 6.2

    Note: In a real implementation, this would use the Kubernetes API
    to exec into nvidia-driver-daemonset pods and run nvidia-smi.
    For the sandbox, this provides mock data.
    """

    NVIDIA_SMI_CMD = [
        "nvidia-smi",
        "--query-gpu=index,uuid,name,driver_version,memory.total,memory.used,"
        "memory.free,utilization.gpu,utilization.memory,temperature.gpu,"
        "power.draw,power.limit,fan.speed",
        "--format=csv,noheader,nounits",
    ]

    NVIDIA_SMI_PROCESSES_CMD = [
        "nvidia-smi",
        "--query-compute-apps=pid,process_name,used_memory",
        "--format=csv,noheader,nounits",
    ]

    async def list_gpu_nodes(self, cluster: dict) -> list[dict[str, Any]]:
        """List GPU nodes in a cluster.

        In production, this would query K8s API for nodes with GPU labels.
        For sandbox testing, returns mock data if cluster has GPU capability.
        """
        if not cluster.get("capabilities", {}).get("has_gpu_nodes"):
            return []

        # Mock GPU node data for testing
        # In production, this would query the K8s API
        return [
            {
                "cluster_id": str(cluster["id"]),
                "cluster_name": cluster["name"],
                "node_name": f"worker-gpu-{i:02d}",
                "gpus": self._generate_mock_gpus(cluster, i),
                "last_updated": datetime.utcnow().isoformat(),
            }
            for i in range(1, min(cluster.get("capabilities", {}).get("gpu_count", 0) // 2 + 1, 4))
        ]

    async def collect_from_node(
        self,
        cluster: dict,
        node_name: str,
    ) -> dict[str, Any] | None:
        """Collect GPU data from specific node.

        Spec Reference: specs/03-observability-collector.md Section 6.2

        In production, this would:
        1. Find nvidia-driver-daemonset pod on the node
        2. Execute nvidia-smi via kubectl exec
        3. Parse the output

        For sandbox testing, returns mock data.
        """
        if not cluster.get("capabilities", {}).get("has_gpu_nodes"):
            return None

        # Extract node index from name
        try:
            node_index = int(node_name.split("-")[-1])
        except (ValueError, IndexError):
            node_index = 1

        return {
            "cluster_id": str(cluster["id"]),
            "cluster_name": cluster["name"],
            "node_name": node_name,
            "gpus": self._generate_mock_gpus(cluster, node_index),
            "last_updated": datetime.utcnow().isoformat(),
        }

    def _generate_mock_gpus(self, cluster: dict, node_index: int) -> list[dict]:
        """Generate mock GPU data for testing."""
        gpu_types = cluster.get("capabilities", {}).get("gpu_types", ["NVIDIA A100"])
        gpu_count = min(cluster.get("capabilities", {}).get("gpu_count", 0), 8)

        # Distribute GPUs across nodes (2 GPUs per node typically)
        gpus_per_node = 2
        start_index = (node_index - 1) * gpus_per_node
        end_index = min(start_index + gpus_per_node, gpu_count)

        gpus = []
        for i in range(start_index, end_index):
            gpu_type = gpu_types[i % len(gpu_types)] if gpu_types else "NVIDIA A100"

            # Set memory based on GPU type
            if "H100" in gpu_type:
                memory_total = 80 * 1024  # 80GB
            elif "A100" in gpu_type:
                memory_total = 80 * 1024  # 80GB
            elif "A10" in gpu_type:
                memory_total = 24 * 1024  # 24GB
            else:
                memory_total = 16 * 1024  # 16GB

            # Simulate realistic utilization (varies by node index)
            utilization = (50 + (node_index * 10 + i * 5)) % 100
            memory_used = int(memory_total * utilization / 100 * 0.8)

            gpus.append({
                "index": i % gpus_per_node,
                "uuid": f"GPU-{cluster['id'][:8]}-{node_index:02d}-{i:02d}",
                "name": gpu_type,
                "driver_version": "535.104.12",
                "cuda_version": "12.2",
                "memory_total_mb": memory_total,
                "memory_used_mb": memory_used,
                "memory_free_mb": memory_total - memory_used,
                "utilization_gpu_percent": utilization,
                "utilization_memory_percent": int(memory_used / memory_total * 100),
                "temperature_celsius": 55 + utilization // 5,
                "power_draw_watts": 100 + utilization * 2,
                "power_limit_watts": 400,
                "fan_speed_percent": 30 + utilization // 3,
                "processes": self._generate_mock_processes(utilization),
            })

        return gpus

    def _generate_mock_processes(self, utilization: int) -> list[dict]:
        """Generate mock GPU processes."""
        if utilization < 20:
            return []

        processes = []
        if utilization >= 20:
            processes.append({
                "pid": 12345 + utilization,
                "process_name": "python",
                "used_memory_mb": int(utilization * 100),
                "type": "COMPUTE",
            })
        if utilization >= 50:
            processes.append({
                "pid": 12346 + utilization,
                "process_name": "pytorch",
                "used_memory_mb": int(utilization * 200),
                "type": "COMPUTE",
            })

        return processes

    def _parse_nvidia_smi_output(
        self,
        cluster_id: str,
        node_name: str,
        gpu_output: str,
        proc_output: str,
    ) -> dict[str, Any]:
        """Parse nvidia-smi CSV output.

        Spec Reference: specs/03-observability-collector.md Section 6.2

        This would be used in production to parse actual nvidia-smi output.
        """
        gpus = []

        for line in gpu_output.strip().split("\n"):
            if not line:
                continue

            fields = [f.strip() for f in line.split(",")]
            if len(fields) < 13:
                continue

            gpus.append({
                "index": int(fields[0]),
                "uuid": fields[1],
                "name": fields[2],
                "driver_version": fields[3],
                "memory_total_mb": int(float(fields[4])),
                "memory_used_mb": int(float(fields[5])),
                "memory_free_mb": int(float(fields[6])),
                "utilization_gpu_percent": int(float(fields[7])),
                "utilization_memory_percent": int(float(fields[8])),
                "temperature_celsius": int(float(fields[9])),
                "power_draw_watts": float(fields[10]),
                "power_limit_watts": float(fields[11]),
                "fan_speed_percent": int(float(fields[12])) if fields[12] != "[N/A]" else None,
                "processes": [],
            })

        # Parse processes
        processes_by_gpu = {}
        for line in proc_output.strip().split("\n"):
            if not line:
                continue

            fields = [f.strip() for f in line.split(",")]
            if len(fields) < 3:
                continue

            # Note: nvidia-smi doesn't directly provide GPU index for processes
            # Would need additional logic to map processes to GPUs

        return {
            "cluster_id": cluster_id,
            "node_name": node_name,
            "gpus": gpus,
            "last_updated": datetime.utcnow().isoformat(),
        }
