"""API Gateway Service main application.

Spec Reference: specs/06-api-gateway.md Section 3
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from shared.config import get_settings
from shared.observability import get_logger
from shared.redis_client import RedisClient

from .api import health, proxy
from .middleware.rate_limit import RateLimitMiddleware

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Handles startup and shutdown of shared resources.
    """
    settings = get_settings()

    logger.info(
        "Starting API Gateway service",
        version="0.1.0",
    )

    # Initialize Redis client for rate limiting
    redis = RedisClient(settings.redis.url)
    await redis.connect()
    app.state.redis = redis

    # Initialize HTTP client for proxying
    app.state.http_client = httpx.AsyncClient(timeout=60.0)

    # Backend service URLs
    app.state.backends = {
        "cluster-registry": settings.services.cluster_registry_url,
        "observability-collector": settings.services.observability_collector_url,
        "intelligence-engine": settings.services.intelligence_engine_url,
        "realtime-streaming": getattr(
            settings.services, "realtime_streaming_url",
            "http://realtime-streaming:8080"
        ),
    }

    logger.info(
        "API Gateway ready",
        backends=list(app.state.backends.keys()),
    )

    yield

    # Cleanup
    logger.info("Shutting down API Gateway service")
    await app.state.http_client.aclose()
    await redis.close()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="AIOps NextGen - API Gateway",
        description="Unified API entry point for all services",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS middleware
    # Spec Reference: specs/06-api-gateway.md Section 13
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.is_development else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiting middleware
    # Spec Reference: specs/06-api-gateway.md Section 7
    app.add_middleware(RateLimitMiddleware)

    # Include routers
    app.include_router(health.router, tags=["Health"])
    app.include_router(proxy.router, tags=["Proxy"])

    return app


app = create_app()
