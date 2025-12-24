"""Intelligence Engine Service - Main Application.

Spec Reference: specs/04-intelligence-engine.md

AI-powered analysis and chat with MCP tool calling.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.config import IntelligenceEngineSettings
from shared.observability import get_logger, setup_logging
from shared.redis_client import RedisClient

from .api import chat, health, personas
from .llm.router import LLMRouter
from .services.chat import ChatService
from .services.personas import PersonaService
from .tools.executor import ToolExecutor

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    settings = app.state.settings

    # Setup logging
    setup_logging(log_level=settings.log_level, log_format=settings.log_format)
    logger.info(
        "Starting Intelligence Engine",
        environment=settings.environment.value if hasattr(settings.environment, 'value') else settings.environment,
        llm_provider=settings.llm.provider.value if hasattr(settings.llm.provider, 'value') else settings.llm.provider,
    )

    # Initialize Redis
    redis = RedisClient(settings.redis.url)
    await redis.connect()
    app.state.redis = redis

    # Initialize LLM Router
    llm_router = LLMRouter(settings.llm)
    app.state.llm_router = llm_router

    # Initialize services
    persona_service = PersonaService()
    app.state.persona_service = persona_service

    tool_executor = ToolExecutor(settings.services)
    app.state.tool_executor = tool_executor

    chat_service = ChatService(
        redis=redis,
        llm_router=llm_router,
        tool_executor=tool_executor,
        persona_service=persona_service,
    )
    app.state.chat_service = chat_service

    logger.info("Intelligence Engine ready")

    yield

    # Cleanup
    logger.info("Shutting down Intelligence Engine")
    await redis.close()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = IntelligenceEngineSettings()

    app = FastAPI(
        title="Intelligence Engine",
        description="AI-powered analysis and chat for AIOps NextGen",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Store settings
    app.state.settings = settings

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(personas.router)

    return app


app = create_app()
