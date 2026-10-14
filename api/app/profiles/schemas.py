import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, HttpUrl, field_validator

from app.config.schemas import APIModel


class CandidateProfileUpsert(APIModel):
    full_name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=40)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=120)
    timezone: str | None = Field(default=None, max_length=64)
    college: str | None = Field(default=None, max_length=255)
    degree: str | None = Field(default=None, max_length=255)
    graduation_year: int | None = Field(default=None, ge=1900, le=2200)
    current_role: str | None = Field(default=None, max_length=200)
    location: str | None = Field(default=None, max_length=200)
    work_authorization: str | None = Field(default=None, max_length=200)
    relocation_allowed: bool = False
    visa_sponsorship_required: bool | None = None
    linkedin_url: HttpUrl | None = None
    github_url: HttpUrl | None = None
    portfolio_url: HttpUrl | None = None

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str | None) -> str | None:
        if value:
            try:
                ZoneInfo(value)
            except (ValueError, ZoneInfoNotFoundError) as error:
                raise ValueError("Invalid IANA timezone.") from error
        return value


class CandidateProfileRead(APIModel):
    id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    phone: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    timezone: str | None = None
    college: str | None = None
    degree: str | None = None
    graduation_year: int | None = None
    current_role: str | None = None
    location: str | None = None
    work_authorization: str | None = None
    relocation_allowed: bool
    visa_sponsorship_required: bool | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
