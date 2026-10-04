from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class WorkMode(StrEnum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"


class CandidatePreferences(BaseModel):
    model_config = ConfigDict(frozen=True)
    desired_roles: tuple[str, ...] = ()
    preferred_skills: tuple[str, ...] = ()
    internship_duration_weeks: int | None = Field(default=None, ge=1, le=104)
    minimum_stipend: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    preferred_locations: tuple[str, ...] = ()
    work_modes: tuple[WorkMode, ...] = ()
    desired_start_date: date | None = None
    industries: tuple[str, ...] = ()
    preferred_companies: tuple[str, ...] = ()
    excluded_companies: tuple[str, ...] = ()
    excluded_keywords: tuple[str, ...] = ()
    maximum_applications_per_day: int = Field(default=5, ge=0, le=50)
    work_authorization: str | None = None
    relocation_preference: bool = False
