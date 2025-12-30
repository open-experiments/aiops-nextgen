"""Tests for Observability Collector endpoints."""

from __future__ import annotations

from uuid import uuid4

from app.collectors.gpu_collector import GPUCollector
from app.collectors.prometheus_collector import PrometheusCollector


class TestGPUCollector:
    """Tests for GPU collector."""

    def test_generate_mock_gpus(self):
        """Test mock GPU data generation."""
        collector = GPUCollector()

        cluster = {
            "id": str(uuid4()),
            "name": "test-cluster",
            "capabilities": {
                "has_gpu_nodes": True,
                "gpu_count": 4,
                "gpu_types": ["NVIDIA A100"],
            },
        }

        gpus = collector._generate_mock_gpus(cluster, 1)

        assert len(gpus) == 2  # 2 GPUs per node
        assert gpus[0]["name"] == "NVIDIA A100"
        assert gpus[0]["memory_total_mb"] == 80 * 1024
        assert 0 <= gpus[0]["utilization_gpu_percent"] <= 100

    def test_generate_mock_processes(self):
        """Test mock process generation."""
        collector = GPUCollector()

        # Low utilization - no processes
        procs = collector._generate_mock_processes(10)
        assert len(procs) == 0

        # Medium utilization - one process
        procs = collector._generate_mock_processes(30)
        assert len(procs) == 1

        # High utilization - two processes
        procs = collector._generate_mock_processes(70)
        assert len(procs) == 2


class TestPrometheusCollector:
    """Tests for Prometheus collector."""

    def test_parse_result_vector(self):
        """Test parsing vector result."""
        collector = PrometheusCollector()

        result = {
            "resultType": "vector",
            "result": [
                {
                    "metric": {"__name__": "up", "job": "prometheus"},
                    "value": [1703433600, "1"],
                }
            ],
        }

        parsed = collector._parse_result(result)

        assert len(parsed) == 1
        assert parsed[0]["metric"]["__name__"] == "up"
        assert len(parsed[0]["values"]) == 1

    def test_parse_result_matrix(self):
        """Test parsing matrix result."""
        collector = PrometheusCollector()

        result = {
            "resultType": "matrix",
            "result": [
                {
                    "metric": {"__name__": "up", "job": "prometheus"},
                    "values": [
                        [1703433600, "1"],
                        [1703433660, "1"],
                    ],
                }
            ],
        }

        parsed = collector._parse_result(result)

        assert len(parsed) == 1
        assert len(parsed[0]["values"]) == 2

    def test_get_auth_headers(self):
        """Test auth header generation."""
        collector = PrometheusCollector()

        cluster = {"id": str(uuid4()), "name": "test"}
        headers = collector._get_auth_headers(cluster)

        # Currently returns empty headers
        assert isinstance(headers, dict)
