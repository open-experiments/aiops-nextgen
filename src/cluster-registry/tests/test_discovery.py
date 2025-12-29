"""Tests for discovery service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.discovery import (
    ComponentStatus,
    DiscoveredComponent,
    DiscoveryService,
)


@pytest.fixture
def discovery_service():
    return DiscoveryService()


@pytest.fixture
def mock_headers():
    return {"Authorization": "Bearer test-token"}


class TestPrometheusDiscovery:
    async def test_discovers_openshift_prometheus(self, discovery_service, mock_headers):
        """Test Prometheus discovery in openshift-monitoring namespace."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "spec": {
                "ports": [{"name": "web", "port": 9090}]
            }
        }

        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(return_value=mock_response)

        result = await discovery_service._discover_prometheus(
            mock_instance,
            "https://api.cluster.local:6443",
            mock_headers,
        )

        assert result.status == ComponentStatus.DISCOVERED
        assert result.namespace == "openshift-monitoring"
        assert "9090" in result.endpoint

    async def test_prometheus_not_found(self, discovery_service, mock_headers):
        """Test Prometheus not found returns NOT_FOUND status."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(return_value=mock_response)

        result = await discovery_service._discover_prometheus(
            mock_instance,
            "https://api.cluster.local:6443",
            mock_headers,
        )

        assert result.status == ComponentStatus.NOT_FOUND


class TestGPUDiscovery:
    async def test_discovers_gpu_operator(self, discovery_service, mock_headers):
        """Test GPU operator discovery."""
        # Mock namespace and daemonset exist
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(return_value=mock_response)

        result = await discovery_service._discover_gpu_operator(
            mock_instance,
            "https://api.cluster.local:6443",
            mock_headers,
        )

        assert result.status == ComponentStatus.DISCOVERED
        assert result.namespace == "gpu-operator"

    async def test_gpu_not_found(self, discovery_service, mock_headers):
        """Test GPU operator not found."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(return_value=mock_response)

        result = await discovery_service._discover_gpu_operator(
            mock_instance,
            "https://api.cluster.local:6443",
            mock_headers,
        )

        assert result.status == ComponentStatus.NOT_FOUND


class TestLokiDiscovery:
    async def test_discovers_loki(self, discovery_service, mock_headers):
        """Test Loki discovery."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "spec": {
                "ports": [{"name": "http", "port": 3100}]
            }
        }

        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(return_value=mock_response)

        result = await discovery_service._discover_loki(
            mock_instance,
            "https://api.cluster.local:6443",
            mock_headers,
        )

        assert result.status == ComponentStatus.DISCOVERED


class TestTempoDiscovery:
    async def test_discovers_tempo(self, discovery_service, mock_headers):
        """Test Tempo discovery."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "spec": {
                "ports": [{"name": "http", "port": 3200}]
            }
        }

        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(return_value=mock_response)

        result = await discovery_service._discover_tempo(
            mock_instance,
            "https://api.cluster.local:6443",
            mock_headers,
        )

        assert result.status == ComponentStatus.DISCOVERED


class TestCapabilities:
    def test_build_capabilities_all_present(self, discovery_service):
        """Test capabilities built with all components present."""
        prometheus = DiscoveredComponent(
            name="prometheus",
            status=ComponentStatus.DISCOVERED,
            endpoint="http://prometheus:9090",
        )
        loki = DiscoveredComponent(
            name="loki",
            status=ComponentStatus.DISCOVERED,
            endpoint="http://loki:3100",
        )
        tempo = DiscoveredComponent(
            name="tempo",
            status=ComponentStatus.DISCOVERED,
            endpoint="http://tempo:3200",
        )
        gpu = DiscoveredComponent(
            name="gpu-operator",
            status=ComponentStatus.DISCOVERED,
        )
        cnf = [
            DiscoveredComponent(name="ptp", status=ComponentStatus.DISCOVERED),
            DiscoveredComponent(name="sriov", status=ComponentStatus.DISCOVERED),
        ]

        capabilities = discovery_service._build_capabilities(
            prometheus, loki, tempo, gpu, cnf
        )

        assert capabilities.has_gpu is True
        assert capabilities.has_prometheus is True
        assert capabilities.has_loki is True
        assert capabilities.has_tempo is True
        assert len(capabilities.cnf_types) == 2

    def test_build_capabilities_none_present(self, discovery_service):
        """Test capabilities built with no components present."""
        not_found = DiscoveredComponent(
            name="test",
            status=ComponentStatus.NOT_FOUND,
        )

        capabilities = discovery_service._build_capabilities(
            not_found, not_found, not_found, not_found, []
        )

        assert capabilities.has_gpu is False
        assert capabilities.has_prometheus is False
        assert capabilities.has_loki is False
        assert capabilities.has_tempo is False
        assert capabilities.cnf_types == []


class TestEndpoints:
    def test_build_endpoints_all_discovered(self, discovery_service):
        """Test building endpoints from discovered components."""
        prometheus = DiscoveredComponent(
            name="prometheus",
            status=ComponentStatus.DISCOVERED,
            endpoint="http://prometheus:9090",
        )
        loki = DiscoveredComponent(
            name="loki",
            status=ComponentStatus.DISCOVERED,
            endpoint="http://loki:3100",
        )
        tempo = DiscoveredComponent(
            name="tempo",
            status=ComponentStatus.DISCOVERED,
            endpoint="http://tempo:3200",
        )

        endpoints = discovery_service._build_endpoints(prometheus, loki, tempo)

        assert endpoints.prometheus_url == "http://prometheus:9090"
        assert endpoints.loki_url == "http://loki:3100"
        assert endpoints.tempo_url == "http://tempo:3200"

    def test_build_endpoints_none_discovered(self, discovery_service):
        """Test building endpoints when nothing discovered."""
        not_found = DiscoveredComponent(
            name="test",
            status=ComponentStatus.NOT_FOUND,
        )

        endpoints = discovery_service._build_endpoints(not_found, not_found, not_found)

        assert endpoints.prometheus_url is None
        assert endpoints.loki_url is None
        assert endpoints.tempo_url is None
