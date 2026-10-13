from app.applications.executors import (
    ApplicationPackage,
    AuthorizedApiExecutor,
    ManualApplicationExecutor,
)
from app.applications.policy import ApplicationPolicyService, SubmissionContext
from app.applications.questions import CandidateAnswerVault
from app.job_sources.schemas import ApplicationMethod, DiscoveryMethod, SourceCapability
from app.resumes.facts import ResumeFactStore


def _source() -> SourceCapability:
    return SourceCapability(
        source_name="reviewed",
        discovery_supported=True,
        discovery_method=DiscoveryMethod.API,
        application_supported=True,
        application_method=ApplicationMethod.API,
        messaging_supported=False,
        requires_user_confirmation=False,
        authorization_verified=True,
    )


def _context(**changes: object) -> SubmissionContext:
    values: dict[str, object] = {
        "job_exists": True,
        "hard_filters_passed": True,
        "match_score": 90,
        "resume_verified": True,
        "already_applied": False,
        "daily_limit_exceeded": False,
        "required_questions_answered": True,
        "uncertain_sensitive_answers": False,
        "captcha_present": False,
        "platform_restriction_blocks_automation": False,
        "idempotency_key": "idempotency-key-1234",
    }
    values.update(changes)
    return SubmissionContext(**values)


def test_sensitive_answers_are_only_returned_from_candidate_vault() -> None:
    facts = ResumeFactStore.from_parsed_resume({"projects": ["Built a Python API."]})
    vault = CandidateAnswerVault({"visa": "No sponsorship required"})
    assert (
        vault.answer("Will you require visa sponsorship?", facts).answer
        == "No sponsorship required"
    )
    assert vault.answer("What is your expected compensation?", facts).requires_user_review is True


def test_policy_fails_closed_for_captcha_and_uncertain_sensitive_answers() -> None:
    service = ApplicationPolicyService()
    assert service.evaluate_submission(_context(captcha_present=True), _source()).allowed is False
    assert (
        service.evaluate_submission(
            _context(uncertain_sensitive_answers=True), _source()
        ).next_status
        == "awaiting_user"
    )
    assert (
        service.evaluate_submission(_context(daily_limit_exceeded=True), _source()).allowed is False
    )


def test_executors_do_not_submit_and_idempotency_returns_existing_result() -> None:
    package = ApplicationPackage(None, None, {}, "https://jobs.example/1")
    executor = AuthorizedApiExecutor()
    first = executor.submit(package, _context(), _source())
    second = executor.submit(package, _context(), _source())
    assert first == second and first.status == "awaiting_user"
    assert (
        ManualApplicationExecutor().prepare(package, "manual-key-123456").status
        == "manual_application_required"
    )
