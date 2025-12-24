"""Test fixtures for Cluster Registry.

Spec Reference: specs/02-cluster-registry.md
"""

import asyncio
from typing import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from shared.database import Base
from shared.redis_client import RedisClient


# Use SQLite for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    # Create tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    # Drop tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


class MockRedisClient:
    """Mock Redis client for testing."""

    def __init__(self):
        self._data = {}
        self._channels = {}

    async def connect(self):
        pass

    async def disconnect(self):
        pass

    async def ping(self):
        return True

    async def get(self, key: str):
        return self._data.get(key)

    async def set(self, key: str, value: str, ex: int = None):
        self._data[key] = value

    async def delete(self, key: str):
        if key in self._data:
            del self._data[key]

    async def publish(self, channel: str, message: dict):
        if channel not in self._channels:
            self._channels[channel] = []
        self._channels[channel].append(message)


@pytest.fixture
def mock_redis():
    """Create mock Redis client."""
    return MockRedisClient()


@pytest_asyncio.fixture
async def test_client(test_engine, mock_redis) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client."""
    from app.main import app

    # Create tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Override app state
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    app.state.db_engine = test_engine
    app.state.session_factory = session_factory
    app.state.redis = mock_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    # Cleanup
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def sample_cluster_data():
    """Sample cluster data for testing."""
    return {
        "name": "test-cluster-01",
        "display_name": "Test Cluster 01",
        "api_server_url": "https://api.test-cluster-01.example.com:6443",
        "cluster_type": "SPOKE",
        "platform": "OPENSHIFT",
        "region": "us-east-1",
        "environment": "DEVELOPMENT",
        "labels": {"team": "platform", "env": "test"},
        "endpoints": {
            "prometheus_url": "https://prometheus.test-cluster-01.example.com:9090"
        },
    }
