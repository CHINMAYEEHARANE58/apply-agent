"""Read only already-imported listings; no remote browsing or fetching."""
import re
from typing import cast

from pydantic import HttpUrl
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.job_sources.adapters import JobSourceAdapter, manual_discovery_capability
from app.job_sources.schemas import SourceCapability
from app.jobs.discovery_schemas import (
    InternshipDuration,
    JobSearchQuery,
    NormalizedJob,
    SourceJobPayload,
    WorkplaceType,
)
from app.jobs.models import Job


def canonical_job(job: Job) -> NormalizedJob:
    if job.normalized_payload:
        return NormalizedJob.model_validate(job.normalized_payload)
    duration = re.fullmatch(r"\s*(\d+)\s*(weeks?|months?)\s*", job.duration or "", re.I)
    return NormalizedJob(source=job.source, source_job_id=job.external_job_id, url=HttpUrl(job.job_url), company=job.company, title=job.title, description=job.description, location=job.location, workplace_type=cast(WorkplaceType, job.workplace_type if job.workplace_type in {"remote", "hybrid", "onsite"} else "unknown"), required_skills=job.skills, stipend_min=job.stipend, currency=job.currency, posted_at=job.posted_at, internship_duration=InternshipDuration(value=int(duration[1]), unit="weeks" if duration[2].lower().startswith("week") else "months") if duration else None)


class StoredCatalogAdapter(JobSourceAdapter):
    def __init__(self, session: Session) -> None:
        self.session = session

    def search_jobs(self, query: JobSearchQuery) -> tuple[SourceJobPayload, ...]:
        rows = self.session.scalars(select(Job).order_by(Job.discovered_at.desc(), Job.id).limit(query.limit))
        return tuple(SourceJobPayload(**canonical_job(job).model_dump(exclude={"source"})) for job in rows)

    def get_job(self, source_job_id: str) -> SourceJobPayload | None:
        row = self.session.scalar(select(Job).where(Job.external_job_id == source_job_id).order_by(Job.id).limit(1))
        return SourceJobPayload(**canonical_job(row).model_dump(exclude={"source"})) if row else None

    def normalize_job(self, raw_job: SourceJobPayload) -> NormalizedJob:
        # The catalogue is a manual handoff, never an authorization grant.
        return NormalizedJob(source="catalog", **raw_job.model_dump())

    def get_capabilities(self) -> SourceCapability:
        return manual_discovery_capability("catalog")
