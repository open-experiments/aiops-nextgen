# Sprint 10: API Gateway Polish

**Issues Addressed:** ISSUE-018 (MEDIUM), ISSUE-019 (MEDIUM), ISSUE-021 (LOW), ISSUE-022 (LOW)
**Priority:** P2
**Dependencies:** All previous sprints

---

## Overview

This sprint polishes the API Gateway with chat persistence, health aggregation, request validation, and distributed tracing. These are the final improvements needed for production readiness.

---

## Task 10.1: Chat Session Persistence

**File:** `src/intelligence-engine/services/chat_persistence.py`

### Implementation

```python
"""Chat Session Persistence Service.

Spec Reference: specs/04-intelligence-engine.md Section 2.2

Persists chat sessions and messages to PostgreSQL for:
- Session continuity across restarts
- Conversation history access
- Analytics and auditing
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_async_session
from shared.models import ChatSession, ChatMessage, MessageRole
from shared.observability import get_logger

logger = get_logger(__name__)


# SQLAlchemy ORM Models

from sqlalchemy import Column, String, DateTime, Text, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from shared.database import Base


class ChatSessionORM(Base):
    """Chat session database model."""

    __tablename__ = "chat_sessions"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(255), nullable=False, index=True)
    persona = Column(String(50), nullable=False, default="telco_expert")
    title = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    metadata = Column(JSON, nullable=True)

    messages = relationship("ChatMessageORM", back_populates="session", cascade="all, delete-orphan")


class ChatMessageORM(Base):
    """Chat message database model."""

    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True)
    session_id = Column(String(36), ForeignKey("chat_sessions.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user, assistant, system, tool
    content = Column(Text, nullable=False)
    tool_calls = Column(JSON, nullable=True)
    tool_results = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    metadata = Column(JSON, nullable=True)

    session = relationship("ChatSessionORM", back_populates="messages")


class ChatPersistenceService:
    """Service for persisting chat sessions and messages."""

    async def create_session(
        self,
        user_id: str,
        persona: str = "telco_expert",
        title: Optional[str] = None,
    ) -> ChatSession:
        """Create a new chat session.

        Args:
            user_id: User identifier
            persona: AI persona to use
            title: Optional session title

        Returns:
            Created ChatSession
        """
        session_id = str(uuid4())
        now = datetime.now(timezone.utc)

        async with get_async_session() as db:
            session_orm = ChatSessionORM(
                id=session_id,
                user_id=user_id,
                persona=persona,
                title=title or f"Chat {now.strftime('%Y-%m-%d %H:%M')}",
                created_at=now,
                updated_at=now,
            )

            db.add(session_orm)
            await db.commit()

            logger.info(
                "Chat session created",
                session_id=session_id,
                user_id=user_id,
            )

            return ChatSession(
                id=session_id,
                user_id=user_id,
                persona=persona,
                title=session_orm.title,
                created_at=now,
                updated_at=now,
                messages=[],
            )

    async def get_session(
        self,
        session_id: str,
        include_messages: bool = True,
    ) -> Optional[ChatSession]:
        """Get a chat session by ID.

        Args:
            session_id: Session identifier
            include_messages: Whether to include message history

        Returns:
            ChatSession or None if not found
        """
        async with get_async_session() as db:
            result = await db.execute(
                select(ChatSessionORM).where(ChatSessionORM.id == session_id)
            )
            session_orm = result.scalar_one_or_none()

            if not session_orm:
                return None

            messages = []
            if include_messages:
                msg_result = await db.execute(
                    select(ChatMessageORM)
                    .where(ChatMessageORM.session_id == session_id)
                    .order_by(ChatMessageORM.created_at)
                )
                for msg_orm in msg_result.scalars():
                    messages.append(
                        ChatMessage(
                            id=msg_orm.id,
                            session_id=msg_orm.session_id,
                            role=MessageRole(msg_orm.role),
                            content=msg_orm.content,
                            tool_calls=msg_orm.tool_calls,
                            tool_results=msg_orm.tool_results,
                            created_at=msg_orm.created_at,
                        )
                    )

            return ChatSession(
                id=session_orm.id,
                user_id=session_orm.user_id,
                persona=session_orm.persona,
                title=session_orm.title,
                created_at=session_orm.created_at,
                updated_at=session_orm.updated_at,
                messages=messages,
            )

    async def list_sessions(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> list[ChatSession]:
        """List chat sessions for a user.

        Args:
            user_id: User identifier
            limit: Maximum sessions to return
            offset: Pagination offset

        Returns:
            List of ChatSession objects (without messages)
        """
        async with get_async_session() as db:
            result = await db.execute(
                select(ChatSessionORM)
                .where(ChatSessionORM.user_id == user_id)
                .order_by(ChatSessionORM.updated_at.desc())
                .limit(limit)
                .offset(offset)
            )

            sessions = []
            for session_orm in result.scalars():
                sessions.append(
                    ChatSession(
                        id=session_orm.id,
                        user_id=session_orm.user_id,
                        persona=session_orm.persona,
                        title=session_orm.title,
                        created_at=session_orm.created_at,
                        updated_at=session_orm.updated_at,
                        messages=[],
                    )
                )

            return sessions

    async def add_message(
        self,
        session_id: str,
        role: MessageRole,
        content: str,
        tool_calls: Optional[list] = None,
        tool_results: Optional[list] = None,
    ) -> ChatMessage:
        """Add a message to a session.

        Args:
            session_id: Session identifier
            role: Message role
            content: Message content
            tool_calls: Optional tool calls made
            tool_results: Optional tool results received

        Returns:
            Created ChatMessage
        """
        message_id = str(uuid4())
        now = datetime.now(timezone.utc)

        async with get_async_session() as db:
            message_orm = ChatMessageORM(
                id=message_id,
                session_id=session_id,
                role=role.value,
                content=content,
                tool_calls=tool_calls,
                tool_results=tool_results,
                created_at=now,
            )

            db.add(message_orm)

            # Update session updated_at
            await db.execute(
                update(ChatSessionORM)
                .where(ChatSessionORM.id == session_id)
                .values(updated_at=now)
            )

            await db.commit()

            return ChatMessage(
                id=message_id,
                session_id=session_id,
                role=role,
                content=content,
                tool_calls=tool_calls,
                tool_results=tool_results,
                created_at=now,
            )

    async def delete_session(self, session_id: str) -> bool:
        """Delete a chat session.

        Args:
            session_id: Session identifier

        Returns:
            True if deleted, False if not found
        """
        async with get_async_session() as db:
            result = await db.execute(
                delete(ChatSessionORM).where(ChatSessionORM.id == session_id)
            )
            await db.commit()

            deleted = result.rowcount > 0

            if deleted:
                logger.info("Chat session deleted", session_id=session_id)

            return deleted

    async def update_session_title(
        self,
        session_id: str,
        title: str,
    ) -> bool:
        """Update session title.

        Args:
            session_id: Session identifier
            title: New title

        Returns:
            True if updated
        """
        async with get_async_session() as db:
            result = await db.execute(
                update(ChatSessionORM)
                .where(ChatSessionORM.id == session_id)
                .values(title=title, updated_at=datetime.now(timezone.utc))
            )
            await db.commit()

            return result.rowcount > 0


# Singleton instance
chat_persistence = ChatPersistenceService()
```

