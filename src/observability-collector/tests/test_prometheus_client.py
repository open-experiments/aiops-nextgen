"""Tests for Prometheus client."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from app.clients.prometheus import (
    PrometheusAuthConfig,
    PrometheusAuthType,
    PrometheusClient,
)

from shared.models import MetricResultStatus, MetricResultType


@pytest.fixture
def auth_config():
    return PrometheusAuthConfig(
        auth_type=PrometheusAuthType.BEARER,
        token="test-bearer-token",
    )


@pytest.fixture
def prometheus_client(auth_config):
    return PrometheusClient(
        base_url="https://prometheus.example.com",
        auth_config=auth_config,
    )


class TestAuthentication:
    def test_bearer_auth_headers(self, prometheus_client):
        """Test Bearer token header generation."""
        headers = prometheus_client._get_auth_headers()

        assert headers["Authorization"] == "Bearer test-bearer-token"

    def test_no_auth_headers_when_none(self):
        """Test no headers when auth type is NONE."""
        config = PrometheusAuthConfig(auth_type=PrometheusAuthType.NONE)
        client = PrometheusClient("http://localhost:9090", config)

        headers = client._get_auth_headers()

        assert "Authorization" not in headers

    def test_basic_auth_configured(self):
        """Test Basic auth client creation."""
        config = PrometheusAuthConfig(
            auth_type=PrometheusAuthType.BASIC,
            username="admin",
            password="secret",
        )
        client = PrometheusClient("http://localhost:9090", config)

        assert client.auth_config.username == "admin"


class TestQueries:
    async def test_instant_query_success(self, prometheus_client):
        """Test successful instant query."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [
                    {
                        "metric": {"__name__": "up", "job": "prometheus"},
                        "value": [1234567890, "1"],
                    }
                ],
            },
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(prometheus_client, "_get_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_client

            result = await prometheus_client.query("up")

            assert result.status == MetricResultStatus.SUCCESS
            assert result.result_type == MetricResultType.VECTOR
            assert len(result.result) == 1
            assert result.result[0].metric == "up"

    async def test_query_auth_failure(self, prometheus_client):
        """Test query with authentication failure."""
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch.object(prometheus_client, "_get_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_client

            result = await prometheus_client.query("up")

            assert result.status == MetricResultStatus.ERROR
            assert "Authentication failed" in result.error

    async def test_query_authorization_failure(self, prometheus_client):
        """Test query with authorization failure."""
        mock_response = MagicMock()
        mock_response.status_code = 403

        with patch.object(prometheus_client, "_get_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_client

            result = await prometheus_client.query("up")

            assert result.status == MetricResultStatus.ERROR
            assert "Authorization failed" in result.error

    async def test_range_query_success(self, prometheus_client):
        """Test successful range query."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [
                    {
                        "metric": {"__name__": "up", "job": "prometheus"},
                        "values": [
                            [1234567890, "1"],
                            [1234567950, "1"],
                            [1234568010, "1"],
                        ],
                    }
                ],
            },
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(prometheus_client, "_get_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_client

            now = datetime.now(UTC)
            start = now.replace(hour=max(0, now.hour - 1))

            result = await prometheus_client.query_range("up", start, now, "1m")

            assert result.status == MetricResultStatus.SUCCESS
            assert result.result_type == MetricResultType.MATRIX
            assert len(result.result[0].values) == 3

    async def test_query_timeout(self, prometheus_client):
        """Test query timeout handling."""
        with patch.object(prometheus_client, "_get_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_get.return_value = mock_client

            result = await prometheus_client.query("up")

            assert result.status == MetricResultStatus.ERROR
            assert "timeout" in result.error.lower()


class TestHealthCheck:
    async def test_healthy(self, prometheus_client):
        """Test health check returns True when healthy."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(prometheus_client, "_get_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_client

            result = await prometheus_client.check_health()

            assert result is True

    async def test_unhealthy(self, prometheus_client):
        """Test health check returns False when unhealthy."""
        with patch.object(prometheus_client, "_get_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_get.return_value = mock_client

            result = await prometheus_client.check_health()

            assert result is False


class TestResultParsing:
    def test_parse_vector_result(self, prometheus_client):
        """Test parsing vector (instant) query result."""
        data = {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [
                    {
                        "metric": {"__name__": "up", "instance": "localhost:9090"},
                        "value": [1234567890.123, "1"],
                    }
                ],
            },
        }

        result = prometheus_client._parse_query_result(data)

        assert result.result_type == MetricResultType.VECTOR
        assert result.result[0].labels["instance"] == "localhost:9090"
        assert result.result[0].values[0]["value"] == 1.0

    def test_parse_matrix_result(self, prometheus_client):
        """Test parsing matrix (range) query result."""
        data = {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [
                    {
                        "metric": {"__name__": "up"},
                        "values": [
                            [1234567890, "1"],
                            [1234567950, "0.5"],
                        ],
                    }
                ],
            },
        }

        result = prometheus_client._parse_query_result(data)

        assert result.result_type == MetricResultType.MATRIX
        assert len(result.result[0].values) == 2
        assert result.result[0].values[1]["value"] == 0.5
