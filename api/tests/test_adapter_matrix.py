import pytest
from pydantic import ValidationError

from app.job_sources import adapters
from app.jobs.discovery import JobDeduplicator, are_reasonable_duplicates
from app.jobs.discovery_schemas import JobSearchQuery, SourceJobPayload

ADAPTERS = [adapters.EmployerCareerSiteMockAdapter, adapters.AtsMockAdapter, adapters.PermittedJobApiMockAdapter, adapters.RssFeedMockAdapter, adapters.JobAlertEmailMockAdapter, adapters.LinkedInDiscoveryLinkAdapter, adapters.IndeedDiscoveryLinkAdapter, adapters.GlassdoorDiscoveryLinkAdapter, adapters.NaukriDiscoveryLinkAdapter]


@pytest.mark.parametrize("adapter_type", ADAPTERS)
def test_every_adapter_contract_uses_only_fixture_data(adapter_type) -> None:
    payload = SourceJobPayload(source_job_id="one", url="https://example.com/jobs/one", company="Acme", title="Software Intern", description="Build Python APIs using SQL and React.", required_skills=[" Python ", "Python", "React"])
    adapter = adapter_type([payload])
    assert adapter.search_jobs(JobSearchQuery(roles=["Software"], limit=1)) == (payload,)
    assert adapter.search_jobs(JobSearchQuery(roles=["Unrelated"])) == ()
    assert adapter.get_job("one") == payload and adapter.get_job("missing") is None
    job = adapter.normalize_job(payload)
    assert job.source == adapter.get_capabilities().source_name
    assert job.required_skills == ["Python", "React"]
    assert not adapter.get_capabilities().application_supported
    assert not adapter.get_capabilities().authorization_verified


@pytest.mark.parametrize("changes", [{"url": "javascript:alert(1)"}, {"title": ""}, {"workplace_type": "moon"}, {"stipend_min": -1}])
def test_invalid_normalized_job_data_is_rejected(changes) -> None:
    values = {"source_job_id": "one", "url": "https://example.com/jobs/one", "company": "Acme", "title": "Intern", "description": "Python", **changes}
    with pytest.raises(ValidationError):
        adapters.PermittedJobApiMockAdapter().normalize_job(SourceJobPayload(**values))


def test_duplicate_detection_handles_punctuation_and_keeps_all_urls() -> None:
    adapter = adapters.PermittedJobApiMockAdapter()
    first = adapter.normalize_job(SourceJobPayload(source_job_id="one", url="https://example.com/one", company="Acme, Inc.", title="Software Intern", location="Pune", description="Build Python APIs using SQL and React."))
    second = first.model_copy(update={"company": "ACME INC", "description": "Build Python APIs using SQL and React!", "source_job_id": "two", "url": "https://example.com/two"})
    assert are_reasonable_duplicates(first, second)
    rows = JobDeduplicator().extend([first, second])
    assert len(rows) == 1 and set(rows[0].source_urls) == {"https://example.com/one", "https://example.com/two"}


def test_exact_duplicates_with_no_significant_description_terms_are_deduplicated() -> None:
    job = adapters.PermittedJobApiMockAdapter().normalize_job(SourceJobPayload(source_job_id="one", url="https://example.com/one", company="Acme", title="Intern", description="An internship"))
    rows = JobDeduplicator().extend([job, job])
    assert len(rows) == 1
