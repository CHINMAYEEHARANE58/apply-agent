from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest
from pydantic import ValidationError
from test_application_policy_foundations import _context, _source

from app.applications.executors import ApplicationPackage, AuthorizedApiExecutor
from app.applications.policy import ApplicationPolicyService
from app.applications.questions import CandidateAnswerVault
from app.resumes.facts import ResumeFactStore
from app.scheduler.daily import DailySearchService, DailySearchSettings


@pytest.mark.parametrize("change", [
    {"job_exists": False}, {"hard_filters_passed": False}, {"match_score": 74},
    {"resume_verified": False}, {"already_applied": True}, {"daily_limit_exceeded": True},
    {"required_questions_answered": False}, {"uncertain_sensitive_answers": True},
    {"captcha_present": True}, {"platform_restriction_blocks_automation": True},
])
def test_each_policy_gate_independently_blocks_submission(change) -> None:
    result = ApplicationPolicyService().evaluate_submission(_context(**change), _source())
    assert not result.allowed and result.requires_user_confirmation and result.reason


def test_source_permission_and_confirmation_cannot_be_overridden() -> None:
    service = ApplicationPolicyService()
    for changes in [{"application_supported": False}, {"authorization_verified": False}, {"application_supported": False, "authorization_verified": False}]:
        result = service.evaluate_submission(_context(), _source().model_copy(update=changes))
        assert not result.allowed and result.next_status == "manual_application_required"
    source = _source().model_copy(update={"requires_user_confirmation": True})
    result = AuthorizedApiExecutor().submit(ApplicationPackage(None, None, {}, "https://example.com/jobs"), _context(), source)
    assert result.status == "awaiting_user"


@pytest.mark.parametrize("question", ["Are you authorized to work here?", "Do you require visa sponsorship?", "Expected salary?", "When can you start?", "Are you willing to relocate?", "What is your notice period?", "What is your current location?", "How old are you?"])
def test_unknown_sensitive_answers_never_guess_even_from_overlapping_resume_text(question) -> None:
    facts = ResumeFactStore.from_parsed_resume({"experience": [question + " Potentially misleading resume text."]})
    result = CandidateAnswerVault().answer(question, facts)
    assert result.answer is None and result.requires_user_review and result.confidence == 0


@pytest.mark.parametrize("values", [{"search_time": "29:00"}, {"timezone": "Unknown/Timezone"}, {"maximum_jobs_evaluated_daily": -1}, {"maximum_applications_prepared_daily": -1}, {"maximum_applications_submitted_daily": 51}, {"minimum_match_score": 101}])
def test_scheduler_settings_are_validated(values) -> None:
    with pytest.raises(ValidationError):
        DailySearchSettings(**values)


def test_daily_lock_excludes_concurrent_runs_and_preserves_timezone() -> None:
    started, finish = Event(), Event()
    seen = []
    class Pipeline:
        def run(self, user_id, settings):
            seen.append(settings.timezone)
            started.set()
            assert finish.wait(5)
            return {"jobs_evaluated": 1}
    service = DailySearchService(Pipeline())
    user = uuid4()
    settings = DailySearchSettings(timezone="Asia/Kolkata")
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(service.run, user, settings)
        assert started.wait(5)
        try:
            assert service.run(user, settings)["status"] == "already_running"
        finally:
            finish.set()
        assert first.result()["jobs_evaluated"] == 1
    assert seen == ["Asia/Kolkata"] and user not in service.lock.held


@pytest.mark.parametrize("failure", [TimeoutError, ConnectionError, PermissionError, ValueError])
def test_daily_failure_releases_lock_without_fake_success_or_unbounded_retry(failure) -> None:
    class Pipeline:
        def run(self, user_id, settings):
            raise failure("controlled fixture failure")
    service = DailySearchService(Pipeline())
    user = uuid4()
    with pytest.raises(failure):
        service.run(user, DailySearchSettings())
    assert user not in service.lock.held
    assert service.run(user, DailySearchSettings(search_enabled=False))["status"] == "disabled"
