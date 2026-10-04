import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import Field, HttpUrl, field_validator

from app.config.schemas import APIModel


class JobCreate(APIModel):
    source: str = Field(min_length=1, max_length=100)
    external_job_id: str = Field(min_length=1, max_length=255)
    job_url: HttpUrl
    company: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=100_000, description="Untrusted external content, stored as data only.")
    location: str | None = Field(default=None, max_length=200)
    workplace_type: str | None = Field(default=None, max_length=32)
    duration: str | None = Field(default=None, max_length=100)
    stipend: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    skills: list[str] = Field(default_factory=list, max_length=100)
    posted_at: datetime | None = None
    fingerprint: str = Field(min_length=16, max_length=128)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class JobUpdate(APIModel):
    location: str | None = Field(default=None, max_length=200)
    workplace_type: str | None = Field(default=None, max_length=32)
    duration: str | None = Field(default=None, max_length=100)
    stipend: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    skills: list[str] | None = Field(default=None, max_length=100)
    posted_at: datetime | None = None


class JobRead(APIModel):
    id: uuid.UUID
    source: str
    external_job_id: str
    job_url: str
    company: str
    title: str
    description: str
    location: str | None = None
    workplace_type: str | None = None
    duration: str | None = None
    stipend: Decimal | None = None
    currency: str | None = None
    skills: list[str]
    posted_at: datetime | None = None
    discovered_at: datetime
    fingerprint: str


class JobMatchCreate(APIModel):
    job_id: uuid.UUID
    score: int = Field(ge=0, le=100)
    hard_filter_passed: bool
    matched_skills: list[str] = Field(default_factory=list, max_length=100)
    missing_skills: list[str] = Field(default_factory=list, max_length=100)
    explanation: str = Field(min_length=1, max_length=10_000)


class JobMatchUpdate(APIModel):
    score: int | None = Field(default=None, ge=0, le=100)
    hard_filter_passed: bool | None = None
    matched_skills: list[str] | None = Field(default=None, max_length=100)
    missing_skills: list[str] | None = Field(default=None, max_length=100)
    explanation: str | None = Field(default=None, min_length=1, max_length=10_000)


class JobMatchRead(JobMatchCreate):
    id: uuid.UUID
    user_id: uuid.UUID
