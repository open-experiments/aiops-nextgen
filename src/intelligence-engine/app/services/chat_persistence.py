"""Chat Persistence Service with PostgreSQL.

Spec Reference: specs/04-intelligence-engine.md Section 4.1

Implements chat session persistence:
- PostgreSQL as source of truth
- Redis as cache layer
- Async SQLAlchemy integration
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select

from shared.database.models import ChatMessageModel, ChatSessionModel
from shared.models.intelligence import (
    ChatMessage,
    ChatSession,
    MessageRole,
    ToolCall,
    ToolResult,
    ToolResultStatus,
)
from shared.observability import get_logger
from shared.redis_client import RedisClient

logger = get_logger(__name__)


class ChatPersistenceService:
    """Service for persisting chat sessions to PostgreSQL.

    Uses write-through caching strategy:
    - Writes go to both PostgreSQL and Redis
    - Reads check Redis first, fall back to PostgreSQL
    """

    CACHE_TTL_SECONDS = 3600  # 1 hour cache

    def __init__(
        self,
        session_factory,
        redis: RedisClient | None = None,
    ):
        """Initialize persistence service.

        Args:
            session_factory: SQLAlchemy async session factory
            redis: Optional Redis client for caching
        """
        self.session_factory = session_factory
        self.redis = redis

    async def save_session(self, session: ChatSession) -> ChatSession:
        """Save chat session to PostgreSQL.

        Args:
            session: ChatSession to save

        Returns:
            Saved ChatSession
        """
        async with self.session_factory() as db:
            # Check if session exists
            existing = await db.get(ChatSessionModel, session.id)

            if existing:
                # Update existing
                existing.title = session.title
                existing.persona_id = session.persona_id
                existing.cluster_context = (
                    [str(c) for c in session.cluster_context] if session.cluster_context else []
                )
                existing.message_count = session.message_count
                existing.updated_at = datetime.utcnow()
                existing.expires_at = session.expires_at
            else:
                # Create new
                cluster_ctx = (
                    [str(c) for c in session.cluster_context] if session.cluster_context else []
                )
                db_session = ChatSessionModel(
                    id=session.id,
                    user_id=session.user_id,
                    title=session.title,
                    persona_id=session.persona_id,
                    cluster_context=cluster_ctx,
                    message_count=session.message_count,
                    created_at=session.created_at,
                    updated_at=session.updated_at,
                    expires_at=session.expires_at,
                )
                db.add(db_session)

            await db.commit()

        # Update cache
        if self.redis:
            await self._cache_session(session)

        logger.debug("Session saved to PostgreSQL", session_id=str(session.id))
        return session

    async def get_session(self, session_id: UUID) -> ChatSession | None:
        """Get chat session by ID.

        Checks cache first, falls back to PostgreSQL.

        Args:
            session_id: Session ID to fetch

        Returns:
            ChatSession if found, None otherwise
        """
        # Try cache first
        if self.redis:
            cached = await self._get_cached_session(session_id)
            if cached:
                return cached

        # Fall back to PostgreSQL
        async with self.session_factory() as db:
            result = await db.get(ChatSessionModel, session_id)
            if result:
                session = self._model_to_session(result)
                # Update cache
                if self.redis:
                    await self._cache_session(session)
                return session

        return None

    async def list_sessions(self, user_id: str, limit: int = 50) -> list[ChatSession]:
        """List sessions for a user.

        Args:
            user_id: User ID to filter by
            limit: Maximum number of sessions to return

        Returns:
            List of ChatSessions
        """
        async with self.session_factory() as db:
            stmt = (
                select(ChatSessionModel)
                .where(ChatSessionModel.user_id == user_id)
                .order_by(ChatSessionModel.created_at.desc())
                .limit(limit)
            )
            result = await db.execute(stmt)
            models = result.scalars().all()
            return [self._model_to_session(m) for m in models]

    async def delete_session(self, session_id: UUID) -> bool:
        """Delete a chat session.

        Args:
            session_id: Session ID to delete

        Returns:
            True if deleted, False if not found
        """
        async with self.session_factory() as db:
            result = await db.get(ChatSessionModel, session_id)
            if result:
                await db.delete(result)
                await db.commit()

                # Clear cache
                if self.redis:
                    await self.redis.cache_delete("chat_sessions", str(session_id))
                    await self.redis.cache_delete("chat_messages", str(session_id))

                logger.info("Session deleted", session_id=str(session_id))
                return True
        return False

    async def save_message(self, message: ChatMessage) -> ChatMessage:
        """Save chat message to PostgreSQL.

        Args:
            message: ChatMessage to save

        Returns:
            Saved ChatMessage
        """
        async with self.session_factory() as db:
            # Convert tool_calls and tool_results to dicts
            tool_calls_data = []
            for tc in message.tool_calls or []:
                if isinstance(tc, ToolCall):
                    tool_calls_data.append(tc.model_dump())
                else:
                    tool_calls_data.append(tc)

            tool_results_data = []
            for tr in message.tool_results or []:
                if isinstance(tr, ToolResult):
                    data = tr.model_dump()
                    # Convert enum to string
                    if isinstance(data.get("status"), ToolResultStatus):
                        data["status"] = data["status"].value
                    tool_results_data.append(data)
                else:
                    tool_results_data.append(tr)

            db_message = ChatMessageModel(
                id=message.id,
                session_id=message.session_id,
                role=message.role.value if isinstance(message.role, MessageRole) else message.role,
                content=message.content,
                persona_id=message.persona_id,
                tool_calls=tool_calls_data,
                tool_results=tool_results_data,
                model=message.model,
                tokens_used=message.tokens_used,
                latency_ms=message.latency_ms,
                created_at=message.created_at,
            )
            db.add(db_message)
            await db.commit()

        # Update message cache for session
        if self.redis:
            await self._append_message_to_cache(message)

        logger.debug("Message saved to PostgreSQL", message_id=str(message.id))
        return message

    async def get_messages(
        self,
        session_id: UUID,
        limit: int = 100,
    ) -> list[ChatMessage]:
        """Get messages for a session.

        Args:
            session_id: Session ID to fetch messages for
            limit: Maximum number of messages to return

        Returns:
            List of ChatMessages
        """
        # Try cache first
        if self.redis:
            cached = await self._get_cached_messages(session_id)
            if cached:
                return cached[-limit:] if len(cached) > limit else cached

        # Fall back to PostgreSQL
        async with self.session_factory() as db:
            stmt = (
                select(ChatMessageModel)
                .where(ChatMessageModel.session_id == session_id)
                .order_by(ChatMessageModel.created_at.asc())
                .limit(limit)
            )
            result = await db.execute(stmt)
            models = result.scalars().all()
            messages = [self._model_to_message(m) for m in models]

            # Update cache
            if self.redis and messages:
                await self._cache_messages(session_id, messages)

            return messages

    def _model_to_session(self, model: ChatSessionModel) -> ChatSession:
        """Convert SQLAlchemy model to Pydantic model."""
        cluster_context = []
        if model.cluster_context:
            cluster_context = [UUID(c) if isinstance(c, str) else c for c in model.cluster_context]
        return ChatSession(
            id=model.id,
            user_id=model.user_id,
            title=model.title,
            persona_id=model.persona_id,
            cluster_context=cluster_context,
            message_count=model.message_count,
            created_at=model.created_at,
            updated_at=model.updated_at,
            expires_at=model.expires_at,
        )

    def _model_to_message(self, model: ChatMessageModel) -> ChatMessage:
        """Convert SQLAlchemy model to Pydantic model."""
        tool_calls = None
        if model.tool_calls:
            tool_calls = [ToolCall(**tc) if isinstance(tc, dict) else tc for tc in model.tool_calls]

        tool_results = None
        if model.tool_results:
            tool_results = []
            for tr in model.tool_results:
                if isinstance(tr, dict):
                    # Convert status string back to enum
                    tr_copy = tr.copy()
                    if "status" in tr_copy and isinstance(tr_copy["status"], str):
                        tr_copy["status"] = ToolResultStatus(tr_copy["status"])
                    tool_results.append(ToolResult(**tr_copy))
                else:
                    tool_results.append(tr)

        return ChatMessage(
            id=model.id,
            session_id=model.session_id,
            role=MessageRole(model.role.upper()),
            content=model.content,
            persona_id=model.persona_id,
            tool_calls=tool_calls,
            tool_results=tool_results,
            model=model.model,
            tokens_used=model.tokens_used,
            latency_ms=model.latency_ms,
            created_at=model.created_at,
        )

    async def _cache_session(self, session: ChatSession) -> None:
        """Cache session in Redis."""
        if not self.redis:
            return
        await self.redis.cache_set(
            "chat_sessions",
            str(session.id),
            session.model_dump(mode="json"),
            ttl_seconds=self.CACHE_TTL_SECONDS,
        )

    async def _get_cached_session(self, session_id: UUID) -> ChatSession | None:
        """Get session from Redis cache."""
        if not self.redis:
            return None
        data = await self.redis.cache_get_json("chat_sessions", str(session_id))
        if data:
            return ChatSession(**data)
        return None

    async def _cache_messages(
        self,
        session_id: UUID,
        messages: list[ChatMessage],
    ) -> None:
        """Cache messages in Redis."""
        if not self.redis:
            return
        await self.redis.cache_set(
            "chat_messages",
            str(session_id),
            [m.model_dump(mode="json") for m in messages],
            ttl_seconds=self.CACHE_TTL_SECONDS,
        )

    async def _get_cached_messages(self, session_id: UUID) -> list[ChatMessage] | None:
        """Get messages from Redis cache."""
        if not self.redis:
            return None
        data = await self.redis.cache_get_json("chat_messages", str(session_id))
        if data and isinstance(data, list):
            return [ChatMessage(**m) for m in data]
        return None

    async def _append_message_to_cache(self, message: ChatMessage) -> None:
        """Append a single message to the cached message list."""
        if not self.redis:
            return

        # Get existing messages from cache
        messages = await self._get_cached_messages(message.session_id)
        if messages is None:
            messages = []

        messages.append(message)
        await self._cache_messages(message.session_id, messages)


async def check_database_health(session_factory) -> dict[str, Any]:
    """Check PostgreSQL database health.

    Args:
        session_factory: SQLAlchemy async session factory

    Returns:
        Health status dict with status and latency
    """
    import time

    try:
        start = time.time()
        async with session_factory() as db:
            # Simple connectivity check
            await db.execute(select(1))
        latency_ms = int((time.time() - start) * 1000)
        return {
            "status": "healthy",
            "latency_ms": latency_ms,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }
