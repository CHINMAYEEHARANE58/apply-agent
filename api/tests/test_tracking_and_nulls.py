from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from test_authorization_isolation import create_user, headers

from app.applications.schemas import ApplicationUpdate
from app.applications.tracking import TrackedApplication, application_analytics
from app.jobs.schemas_v2 import JobMatchUpdate, JobUpdate


@pytest.mark.parametrize("field", ["score", "hard_filter_passed", "matched_skills", "missing_skills", "explanation"])
def test_match_patch_cannot_null_required_fields(field) -> None:
    with pytest.raises(ValidationError):
        JobMatchUpdate(**{field: None})


def test_null_application_status_and_job_skills_are_validation_errors() -> None:
    with pytest.raises(ValidationError):
        ApplicationUpdate(status=None)
    with pytest.raises(ValidationError):
        JobUpdate(skills=None)


def test_empty_analytics_are_zero_not_demo_counts() -> None:
    result = application_analytics([])
    assert result["applications_this_week"] == result["average_match_score"] == 0
    assert result["response_rate"] == result["interview_rate"] == 0
    assert result["applications_by_role"] == {}


def test_tracking_keeps_a_timeline_and_counts_actual_outcomes() -> None:
    now = datetime.now(UTC)
    submitted = TrackedApplication("Acme", "Software Intern", "Pune", "Manual", 80, "v1", now, status="submitted")
    submitted.update_status("interview", note="Candidate confirmed interview")
    old = TrackedApplication("Other", "Design Intern", "London", "Feed", 60, None, now - timedelta(days=8), status="rejected")
    metrics = application_analytics([submitted, old], now=now)
    assert metrics["applications_this_week"] == 1
    assert metrics["average_match_score"] == 70
    assert metrics["response_rate"] == 1 and metrics["interview_rate"] == 0.5
    assert submitted.timeline[-1].note == "Candidate confirmed interview"


def test_inconsistent_status_updates_are_rejected_before_commit(client) -> None:
    user = create_user(client, "metadata@example.com")
    auth = headers(user)
    job = client.post("/api/v1/jobs", headers=auth, json={"source": "fixture", "external_job_id": "metadata", "job_url": "https://example.com/metadata", "company": "Example", "title": "Intern", "description": "Fixture", "fingerprint": "metadata" * 8}).json()
    application = client.post("/api/v1/applications", headers=auth, json={"job_id": job["id"], "status": "prepared"}).json()
    response = client.patch(f'/api/v1/applications/{application["id"]}', headers=auth, json={"submitted_at": datetime.now(UTC).isoformat()})
    assert response.status_code == 422
    persisted = client.get(f'/api/v1/applications/{application["id"]}', headers=auth).json()
    assert persisted["submitted_at"] is None and persisted["status"] == "prepared"
