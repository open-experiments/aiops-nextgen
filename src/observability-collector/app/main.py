"""Observability Collector Service main application.

Spec Reference: specs/03-observability-collector.md Section 3
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.config import get_settings
from shared.observability import get_logger
from shared.redis_client import RedisClient

from .api import alerts, gpu, health, metrics
from .clients.cluster_registry import ClusterRegistryClient

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Handles startup and shutdown of shared resources.
    """
    settings = get_settings()

    logger.info(
        "Starting Observability Collector service",
        version="0.1.0",
    )

    # Initialize Redis client
    redis = RedisClient(settings.redis.url)
    await redis.connect()
    app.state.redis = redis

    # Initialize Cluster Registry client
    cluster_registry_url = settings.services.cluster_registry_url
    cluster_registry = ClusterRegistryClient(cluster_registry_url)
    app.state.cluster_registry = cluster_registry

    logger.info("Observability Collector service started successfully")

    yield

    # Cleanup
    logger.info("Shutting down Observability Collector service")
    await redis.close()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="AIOps NextGen - Observability Collector",
        description="Federated metrics, traces, logs, and GPU telemetry collection",
        version="0.1.0",
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.is_development else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(health.router, tags=["Health"])
    app.include_router(metrics.router, prefix="/api/v1", tags=["Metrics"])
    app.include_router(alerts.router, prefix="/api/v1", tags=["Alerts"])
    app.include_router(gpu.router, prefix="/api/v1", tags=["GPU"])

    return app


app = create_app()
