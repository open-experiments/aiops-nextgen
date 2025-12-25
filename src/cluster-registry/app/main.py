"""Cluster Registry FastAPI Application.

Spec Reference: specs/02-cluster-registry.md Section 3

The Cluster Registry Service provides:
- CRUD operations for cluster registration
- Secure credential storage and rotation
- Continuous health monitoring
- Capability discovery (GPU, CNF, observability stack)
- Event emission for cluster state changes
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.config import ClusterRegistrySettings
from shared.database import create_engine, create_session_factory
from shared.observability import setup_logging, get_logger
from shared.redis_client import RedisClient

from .api import clusters, fleet, health
from .services.health_service import HealthService

settings = ClusterRegistrySettings()
setup_logging(log_level=settings.log_level, log_format=settings.log_format)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Handles startup and shutdown of:
    - Database connections
    - Redis connections
    - Background health check task
    """
    logger.info("Starting Cluster Registry service", version=settings.app_version)

    # Initialize database
    engine = create_engine(settings.database.async_url, echo=settings.debug)
    session_factory = create_session_factory(engine)
    app.state.db_engine = engine
    app.state.session_factory = session_factory

    # Create tables if they don't exist
    from shared.database import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized")

    # Initialize Redis
    redis_client = RedisClient(settings.redis.url)
    await redis_client.connect()
    app.state.redis = redis_client

    # Start background health check task
    health_service = HealthService(session_factory, redis_client, settings)
    app.state.health_service = health_service
    health_task = asyncio.create_task(health_service.run_periodic_checks())
    app.state.health_task = health_task

    logger.info("Cluster Registry service started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Cluster Registry service")
    health_task.cancel()
    try:
        await health_task
    except asyncio.CancelledError:
        pass
    await redis_client.disconnect()
    await engine.dispose()
    logger.info("Cluster Registry service shutdown complete")


app = FastAPI(
    title="Cluster Registry Service",
    description="Authoritative source for managed cluster metadata, credentials, and health status",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configured via API Gateway in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
# Spec Reference: specs/02-cluster-registry.md Section 4.1
app.include_router(clusters.router, prefix="/api/v1", tags=["Clusters"])
app.include_router(fleet.router, prefix="/api/v1", tags=["Fleet"])
app.include_router(health.router, tags=["Health"])


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "cluster-registry",
        "version": settings.app_version,
        "docs": "/docs",
    }
