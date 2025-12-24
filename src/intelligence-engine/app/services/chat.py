"""Chat service for managing chat sessions and messages.

Spec Reference: specs/04-intelligence-engine.md Section 4.1
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from typing import Any, AsyncIterator
from uuid import UUID, uuid4

from shared.models.intelligence import (
    ChatMessage,
    ChatSession,
    ChatSessionCreate,
    MessageRole,
    ToolCall,
    ToolResult,
    ToolResultStatus,
)
from shared.observability import get_logger
from shared.redis_client import RedisClient, RedisDB

from ..llm.router import LLMRouter
from ..tools.definitions import get_tools_for_persona
from ..tools.executor import ToolExecutor
from .personas import PersonaService

logger = get_logger(__name__)


class ChatService:
    """Service for managing chat sessions and messages.

    Spec Reference: specs/04-intelligence-engine.md Section 4.1
    """

    SESSION_TTL_HOURS = 24
    MAX_CONTEXT_MESSAGES = 50
    MAX_TOOL_ITERATIONS = 5

    def __init__(
        self,
        redis: RedisClient,
        llm_router: LLMRouter,
        tool_executor: ToolExecutor,
        persona_service: PersonaService,
    ):
        self.redis = redis
        self.llm_router = llm_router
        self.tool_executor = tool_executor
        self.persona_service = persona_service

    async def create_session(
        self,
        user_id: str,
        request: ChatSessionCreate,
    ) -> ChatSession:
        """Create a new chat session.

        Spec Reference: specs/04-intelligence-engine.md Section 4.6
        """
        session_id = uuid4()
        now = datetime.utcnow()
        expires_at = now + timedelta(hours=self.SESSION_TTL_HOURS)

        session = ChatSession(
            id=session_id,
            user_id=user_id,
            title=request.title,
            persona_id=request.persona_id,
            cluster_context=request.cluster_context,
            message_count=0,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
        )

        # Store in Redis
        await self._save_session(session)

        logger.info(
            "Chat session created",
            session_id=str(session_id),
            persona_id=request.persona_id,
        )

        return session

    async def get_session(self, session_id: UUID) -> ChatSession | None:
        """Get a chat session by ID.

        Spec Reference: specs/04-intelligence-engine.md Section 4.1
        """
        data = await self.redis.cache_get_json("chat_sessions", str(session_id))
        if data:
            return ChatSession(**data)
        return None

    async def list_sessions(self, user_id: str) -> list[ChatSession]:
        """List sessions for a user.

        Spec Reference: specs/04-intelligence-engine.md Section 4.1
        """
        # For now, scan Redis for user's sessions
        # In production, this would query PostgreSQL
        sessions = []
        cache_client = self.redis.get_client(RedisDB.CACHE)

        pattern = "cache:chat_sessions:*"
        async for key in cache_client.scan_iter(match=pattern):
            data = await cache_client.get(key)
            if data:
                if isinstance(data, bytes):
                    data = data.decode()
                session_data = json.loads(data)
                if session_data.get("user_id") == user_id:
                    sessions.append(ChatSession(**session_data))

        return sorted(sessions, key=lambda s: s.created_at, reverse=True)

    async def delete_session(self, session_id: UUID) -> bool:
        """Delete a chat session.

        Spec Reference: specs/04-intelligence-engine.md Section 4.1
        """
        # Delete session
        await self.redis.cache_delete("chat_sessions", str(session_id))
        # Delete messages
        await self.redis.cache_delete("chat_messages", str(session_id))
        return True

    async def send_message(
        self,
        session_id: UUID,
        content: str,
    ) -> ChatMessage:
        """Send a message and get AI response (non-streaming).

        Spec Reference: specs/04-intelligence-engine.md Section 4.6
        """
        start_time = time.time()

        # Get session
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        # Save user message
        user_message = ChatMessage(
            id=uuid4(),
            session_id=session_id,
            role=MessageRole.USER,
            content=content,
            persona_id=session.persona_id,
            created_at=datetime.utcnow(),
        )
        await self._save_message(user_message)

        # Build messages for LLM
        messages = await self._build_messages(session, content)

        # Get tools for persona
        capabilities = self.persona_service.get_capabilities(session.persona_id)
        tools = get_tools_for_persona(capabilities)

        # Call LLM with tool loop
        response_content = ""
        tool_calls_made = []
        tool_results = []
        tokens_used = 0

        for iteration in range(self.MAX_TOOL_ITERATIONS):
            response = await self.llm_router.chat(
                messages=messages,
                tools=tools if tools else None,
            )

            tokens_used += response.get("tokens_used", 0)

            # Check for tool calls
            if response.get("tool_calls"):
                for tc in response["tool_calls"]:
                    tool_call = ToolCall(
                        id=tc["id"],
                        name=tc["name"],
                        arguments=tc["arguments"],
                    )
                    tool_calls_made.append(tool_call)

                    # Execute tool
                    result = await self.tool_executor.execute(
                        tc["name"],
                        tc["arguments"],
                    )

                    tool_result = ToolResult(
                        tool_call_id=tc["id"],
                        status=ToolResultStatus.SUCCESS if "error" not in result else ToolResultStatus.ERROR,
                        result=result if "error" not in result else None,
                        error=result.get("error"),
                    )
                    tool_results.append(tool_result)

                    # Add to messages for next iteration
                    messages.append({
                        "role": "assistant",
                        "content": response.get("content", ""),
                        "tool_calls": [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {
                                    "name": tc["name"],
                                    "arguments": json.dumps(tc["arguments"]),
                                },
                            }
                        ],
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": json.dumps(result),
                    })
            else:
                # No tool calls, we have final response
                response_content = response.get("content", "")
                break

        latency_ms = int((time.time() - start_time) * 1000)

        # Create assistant message
        assistant_message = ChatMessage(
            id=uuid4(),
            session_id=session_id,
            role=MessageRole.ASSISTANT,
            content=response_content,
            persona_id=session.persona_id,
            tool_calls=tool_calls_made,
            tool_results=tool_results,
            model=response.get("model"),
            tokens_used=tokens_used,
            latency_ms=latency_ms,
            created_at=datetime.utcnow(),
        )
        await self._save_message(assistant_message)

        # Update session
        session.message_count += 2
        session.updated_at = datetime.utcnow()
        await self._save_session(session)

        return assistant_message

    async def stream_message(
        self,
        session_id: UUID,
        content: str,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream a message response (SSE).

        Spec Reference: specs/04-intelligence-engine.md Section 4.6
        """
        start_time = time.time()

        # Get session
        session = await self.get_session(session_id)
        if not session:
            yield {"type": "error", "error": "Session not found"}
            return

        # Save user message
        user_message = ChatMessage(
            id=uuid4(),
            session_id=session_id,
            role=MessageRole.USER,
            content=content,
            persona_id=session.persona_id,
            created_at=datetime.utcnow(),
        )
        await self._save_message(user_message)

        # Build messages for LLM
        messages = await self._build_messages(session, content)

        # Get tools for persona
        capabilities = self.persona_service.get_capabilities(session.persona_id)
        tools = get_tools_for_persona(capabilities)

        # Emit message start
        message_id = uuid4()
        yield {
            "type": "message_start",
            "id": str(message_id),
            "role": "ASSISTANT",
        }

        # Stream from LLM
        full_content = ""
        tool_calls_made = []
        tool_results = []
        tokens_used = 0

        try:
            async for chunk in self.llm_router.stream(
                messages=messages,
                tools=tools if tools else None,
            ):
                if chunk["type"] == "content_delta":
                    full_content += chunk["delta"]
                    yield {
                        "type": "content_delta",
                        "delta": chunk["delta"],
                    }

                elif chunk["type"] == "tool_use":
                    tc = chunk["tool_call"]
                    tool_call = ToolCall(
                        id=tc["id"],
                        name=tc["name"],
                        arguments=tc["arguments"],
                    )
                    tool_calls_made.append(tool_call)

                    yield {
                        "type": "tool_use",
                        "tool_call_id": tc["id"],
                        "name": tc["name"],
                        "arguments": tc["arguments"],
                    }

                    # Execute tool
                    result = await self.tool_executor.execute(
                        tc["name"],
                        tc["arguments"],
                    )

                    tool_result = ToolResult(
                        tool_call_id=tc["id"],
                        status=ToolResultStatus.SUCCESS if "error" not in result else ToolResultStatus.ERROR,
                        result=result if "error" not in result else None,
                        error=result.get("error"),
                    )
                    tool_results.append(tool_result)

                    status_str = tool_result.status.value if hasattr(tool_result.status, 'value') else str(tool_result.status)
                    yield {
                        "type": "tool_result",
                        "tool_call_id": tc["id"],
                        "status": status_str,
                    }

                elif chunk["type"] == "message_complete":
                    if not full_content and chunk.get("content"):
                        full_content = chunk["content"]

        except Exception as e:
            logger.error("Streaming error", error=str(e))
            yield {"type": "error", "error": str(e)}
            return

        latency_ms = int((time.time() - start_time) * 1000)

        # Save assistant message
        assistant_message = ChatMessage(
            id=message_id,
            session_id=session_id,
            role=MessageRole.ASSISTANT,
            content=full_content,
            persona_id=session.persona_id,
            tool_calls=tool_calls_made,
            tool_results=tool_results,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
            created_at=datetime.utcnow(),
        )
        await self._save_message(assistant_message)

        # Update session
        session.message_count += 2
        session.updated_at = datetime.utcnow()
        await self._save_session(session)

        yield {
            "type": "message_complete",
            "tokens_used": tokens_used,
            "latency_ms": latency_ms,
        }

    async def get_messages(self, session_id: UUID) -> list[ChatMessage]:
        """Get messages for a session.

        Spec Reference: specs/04-intelligence-engine.md Section 4.1
        """
        data = await self.redis.cache_get_json("chat_messages", str(session_id))
        if data and isinstance(data, list):
            return [ChatMessage(**m) for m in data]
        return []

    async def _build_messages(
        self,
        session: ChatSession,
        current_content: str,
    ) -> list[dict[str, Any]]:
        """Build message list for LLM including system prompt and history."""
        messages = []

        # Add system prompt
        system_prompt = self.persona_service.get_system_prompt(session.persona_id)
        messages.append({
            "role": "system",
            "content": system_prompt,
        })

        # Add context about clusters if specified
        if session.cluster_context:
            context = f"\nYou are currently focused on the following clusters: {', '.join(str(c) for c in session.cluster_context)}"
            messages[0]["content"] += context

        # Add message history (limited)
        history = await self.get_messages(session.id)
        for msg in history[-self.MAX_CONTEXT_MESSAGES:]:
            role_str = msg.role.value.lower() if hasattr(msg.role, 'value') else str(msg.role).lower()
            messages.append({
                "role": role_str,
                "content": msg.content,
            })

        # Add current message
        messages.append({
            "role": "user",
            "content": current_content,
        })

        return messages

    async def _save_session(self, session: ChatSession) -> None:
        """Save session to Redis."""
        await self.redis.cache_set(
            "chat_sessions",
            str(session.id),
            session.model_dump(mode="json"),
            ttl_seconds=self.SESSION_TTL_HOURS * 3600,
        )

    async def _save_message(self, message: ChatMessage) -> None:
        """Save message to session's message list."""
        messages = await self.get_messages(message.session_id)
        messages.append(message)

        await self.redis.cache_set(
            "chat_messages",
            str(message.session_id),
            [m.model_dump(mode="json") for m in messages],
            ttl_seconds=self.SESSION_TTL_HOURS * 3600,
        )