### Database Migration

**File:** `migrations/versions/002_chat_tables.py`

```python
"""Add chat session tables.

Revision ID: 002
Revises: 001
Create Date: 2024-01-15
"""

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"


def upgrade():
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(255), nullable=False, index=True),
        sa.Column("persona", sa.String(50), nullable=False, default="telco_expert"),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", sa.JSON, nullable=True),
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("chat_sessions.id"), nullable=False, index=True),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("tool_calls", sa.JSON, nullable=True),
        sa.Column("tool_results", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", sa.JSON, nullable=True),
    )


def downgrade():
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
```

---

## Task 10.2: Health Aggregation Service

**File:** `src/api-gateway/services/health_aggregator.py`

### Implementation

```python
"""Health Aggregation Service.

Spec Reference: specs/06-api-gateway.md Section 6

Aggregates health status from all microservices.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional

import httpx
from pydantic import BaseModel

from shared.config import get_settings
from shared.observability import get_logger

logger = get_logger(__name__)


class ServiceHealth(BaseModel):
    """Health status of a single service."""

    name: str
    status: str  # healthy, degraded, unhealthy
    latency_ms: float
    last_check: datetime
    details: Optional[dict] = None


class AggregatedHealth(BaseModel):
    """Aggregated health of all services."""

    status: str  # healthy, degraded, unhealthy
    services: list[ServiceHealth]
    healthy_count: int
    unhealthy_count: int
    checked_at: datetime


class HealthAggregator:
    """Aggregates health from all services."""

    def __init__(self):
        self.settings = get_settings()
        self._services = {
            "cluster-registry": self.settings.services.cluster_registry_url,
            "observability-collector": self.settings.services.observability_collector_url,
            "intelligence-engine": self.settings.services.intelligence_engine_url,
            "realtime-streaming": self.settings.services.realtime_streaming_url,
        }

    async def check_health(self) -> AggregatedHealth:
        """Check health of all services.

        Returns:
            AggregatedHealth with all service statuses
        """
        tasks = [
            self._check_service(name, url)
            for name, url in self._services.items()
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        services = []
        healthy_count = 0
        unhealthy_count = 0

        for i, result in enumerate(results):
            service_name = list(self._services.keys())[i]

            if isinstance(result, Exception):
                services.append(
                    ServiceHealth(
                        name=service_name,
                        status="unhealthy",
                        latency_ms=-1,
                        last_check=datetime.now(timezone.utc),
                        details={"error": str(result)},
                    )
                )
                unhealthy_count += 1
            else:
                services.append(result)
                if result.status == "healthy":
                    healthy_count += 1
                else:
                    unhealthy_count += 1

        # Determine overall status
        if unhealthy_count == 0:
            overall_status = "healthy"
        elif healthy_count == 0:
            overall_status = "unhealthy"
        else:
            overall_status = "degraded"

        return AggregatedHealth(
            status=overall_status,
            services=services,
            healthy_count=healthy_count,
            unhealthy_count=unhealthy_count,
            checked_at=datetime.now(timezone.utc),
        )

    async def _check_service(
        self,
        name: str,
        url: str,
    ) -> ServiceHealth:
        """Check health of a single service.

        Args:
            name: Service name
            url: Service URL

        Returns:
            ServiceHealth for the service
        """
        health_url = f"{url.rstrip('/')}/health"

        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(health_url)

                latency = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

                if response.status_code == 200:
                    details = None
                    try:
                        details = response.json()
                    except Exception:
                        pass

                    return ServiceHealth(
                        name=name,
                        status="healthy",
                        latency_ms=round(latency, 2),
                        last_check=datetime.now(timezone.utc),
                        details=details,
                    )
                else:
                    return ServiceHealth(
                        name=name,
                        status="unhealthy",
                        latency_ms=round(latency, 2),
                        last_check=datetime.now(timezone.utc),
                        details={"status_code": response.status_code},
                    )

        except httpx.TimeoutException:
            return ServiceHealth(
                name=name,
                status="unhealthy",
                latency_ms=-1,
                last_check=datetime.now(timezone.utc),
                details={"error": "timeout"},
            )

        except httpx.ConnectError as e:
            return ServiceHealth(
                name=name,
                status="unhealthy",
                latency_ms=-1,
                last_check=datetime.now(timezone.utc),
                details={"error": f"connection failed: {str(e)}"},
            )


# Singleton instance
health_aggregator = HealthAggregator()
```

