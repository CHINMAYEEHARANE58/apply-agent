import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from app.config.schemas import APIModel

ApplicationStatus = Literal["discovered", "matched", "prepared", "awaiting_approval", "submitted", "assessment", "interview", "rejected", "offer", "withdrawn"]


class ApplicationCreate(APIModel):
    job_id: uuid.UUID
    resume_id: uuid.UUID | None = None
    status: ApplicationStatus = "discovered"
    cover_letter: str | None = Field(default=None, max_length=20_000)
    application_message: str | None = Field(default=None, max_length=10_000)
    submitted_at: datetime | None = None
    external_application_id: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_submission_metadata(self) -> "ApplicationCreate":
        if self.submitted_at and self.status != "submitted":
            raise ValueError("submitted_at is only valid when status is submitted.")
        return self


class ApplicationUpdate(APIModel):
    resume_id: uuid.UUID | None = None
    status: ApplicationStatus | None = None
    cover_letter: str | None = Field(default=None, max_length=20_000)
    application_message: str | None = Field(default=None, max_length=10_000)
    submitted_at: datetime | None = None
    external_application_id: str | None = Field(default=None, max_length=255)


class ApplicationRead(ApplicationCreate):
    id: uuid.UUID
    user_id: uuid.UUID
