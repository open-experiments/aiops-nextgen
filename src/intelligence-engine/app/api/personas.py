"""Persona API endpoints.

Spec Reference: specs/04-intelligence-engine.md Section 4.3
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from shared.models.intelligence import Persona

router = APIRouter(prefix="/api/v1/personas", tags=["personas"])


class PersonaListResponse(BaseModel):
    """Response model for listing personas."""

    personas: list[Persona]


@router.get("", response_model=PersonaListResponse)
async def list_personas(request: Request) -> PersonaListResponse:
    """List all available personas.

    Spec Reference: specs/04-intelligence-engine.md Section 4.3
    """
    persona_service = request.app.state.persona_service
    personas = persona_service.list_personas()
    return PersonaListResponse(personas=personas)


@router.get("/{persona_id}", response_model=Persona)
async def get_persona(
    request: Request,
    persona_id: str,
) -> Persona:
    """Get a persona by ID.

    Spec Reference: specs/04-intelligence-engine.md Section 4.3
    """
    persona_service = request.app.state.persona_service
    persona = persona_service.get_persona(persona_id)

    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    return persona