---

## Task 10.3: Request Validation Middleware

**File:** `src/api-gateway/middleware/validation.py`

### Implementation

```python
"""Request Validation Middleware.

Spec Reference: specs/06-api-gateway.md Section 5.2

Validates incoming requests:
- Content-Type headers
- Request body size limits
- Required headers
- JSON schema validation
"""

from typing import Optional

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware

from shared.observability import get_logger

logger = get_logger(__name__)

MAX_BODY_SIZE = 10 * 1024 * 1024  # 10 MB
REQUIRED_HEADERS = ["user-agent"]


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """Validates incoming HTTP requests."""

    async def dispatch(self, request: Request, call_next):
        """Validate request before processing."""
        # Skip validation for certain paths
        skip_paths = ["/health", "/ready", "/metrics", "/docs", "/openapi.json"]

        if request.url.path in skip_paths:
            return await call_next(request)

        try:
            # Validate content type for POST/PUT/PATCH
            if request.method in ["POST", "PUT", "PATCH"]:
                content_type = request.headers.get("content-type", "")

                if not content_type:
                    raise HTTPException(
                        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                        detail="Content-Type header is required",
                    )

                # Allow JSON and form data
                valid_types = [
                    "application/json",
                    "multipart/form-data",
                    "application/x-www-form-urlencoded",
                ]

                if not any(ct in content_type for ct in valid_types):
                    raise HTTPException(
                        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                        detail=f"Unsupported Content-Type: {content_type}",
                    )

            # Validate content length
            content_length = request.headers.get("content-length")
            if content_length:
                if int(content_length) > MAX_BODY_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Request body too large. Max size: {MAX_BODY_SIZE} bytes",
                    )

            # Validate required headers
            for header in REQUIRED_HEADERS:
                if not request.headers.get(header):
                    logger.warning(
                        "Missing required header",
                        header=header,
                        path=request.url.path,
                    )
                    # Don't reject, just log for now

            # Validate JSON body if present
            if request.method in ["POST", "PUT", "PATCH"]:
                content_type = request.headers.get("content-type", "")
                if "application/json" in content_type:
                    try:
                        body = await request.body()
                        if body:
                            import json
                            json.loads(body)
                    except json.JSONDecodeError as e:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Invalid JSON: {str(e)}",
                        )

        except HTTPException:
            raise
        except Exception as e:
            logger.error("Request validation error", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Request validation failed",
            )

        return await call_next(request)
```

