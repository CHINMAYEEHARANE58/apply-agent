from decimal import Decimal

from app.job_sources.adapters import (
    IndeedDiscoveryLinkAdapter,
    JobAlertEmailMockAdapter,
    LinkedInDiscoveryLinkAdapter,
    PermittedJobApiMockAdapter,
)
from app.job_sources.schemas import ApplicationMethod, DiscoveryMethod
from app.jobs.discovery import JobDeduplicator, are_reasonable_duplicates, job_fingerprint
from app.jobs.discovery_schemas import JobSearchQuery, SourceJobPayload


def _payload(*, source_id: str, url: str, description: str = "Build Python services with FastAPI.") -> SourceJobPayload:
    return SourceJobPayload(
        source_job_id=source_id,
        url=url,
        company="Acme",
        title="Backend Engineering Intern",
        description=description,
        required_skills=["Python", "FastAPI"],
        preferred_skills=["PostgreSQL"],
        location="Bengaluru, India",
        workplace_type="hybrid",
        stipend_min=Decimal("1000"),
        currency="usd",
    )


def test_mock_adapter_normalizes_to_the_common_job_schema() -> None:
    adapter = PermittedJobApiMockAdapter([_payload(source_id="one", url="https://jobs.example/one")])

    raw = adapter.search_jobs(JobSearchQuery(roles=["Backend"]))[0]
    job = adapter.normalize_job(raw)

    assert job.source == "Permitted job API (mock)"
    assert job.currency == "USD"
    assert job.required_skills == ["Python", "FastAPI"]


def test_link_only_sources_never_assume_automation_or_application_permission() -> None:
    for adapter in (LinkedInDiscoveryLinkAdapter(), IndeedDiscoveryLinkAdapter()):
        capability = adapter.get_capabilities()
        assert capability.discovery_method is DiscoveryMethod.MANUAL
        assert capability.application_supported is False
        assert capability.application_method is ApplicationMethod.MANUAL
        assert capability.authorization_verified is False


def test_email_mock_declares_email_discovery_without_application_permission() -> None:
    capability = JobAlertEmailMockAdapter().get_capabilities()
    assert capability.discovery_method is DiscoveryMethod.EMAIL
    assert capability.application_supported is False


def test_deduplicator_tracks_every_original_source_url() -> None:
    first = PermittedJobApiMockAdapter([_payload(source_id="one", url="https://jobs.example/one")])
    second = IndeedDiscoveryLinkAdapter(
        [
            _payload(
                source_id="two",
                url="https://indeed.example/two",
                description="Services Build Python with FastAPI.",
            )
        ]
    )
    first_raw = first.get_job("one")
    second_raw = second.get_job("two")
    assert first_raw is not None and second_raw is not None
    first_job = first.normalize_job(first_raw)
    second_job = second.normalize_job(second_raw)

    deduplicator = JobDeduplicator()
    item, duplicate = deduplicator.add(first_job)
    merged, was_duplicate = deduplicator.add(second_job)

    assert duplicate is False
    assert was_duplicate is True
    assert item.canonical_job == merged.canonical_job
    assert set(merged.source_urls) == {"https://jobs.example/one", "https://indeed.example/two"}
    assert are_reasonable_duplicates(first_job, second_job)
    assert job_fingerprint(first_job)


def test_distinct_descriptions_do_not_merge_on_company_and_title_alone() -> None:
    adapter = PermittedJobApiMockAdapter()
    left = adapter.normalize_job(_payload(source_id="one", url="https://jobs.example/one"))
    right = adapter.normalize_job(
        _payload(
            source_id="two",
            url="https://jobs.example/two",
            description="Design hardware circuits and validate board layouts.",
        )
    )
    assert are_reasonable_duplicates(left, right) is False
