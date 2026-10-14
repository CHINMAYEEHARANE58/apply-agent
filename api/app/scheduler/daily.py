"""Lockable daily-search orchestration with no implicit source automation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from threading import Lock
from typing import Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator

from app.config.schemas import APIModel


class DailySearchSettings(APIModel):
    search_enabled: bool = True
    search_time: str = Field(default="09:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    timezone: str = "UTC"
    maximum_jobs_evaluated_daily: int = Field(default=100, ge=0, le=10000)
    maximum_applications_prepared_daily: int = Field(default=20, ge=0, le=1000)
    maximum_applications_submitted_daily: int = Field(default=10, ge=0, le=50)
    minimum_match_score: int = Field(default=75, ge=0, le=100)

    @field_validator("timezone")
    @classmethod
    def timezone_exists(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError("Invalid IANA timezone.") from error
        return value


class DailyPipeline(Protocol):
    def run(self, user_id: uuid.UUID, settings: DailySearchSettings) -> dict[str, int]: ...


@dataclass
class InMemoryDailyLock:
    held: set[uuid.UUID] = field(default_factory=set)
    _mutex: Lock = field(default_factory=Lock, repr=False)

    def acquire(self, user_id: uuid.UUID) -> bool:
        with self._mutex:
            if user_id in self.held:
                return False
            self.held.add(user_id)
            return True

    def release(self, user_id: uuid.UUID) -> None:
        with self._mutex:
            self.held.discard(user_id)


@dataclass
class DailySearchService:
    pipeline: DailyPipeline
    lock: InMemoryDailyLock = field(default_factory=InMemoryDailyLock)

    def run(self, user_id: uuid.UUID, settings: DailySearchSettings) -> dict[str, int | str]:
        if not settings.search_enabled:
            return {"status": "disabled"}
        if not self.lock.acquire(user_id):
            return {"status": "already_running"}
        try:
            return {"status": "completed", **self.pipeline.run(user_id, settings)}
        finally:
            self.lock.release(user_id)
