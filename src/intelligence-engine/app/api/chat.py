"""Chat API endpoints.

Spec Reference: specs/04-intelligence-engine.md Section 4.1
"""

from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from shared.models.intelligence import ChatMessage, ChatSession, ChatSessionCreate

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


class MessageRequest(BaseModel):
    """Request body for sending a message."""

    content: str


@router.post("/sessions", response_model=ChatSession, status_code=201)
async def create_session(
    request: Request,
    body: ChatSessionCreate,
) -> ChatSession:
    """Create a new chat session.

    Spec Reference: specs/04-intelligence-engine.md Section 4.6
    """
    chat_service = request.app.state.chat_service
    # For now, use a default user ID (in production, get from auth)
    user_id = "default-user"

    session = await chat_service.create_session(user_id, body)
    return session


@router.get("/sessions", response_model=list[ChatSession])
async def list_sessions(request: Request) -> list[ChatSession]:
    """List user's chat sessions.

    Spec Reference: specs/04-intelligence-engine.md Section 4.1
    """
    chat_service = request.app.state.chat_service
    user_id = "default-user"

    return await chat_service.list_sessions(user_id)


@router.get("/sessions/{session_id}", response_model=ChatSession)
async def get_session(
    request: Request,
    session_id: UUID,
) -> ChatSession:
    """Get a chat session by ID.

    Spec Reference: specs/04-intelligence-engine.md Section 4.1
    """
    chat_service = request.app.state.chat_service
    session = await chat_service.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    request: Request,
    session_id: UUID,
) -> None:
    """Delete a chat session.

    Spec Reference: specs/04-intelligence-engine.md Section 4.1
    """
    chat_service = request.app.state.chat_service
    await chat_service.delete_session(session_id)


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessage])
async def get_messages(
    request: Request,
    session_id: UUID,
) -> list[ChatMessage]:
    """Get messages for a session.

    Spec Reference: specs/04-intelligence-engine.md Section 4.1
    """
    chat_service = request.app.state.chat_service
    return await chat_service.get_messages(session_id)


@router.post("/sessions/{session_id}/messages", response_model=ChatMessage)
async def send_message(
    request: Request,
    session_id: UUID,
    body: MessageRequest,
) -> ChatMessage:
    """Send a message and get AI response (non-streaming).

    Spec Reference: specs/04-intelligence-engine.md Section 4.6
    """
    chat_service = request.app.state.chat_service

    try:
        return await chat_service.send_message(session_id, body.content)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/sessions/{session_id}/stream")
async def stream_message(
    request: Request,
    session_id: UUID,
    body: MessageRequest,
):
    """Stream a message response (SSE).

    Spec Reference: specs/04-intelligence-engine.md Section 4.6
    """
    chat_service = request.app.state.chat_service

    async def event_generator():
        async for chunk in chat_service.stream_message(session_id, body.content):
            event_type = chunk.get("type", "message")
            yield {
                "event": event_type,
                "data": json.dumps(chunk),
            }

    return EventSourceResponse(event_generator())