---

## Task 10.4: Distributed Tracing

**File:** `src/shared/observability/tracing.py`

### Implementation

```python
"""Distributed Tracing with OpenTelemetry.

Spec Reference: specs/09-deployment.md Section 8.1

Implements distributed tracing across all services.
"""

from typing import Optional
import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.b3 import B3MultiFormat

from shared.config import get_settings
from shared.observability import get_logger

logger = get_logger(__name__)


class TracingConfig:
    """Tracing configuration."""

    def __init__(
        self,
        service_name: str,
        service_version: str = "0.1.0",
        enabled: bool = True,
        endpoint: Optional[str] = None,
    ):
        self.service_name = service_name
        self.service_version = service_version
        self.enabled = enabled
        self.endpoint = endpoint or get_settings().observability.otel_exporter_endpoint


def setup_tracing(config: TracingConfig) -> Optional[TracerProvider]:
    """Setup OpenTelemetry tracing.

    Args:
        config: Tracing configuration

    Returns:
        TracerProvider if enabled, None otherwise
    """
    if not config.enabled:
        logger.info("Tracing disabled")
        return None

    # Create resource with service info
    resource = Resource.create({
        "service.name": config.service_name,
        "service.version": config.service_version,
        "deployment.environment": os.getenv("ENV", "development"),
    })

    # Create tracer provider
    provider = TracerProvider(resource=resource)

    # Add OTLP exporter
    try:
        exporter = OTLPSpanExporter(
            endpoint=config.endpoint,
            insecure=True,  # Use insecure for local development
        )
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)

        logger.info(
            "OTLP exporter configured",
            endpoint=config.endpoint,
        )
    except Exception as e:
        logger.warning(
            "Failed to configure OTLP exporter",
            error=str(e),
        )

    # Set as global provider
    trace.set_tracer_provider(provider)

    # Set B3 propagation for cross-service tracing
    set_global_textmap(B3MultiFormat())

    logger.info(
        "Tracing initialized",
        service=config.service_name,
    )

    return provider


def instrument_fastapi(app, service_name: str):
    """Instrument FastAPI application.

    Args:
        app: FastAPI application
        service_name: Service name for spans
    """
    FastAPIInstrumentor.instrument_app(
        app,
        server_request_hook=_server_request_hook,
        client_request_hook=_client_request_hook,
        client_response_hook=_client_response_hook,
    )

    logger.info("FastAPI instrumented for tracing")


def instrument_httpx():
    """Instrument HTTPX client."""
    HTTPXClientInstrumentor().instrument()
    logger.info("HTTPX instrumented for tracing")


def instrument_sqlalchemy(engine):
    """Instrument SQLAlchemy.

    Args:
        engine: SQLAlchemy engine
    """
    SQLAlchemyInstrumentor().instrument(engine=engine)
    logger.info("SQLAlchemy instrumented for tracing")


def instrument_redis():
    """Instrument Redis client."""
    RedisInstrumentor().instrument()
    logger.info("Redis instrumented for tracing")


def _server_request_hook(span, scope):
    """Hook for incoming requests."""
    if span and span.is_recording():
        # Add custom attributes
        span.set_attribute("http.request.id", scope.get("request_id", ""))


def _client_request_hook(span, request):
    """Hook for outgoing requests."""
    if span and span.is_recording():
        span.set_attribute("http.client", "httpx")


def _client_response_hook(span, request, response):
    """Hook for response received."""
    if span and span.is_recording():
        span.set_attribute("http.response.size", len(response.content) if response.content else 0)


def get_tracer(name: str) -> trace.Tracer:
    """Get a tracer instance.

    Args:
        name: Tracer name (usually __name__)

    Returns:
        Tracer instance
    """
    return trace.get_tracer(name)


def create_span(
    tracer: trace.Tracer,
    name: str,
    attributes: Optional[dict] = None,
):
    """Create a new span.

    Args:
        tracer: Tracer instance
        name: Span name
        attributes: Optional span attributes

    Returns:
        Span context manager
    """
    return tracer.start_as_current_span(
        name,
        attributes=attributes,
    )
```

