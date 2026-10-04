import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from app.config.schemas import APIModel

ApplicationMode = Literal["review", "batch", "authorized-auto"]
DurationUnit = Literal["weeks", "months"]


class InternshipPreferenceUpsert(APIModel):
    roles: list[str] = Field(default_factory=list, max_length=50)
    skills: list[str] = Field(default_factory=list, max_length=100)
    preferred_locations: list[str] = Field(default_factory=list, max_length=100)
    remote_allowed: bool = True
    hybrid_allowed: bool = True
    onsite_allowed: bool = False
    min_duration: int | None = Field(default=None, ge=1, le=104)
    max_duration: int | None = Field(default=None, ge=1, le=104)
    duration_unit: DurationUnit = "weeks"
    minimum_stipend: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    allow_unpaid: bool = False
    earliest_start_date: date | None = None
    latest_start_date: date | None = None
    preferred_industries: list[str] = Field(default_factory=list, max_length=50)
    preferred_companies: list[str] = Field(default_factory=list, max_length=100)
    excluded_companies: list[str] = Field(default_factory=list, max_length=100)
    excluded_keywords: list[str] = Field(default_factory=list, max_length=100)
    max_daily_applications: int = Field(default=5, ge=0, le=50)
    application_mode: ApplicationMode = "review"

    @model_validator(mode="after")
    def validate_ranges(self) -> "InternshipPreferenceUpsert":
        if self.min_duration and self.max_duration and self.min_duration > self.max_duration:
            raise ValueError("min_duration must be less than or equal to max_duration.")
        if self.earliest_start_date and self.latest_start_date and self.earliest_start_date > self.latest_start_date:
            raise ValueError("earliest_start_date must not be after latest_start_date.")
        return self


class InternshipPreferenceRead(InternshipPreferenceUpsert):
    id: uuid.UUID
    user_id: uuid.UUID
