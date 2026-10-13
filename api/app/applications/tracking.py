"""Application timeline and user-owned dashboard analytics."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal

ApplicationTrackingStatus = Literal[
    "discovered",
    "strong_match",
    "prepared",
    "awaiting_approval",
    "submitted",
    "assessment",
    "interview",
    "rejected",
    "offer",
    "withdrawn",
]


@dataclass(frozen=True)
class TimelineEvent:
    event_type: str
    at: datetime
    note: str | None = None


@dataclass
class TrackedApplication:
    company: str
    role: str
    location: str | None
    source: str
    match_score: int
    resume_version: str | None
    application_date: datetime | None
    status: ApplicationTrackingStatus = "discovered"
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))
    notes: str | None = None
    timeline: list[TimelineEvent] = field(default_factory=list)

    def update_status(self, status: ApplicationTrackingStatus, *, note: str | None = None) -> None:
        self.status = status
        self.last_updated = datetime.now(UTC)
        self.timeline.append(TimelineEvent(f"status:{status}", self.last_updated, note))


def application_analytics(
    applications: list[TrackedApplication], *, now: datetime | None = None
) -> dict[str, object]:
    current = now or datetime.now(UTC)
    week_ago = current - timedelta(days=7)
    submitted = [
        item
        for item in applications
        if item.status in {"submitted", "assessment", "interview", "rejected", "offer"}
    ]
    responses = [
        item
        for item in submitted
        if item.status in {"assessment", "interview", "rejected", "offer"}
    ]
    interviews = [item for item in submitted if item.status in {"interview", "offer"}]
    return {
        "applications_this_week": sum(
            bool(item.application_date and item.application_date >= week_ago)
            for item in applications
        ),
        "average_match_score": round(
            sum(item.match_score for item in applications) / len(applications), 2
        )
        if applications
        else 0,
        "response_rate": len(responses) / len(submitted) if submitted else 0,
        "interview_rate": len(interviews) / len(submitted) if submitted else 0,
        "applications_by_role": dict(Counter(item.role for item in applications)),
        "applications_by_source": dict(Counter(item.source for item in applications)),
        "applications_by_location": dict(
            Counter(item.location or "Unknown" for item in applications)
        ),
    }
