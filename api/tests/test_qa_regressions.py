from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from test_authorization_isolation import create_user, headers

from app.ai.application_writing import MessageDeduplicationRegistry, generate_application_drafts
from app.applications.questions import CandidateAnswerVault
from app.jobs.discovery_schemas import NormalizedJob
from app.matching.engine import CandidateMatchingProfile, match_internship
from app.resumes.facts import ResumeFactStore


def test_jobs_api_requires_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/jobs").status_code == 401


@pytest.mark.parametrize("method", ["PATCH", "DELETE"])
def test_clerk_users_cannot_mutate_the_shared_job_catalog(
    client: TestClient, clerk_token: Callable[..., str], method: str
) -> None:
    request = {"headers": {"Authorization": f"Bearer {clerk_token()}"}}
    if method == "PATCH":
        request["json"] = {"location": "changed"}
    # Must reject the action before even disclosing whether a global job exists.
    assert client.request(method, f"/api/v1/jobs/{uuid4()}", **request).status_code == 403


@pytest.mark.parametrize("topic,question", [
    ("work_authorization", "Are you legally authorized to work here?"),
    ("start_date", "When can you start?"),
    ("notice_period", "What is your notice period?"),
    ("location", "Where are you currently based?"),
    ("relocation", "Are you willing to relocate?"),
])
def test_canonical_sensitive_answer_keys_are_not_lost(topic: str, question: str) -> None:
    value = "Candidate-supplied answer"
    answer = CandidateAnswerVault({topic: value}).answer(question, ResumeFactStore([]))
    assert answer.answer == value
    assert answer.kind == "static" and not answer.requires_user_review


def test_language_question_is_not_misclassified_as_age() -> None:
    facts = ResumeFactStore.from_parsed_resume({"skills": ["Programming languages: Python"]})
    answer = CandidateAnswerVault().answer("What programming languages have you used?", facts)
    assert answer.kind == "fact_backed" and answer.answer is not None


def test_recruiter_drafts_do_not_claim_an_application_was_submitted() -> None:
    facts = ResumeFactStore.from_parsed_resume({"skills": ["Python"], "projects": ["Built a Python API."]})
    job = NormalizedJob(source="test", source_job_id="one", url="https://example.com/jobs/one", company="Example", title="Software Intern", description="Build Python APIs", required_skills=["Python"], workplace_type="remote")
    match = match_internship(job, CandidateMatchingProfile(roles=["Software Intern"], minimum_match_score=0), facts)
    draft = generate_application_drafts(candidate_name="Test Candidate", job=job, match=match, fact_store=facts)
    assert draft.recruiter_message
    assert "I have applied" not in draft.recruiter_message


def test_preferred_skills_cannot_become_unverified_candidate_claims() -> None:
    facts = ResumeFactStore.from_parsed_resume({"skills": ["Python"], "projects": ["Built a Python API."]})
    job = NormalizedJob(source="test", source_job_id="one", url="https://example.com/jobs/one", company="Example", title="Software Intern", description="Build cloud APIs", required_skills=["AWS"], workplace_type="remote")
    match = match_internship(job, CandidateMatchingProfile(roles=["Software Intern"], skills=["AWS"], minimum_match_score=0), facts)
    draft = generate_application_drafts(candidate_name="Test Candidate", job=job, match=match, fact_store=facts)
    assert draft.recruiter_message
    assert "background in AWS" not in draft.recruiter_message
    assert draft.cover_letter and "interest in AWS" not in draft.cover_letter


def test_same_recruiter_is_not_contacted_again_for_another_job() -> None:
    registry = MessageDeduplicationRegistry()
    user_id = uuid4()
    registry.record_sent(user_id=user_id, job_url="https://example.com/job1", recruiter_identity=" Recruiter-1 ")
    assert not registry.can_send(user_id=user_id, job_url="https://example.com/job2", recruiter_identity="recruiter-1")


def test_application_can_progress_to_interview_without_losing_submission_date(client: TestClient) -> None:
    user_id = create_user(client, "tracker@example.com")
    auth = headers(user_id)
    job = client.post("/api/v1/jobs", headers=auth, json={"source": "test", "external_job_id": "tracking", "job_url": "https://example.com/tracking", "company": "Example", "title": "Intern", "description": "Test role", "fingerprint": "track" * 16}).json()
    submitted = datetime.now(UTC).isoformat()
    application = client.post("/api/v1/applications", headers=auth, json={"job_id": job["id"], "status": "submitted", "submitted_at": submitted}).json()
    response = client.patch(f'/api/v1/applications/{application["id"]}', headers=auth, json={"status": "interview"})
    assert response.status_code == 200
    assert response.json()["status"] == "interview"
    assert response.json()["submitted_at"] == application["submitted_at"]
