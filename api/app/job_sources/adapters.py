"""Pluggable, policy-declared job discovery adapters.

These adapters deliberately provide no browser driver, scraper, credential
store, CAPTCHA handler, or HTTP client. Production adapters may only be added
after their written/API authorization is reviewed and recorded in capabilities.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from app.job_sources.schemas import ApplicationMethod, DiscoveryMethod, SourceCapability
from app.jobs.discovery_schemas import JobSearchQuery, NormalizedJob, SourceJobPayload


class JobSourceAdapter(ABC):
    """The complete contract every permitted source must implement."""

    @abstractmethod
    def search_jobs(self, query: JobSearchQuery) -> tuple[SourceJobPayload, ...]:
        """Return source data only; callers decide whether and how to store it."""

    @abstractmethod
    def get_job(self, source_job_id: str) -> SourceJobPayload | None:
        """Return a known listing without authenticating, scraping, or browsing."""

    @abstractmethod
    def normalize_job(self, raw_job: SourceJobPayload) -> NormalizedJob:
        """Map a source payload into the source-neutral job schema."""

    @abstractmethod
    def get_capabilities(self) -> SourceCapability:
        """Declare the source's permitted discovery, application, and messaging paths."""


class MockJobSourceAdapter(JobSourceAdapter):
    """In-memory development adapter. It never performs a network request."""

    def __init__(
        self,
        capability: SourceCapability,
        jobs: Iterable[SourceJobPayload] = (),
    ) -> None:
        self._capability = capability
        self._jobs = {job.source_job_id: job for job in jobs}

    def search_jobs(self, query: JobSearchQuery) -> tuple[SourceJobPayload, ...]:
        terms = {term.casefold() for term in [*query.roles, *query.keywords] if term.strip()}
        if not terms:
            return tuple(self._jobs.values())[: query.limit]
        matches = [
            job
            for job in self._jobs.values()
            if any(term in f"{job.title} {job.description}".casefold() for term in terms)
        ]
        return tuple(matches[: query.limit])

    def get_job(self, source_job_id: str) -> SourceJobPayload | None:
        return self._jobs.get(source_job_id)

    def normalize_job(self, raw_job: SourceJobPayload) -> NormalizedJob:
        return NormalizedJob(source=self.get_capabilities().source_name, **raw_job.model_dump())

    def get_capabilities(self) -> SourceCapability:
        return self._capability


def manual_discovery_capability(source_name: str) -> SourceCapability:
    """Capability for link-only sources with no assumed automation permission."""

    return SourceCapability(
        source_name=source_name,
        discovery_supported=True,
        discovery_method=DiscoveryMethod.MANUAL,
        application_supported=False,
        application_method=ApplicationMethod.MANUAL,
        messaging_supported=False,
        requires_user_confirmation=True,
        authorization_verified=False,
    )


class LinkedInDiscoveryLinkAdapter(MockJobSourceAdapter):
    def __init__(self, jobs: Iterable[SourceJobPayload] = ()) -> None:
        super().__init__(manual_discovery_capability("LinkedIn discovery links"), jobs)


class IndeedDiscoveryLinkAdapter(MockJobSourceAdapter):
    def __init__(self, jobs: Iterable[SourceJobPayload] = ()) -> None:
        super().__init__(manual_discovery_capability("Indeed discovery links"), jobs)


class GlassdoorDiscoveryLinkAdapter(MockJobSourceAdapter):
    def __init__(self, jobs: Iterable[SourceJobPayload] = ()) -> None:
        super().__init__(manual_discovery_capability("Glassdoor discovery links"), jobs)


class NaukriDiscoveryLinkAdapter(MockJobSourceAdapter):
    def __init__(self, jobs: Iterable[SourceJobPayload] = ()) -> None:
        super().__init__(manual_discovery_capability("Naukri discovery links"), jobs)


class EmployerCareerSiteMockAdapter(MockJobSourceAdapter):
    def __init__(self, jobs: Iterable[SourceJobPayload] = ()) -> None:
        super().__init__(
            SourceCapability(
                source_name="Employer career sites (mock)",
                discovery_supported=True,
                discovery_method=DiscoveryMethod.MANUAL,
                application_supported=False,
                application_method=ApplicationMethod.MANUAL,
                messaging_supported=False,
                requires_user_confirmation=True,
                authorization_verified=False,
            ),
            jobs,
        )


class AtsMockAdapter(EmployerCareerSiteMockAdapter):
    def get_capabilities(self) -> SourceCapability:
        return self._capability.model_copy(update={"source_name": "ATS systems (mock)"})


class PermittedJobApiMockAdapter(MockJobSourceAdapter):
    def __init__(self, jobs: Iterable[SourceJobPayload] = ()) -> None:
        super().__init__(
            SourceCapability(
                source_name="Permitted job API (mock)",
                discovery_supported=True,
                discovery_method=DiscoveryMethod.API,
                application_supported=False,
                application_method=ApplicationMethod.MANUAL,
                messaging_supported=False,
                requires_user_confirmation=True,
                authorization_verified=False,
            ),
            jobs,
        )


class RssFeedMockAdapter(PermittedJobApiMockAdapter):
    def get_capabilities(self) -> SourceCapability:
        return self._capability.model_copy(
            update={"source_name": "RSS feeds (mock)", "discovery_method": DiscoveryMethod.FEED}
        )


class JobAlertEmailMockAdapter(PermittedJobApiMockAdapter):
    def get_capabilities(self) -> SourceCapability:
        return self._capability.model_copy(
            update={"source_name": "Job alert emails (mock)", "discovery_method": DiscoveryMethod.EMAIL}
        )
