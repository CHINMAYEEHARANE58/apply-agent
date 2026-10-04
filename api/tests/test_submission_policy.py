from app.job_sources.schemas import ApplicationMethod, DiscoveryMethod, SourceCapability
from app.security.submission_policy import SubmissionDecision, evaluate_submission_policy


def source(**overrides: object) -> SourceCapability:
    defaults: dict[str, object] = {
        "source_name": "Example Source",
        "discovery_supported": True,
        "discovery_method": DiscoveryMethod.API,
        "application_supported": True,
        "application_method": ApplicationMethod.AUTHORIZED_API,
        "messaging_supported": False,
        "requires_user_confirmation": False,
        "authorization_verified": True,
    }
    defaults.update(overrides)
    return SourceCapability.model_validate(defaults)


def test_unverified_source_can_never_submit() -> None:
    result = evaluate_submission_policy(source(authorization_verified=False))
    assert result.decision == SubmissionDecision.ASSISTED_MANUAL


def test_source_without_application_capability_is_manual() -> None:
    result = evaluate_submission_policy(source(application_supported=False))
    assert result.decision == SubmissionDecision.ASSISTED_MANUAL


def test_verified_application_capability_is_eligible_for_submitter() -> None:
    result = evaluate_submission_policy(source())
    assert result.decision == SubmissionDecision.AUTHORIZED_SUBMISSION
