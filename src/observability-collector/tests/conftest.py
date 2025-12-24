"""Test fixtures for Observability Collector tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_redis():
    """Create mock Redis client."""
    redis = AsyncMock()
    redis.ping = AsyncMock(return_value=True)
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.keys = AsyncMock(return_value=[])
    redis.publish_event = AsyncMock(return_value=True)
    return redis


@pytest.fixture
def mock_cluster_registry():
    """Create mock Cluster Registry client."""
    client = AsyncMock()
    client.get_cluster = AsyncMock(return_value={
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "test-cluster",
        "endpoints": {
            "prometheus_url": "http://prometheus.test:9090",
        },
        "capabilities": {
            "has_gpu_nodes": True,
            "gpu_count": 4,
            "gpu_types": ["NVIDIA A100"],
        },
    })
    client.list_online_clusters = AsyncMock(return_value=[
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "name": "test-cluster",
            "endpoints": {
                "prometheus_url": "http://prometheus.test:9090",
            },
            "capabilities": {
                "has_gpu_nodes": True,
                "gpu_count": 4,
                "gpu_types": ["NVIDIA A100"],
            },
        }
    ])
    return client
