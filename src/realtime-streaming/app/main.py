"""Real-Time Streaming Service main application.

Spec Reference: specs/05-realtime-streaming.md Section 3
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.config import get_settings
from shared.observability import get_logger
from shared.redis_client import RedisClient

from .api import health, streaming, websocket
from .services.event_router import EventRouter
from .services.hub import WebSocketHub
from .services.subscriptions import SubscriptionManager

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Handles startup and shutdown of shared resources.
    """
    settings = get_settings()

    logger.info(
        "Starting Real-Time Streaming service",
        version="0.1.0",
    )

    # Initialize Redis client
    redis = RedisClient(settings.redis.url)
    await redis.connect()
    app.state.redis = redis

    # Initialize WebSocket hub
    hub = WebSocketHub()
    app.state.hub = hub

    # Initialize subscription manager
    subscription_manager = SubscriptionManager()
    app.state.subscription_manager = subscription_manager

    # Initialize event router
    event_router = EventRouter(redis, hub, subscription_manager)
    app.state.event_router = event_router

    # Start event router background task
    router_task = asyncio.create_task(event_router.start())
    app.state.router_task = router_task

    logger.info("Real-Time Streaming service ready")

    yield

    # Cleanup
    logger.info("Shutting down Real-Time Streaming service")
    await event_router.stop()
    router_task.cancel()
    try:
        await router_task
    except asyncio.CancelledError:
        pass
    await redis.close()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="AIOps NextGen - Real-Time Streaming",
        description="WebSocket-based real-time event streaming",
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
    app.include_router(streaming.router, prefix="/api/v1", tags=["Streaming"])
    app.include_router(websocket.router, tags=["WebSocket"])

    return app


app = create_app()