---

## Task 10.5: Update Main Applications

**File:** `src/api-gateway/main.py` (UPDATE)

```python
# Add to imports
from middleware.validation import RequestValidationMiddleware
from services.health_aggregator import health_aggregator
from shared.observability.tracing import setup_tracing, instrument_fastapi, TracingConfig

# After app creation
app = FastAPI(...)

# Setup tracing
tracing_config = TracingConfig(
    service_name="api-gateway",
    enabled=settings.observability.tracing_enabled,
)
setup_tracing(tracing_config)
instrument_fastapi(app, "api-gateway")

# Add middlewares (order matters - validation before auth)
app.add_middleware(RequestValidationMiddleware)
app.add_middleware(AuthenticationMiddleware)

# Health endpoint with aggregation
@app.get("/health/all")
async def health_all():
    """Get aggregated health of all services."""
    return await health_aggregator.check_health()
```

---

## Acceptance Criteria

- [ ] Chat sessions persisted to PostgreSQL
- [ ] Chat messages stored with full context
- [ ] Session listing with pagination works
- [ ] Health aggregation checks all services
- [ ] Overall status derived from component health
- [ ] Request validation rejects invalid content-type
- [ ] Request validation enforces body size limits
- [ ] Invalid JSON bodies rejected with clear error
- [ ] OpenTelemetry tracing configured
- [ ] Traces exported to OTLP endpoint
- [ ] Cross-service trace propagation via B3 headers
- [ ] All tests pass with >80% coverage

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `src/intelligence-engine/services/chat_persistence.py` | CREATE | Chat persistence service |
| `migrations/versions/002_chat_tables.py` | CREATE | Chat tables migration |
| `src/api-gateway/services/health_aggregator.py` | CREATE | Health aggregation |
| `src/api-gateway/middleware/validation.py` | CREATE | Request validation |
| `src/shared/observability/tracing.py` | CREATE | Distributed tracing |
| `src/api-gateway/main.py` | MODIFY | Add middlewares and tracing |
| `src/*/main.py` | MODIFY | Add tracing to all services |
| `src/intelligence-engine/tests/test_chat_persistence.py` | CREATE | Persistence tests |
| `src/api-gateway/tests/test_health_aggregator.py` | CREATE | Aggregator tests |
| `src/api-gateway/tests/test_validation.py` | CREATE | Validation tests |

---

## Dependencies

### Python packages

Already in pyproject.toml:
- `opentelemetry-api`
- `opentelemetry-sdk`
- `opentelemetry-instrumentation-fastapi`
- `opentelemetry-instrumentation-sqlalchemy`
- `opentelemetry-instrumentation-redis`
- `opentelemetry-exporter-otlp`

Add:
```toml
dependencies = [
    "opentelemetry-instrumentation-httpx>=0.42b0",
    "opentelemetry-propagator-b3>=1.21.0",
]
```

---

## Final Checklist

After completing all 10 sprints:

- [ ] All 23 issues resolved
- [ ] OAuth authentication functional
- [ ] RBAC authorization enforced
- [ ] Credentials in K8s Secrets
- [ ] Real GPU telemetry collection
- [ ] Prometheus/Loki/Tempo authentication
- [ ] CNF monitoring operational
- [ ] WebSocket hardening complete
- [ ] Anomaly detection and RCA functional
- [ ] All MCP tools implemented
- [ ] Reports generation working
- [ ] Chat persistence active
- [ ] Health aggregation working
- [ ] Request validation in place
- [ ] Distributed tracing operational

---

## Post-Sprint Activities

1. **Integration Testing**: Run full E2E tests across all services
2. **Performance Testing**: Load test with realistic workloads
3. **Security Audit**: Penetration testing and security review
4. **Documentation Update**: Update README and API docs
5. **Deployment Prep**: Update Helm charts and configurations
