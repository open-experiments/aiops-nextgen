"""Pytest configuration and shared fixtures.

Spec Reference: Development testing infrastructure
"""

import asyncio
import os
from collections.abc import AsyncGenerator, Generator
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Set test environment before importing settings
os.environ["ENV"] = "development"
os.environ["LOG_LEVEL"] = "DEBUG"
os.environ["LOG_FORMAT"] = "text"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_cluster_data() -> dict[str, Any]:
    """Sample cluster data for testing."""
    return {
        "id": str(uuid4()),
        "name": "test-cluster-01",
        "display_name": "Test Cluster 01",
        "api_server_url": "https://api.test-cluster.example.com:6443",
        "cluster_type": "SPOKE",
        "platform": "OPENSHIFT",
        "platform_version": "4.16.0",
        "region": "us-east-1",
        "environment": "DEVELOPMENT",
        "labels": {"team": "platform", "cost-center": "engineering"},
        "endpoints": {
            "prometheus": "https://prometheus.test-cluster.example.com",
            "tempo": "https://tempo.test-cluster.example.com",
        },
        "capabilities": {"gpu": False, "observability": True},
        "status": {"state": "ONLINE", "message": "Cluster is healthy"},
    }


@pytest.fixture
def sample_chat_session_data() -> dict[str, Any]:
    """Sample chat session data for testing."""
    return {
        "id": str(uuid4()),
        "user_id": "test-user@example.com",
        "title": "Test Chat Session",
        "persona_id": "kubernetes-expert",
        "cluster_context": [str(uuid4())],
        "message_count": 0,
    }


@pytest.fixture
def sample_event_data() -> dict[str, Any]:
    """Sample event data for testing."""
    return {
        "event_id": str(uuid4()),
        "event_type": "CLUSTER_REGISTERED",
        "source": "cluster-registry",
        "cluster_id": str(uuid4()),
        "payload": {"name": "new-cluster"},
    }


@pytest.fixture
def mock_settings() -> dict[str, Any]:
    """Mock settings for testing."""
    return {
        "app_name": "aiops-nextgen-test",
        "environment": "development",
        "log_level": "DEBUG",
        "log_format": "text",
        "database": {
            "host": "localhost",
            "port": 5432,
            "user": "aiops",
            "password": "test_password",
            "database": "aiops_test",
        },
        "redis": {
            "host": "localhost",
            "port": 6379,
        },
    }


# =============================================================================
# Markers
# =============================================================================


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests (no external dependencies)")
    config.addinivalue_line(
        "markers", "integration: Integration tests (require external services)"
    )
    config.addinivalue_line("markers", "slow: Slow tests")
