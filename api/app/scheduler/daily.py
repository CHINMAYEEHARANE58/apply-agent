"""Lockable daily-search orchestration with no implicit source automation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Protocol

from app.config.schemas import APIModel


class DailySearchSettings(APIModel):
    search_enabled: bool = True
    search_time: str = "09:00"
    timezone: str = "UTC"
    maximum_jobs_evaluated_daily: int = 100
    maximum_applications_prepared_daily: int = 20
    maximum_applications_submitted_daily: int = 10
    minimum_match_score: int = 75


class DailyPipeline(Protocol):
    def run(self, user_id: uuid.UUID, settings: DailySearchSettings) -> dict[str, int]: ...


@dataclass
class InMemoryDailyLock:
    held: set[uuid.UUID] = field(default_factory=set)

    def acquire(self, user_id: uuid.UUID) -> bool:
        if user_id in self.held:
            return False
        self.held.add(user_id)
        return True

    def release(self, user_id: uuid.UUID) -> None:
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
