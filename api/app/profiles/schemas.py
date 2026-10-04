import uuid

from pydantic import Field, HttpUrl

from app.config.schemas import APIModel


class CandidateProfileUpsert(APIModel):
    full_name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=40)
    location: str | None = Field(default=None, max_length=200)
    work_authorization: str | None = Field(default=None, max_length=200)
    relocation_allowed: bool = False
    linkedin_url: HttpUrl | None = None
    github_url: HttpUrl | None = None
    portfolio_url: HttpUrl | None = None


class CandidateProfileRead(APIModel):
    id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    phone: str | None = None
    location: str | None = None
    work_authorization: str | None = None
    relocation_allowed: bool
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
