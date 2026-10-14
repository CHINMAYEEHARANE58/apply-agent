import uuid
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator

from app.config.schemas import APIModel
from app.preferences.schemas import ApplicationMode


class SettingsUpdate(APIModel):
    search_enabled: bool = True
    search_time: str = Field(default="09:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    timezone: str = Field(default="UTC", max_length=64)
    minimum_match_score: int = Field(default=75, ge=0, le=100)
    max_daily_applications: int = Field(default=10, ge=0, le=50)
    maximum_jobs_evaluated_daily: int = Field(default=100, ge=0, le=10000)
    maximum_applications_prepared_daily: int = Field(default=20, ge=0, le=1000)
    application_mode: ApplicationMode = "review"
    email_notifications: bool = True
    application_notifications: bool = True
    enabled_sources: list[Literal["catalog"]] = Field(default=["catalog"], max_length=1)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ValueError, ZoneInfoNotFoundError) as error:
            raise ValueError("Invalid IANA timezone.") from error
        return value


class SettingsRead(SettingsUpdate):
    user_id: uuid.UUID
