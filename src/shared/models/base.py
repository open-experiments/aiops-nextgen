"""Base model configuration for all Pydantic models.

Spec Reference: specs/01-data-models.md Section 1 - Conventions
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AIOpsBaseModel(BaseModel):
    """Base model with common configuration.

    Conventions from spec:
    - All timestamps are ISO 8601 format with timezone (UTC preferred)
    - All IDs are UUID v4 unless otherwise specified
    - Field names are lowercase snake_case
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        use_enum_values=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        },
    )
