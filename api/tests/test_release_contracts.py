"""Mandatory product contracts. Missing implementations remain real failures.

These are not xfails/skips. A green foundation suite must never mask missing
settings, saved-job, dashboard, or daily-pipeline production functionality.
"""
import pytest
from fastapi.testclient import TestClient
from test_authorization_isolation import create_user, headers

from app.scheduler.tasks import daily_internship_search

pytestmark = pytest.mark.release


def test_authenticated_dashboard_returns_real_owner_scoped_counts(client: TestClient) -> None:
    user = create_user(client, "release-dashboard@example.com")
    response = client.get("/api/v1/dashboard", headers=headers(user))
    assert response.status_code == 200, "Required persistent dashboard API is missing"
    assert response.json()["applications_submitted"] == 0


def test_settings_can_be_persisted_through_the_authenticated_api(client: TestClient) -> None:
    user = create_user(client, "release-settings@example.com")
    response = client.put("/api/v1/settings/me", headers=headers(user), json={"search_enabled": False, "max_daily_applications": 3})
    assert response.status_code == 200, "UserSettings exists only as a model, not a working API"
    assert client.get("/api/v1/settings/me", headers=headers(user)).json()["max_daily_applications"] == 3


def test_saved_jobs_have_an_owner_scoped_persistence_api(client: TestClient) -> None:
    user = create_user(client, "release-jobs@example.com")
    job = client.post("/api/v1/jobs", headers=headers(user), json={"source": "qa", "external_job_id": "saved", "job_url": "https://example.com/saved", "company": "QA", "title": "Intern", "description": "Fixture", "fingerprint": "saved" * 16}).json()
    response = client.patch(f'/api/v1/jobs/{job["id"]}/state', headers=headers(user), json={"saved": True})
    assert response.status_code == 200, "Saved jobs currently exist only in React memory / a model"


def test_daily_task_runs_the_pipeline_instead_of_returning_a_placeholder(client: TestClient) -> None:
    user = create_user(client, "release-scheduler@example.com")
    client.put("/api/v1/preferences/me", headers=headers(user), json={"search_enabled": True})
    result = daily_internship_search.run(user)
    assert "jobs_evaluated" in result, "Daily Celery task does not load/persist or run the daily pipeline"
