import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.config.schemas import APIModel


class AuditEventCreate(APIModel):
    event_type: str = Field(min_length=1, max_length=100)
    entity_type: str = Field(min_length=1, max_length=100)
    entity_id: uuid.UUID
    metadata: dict[str, Any] | None = None


class AuditEventRead(APIModel):
    id: uuid.UUID
    user_id: uuid.UUID
    event_type: str
    entity_type: str
    entity_id: uuid.UUID
    metadata: dict[str, Any] | None = Field(default=None, validation_alias="event_metadata")
    created_at: datetime
