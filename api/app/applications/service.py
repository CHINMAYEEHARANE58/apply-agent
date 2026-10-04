from dataclasses import dataclass

from app.job_sources.schemas import SourceCapability
from app.security.submission_policy import SubmissionDecision, evaluate_submission_policy


@dataclass(frozen=True)
class ApplicationPreparation:
    decision: SubmissionDecision
    reason: str
    open_application_required: bool


def prepare_application(source: SourceCapability) -> ApplicationPreparation:
    """Prepare an allowed path; actual submission remains an explicit adapter."""
    result = evaluate_submission_policy(source)
    return ApplicationPreparation(
        decision=result.decision,
        reason=result.reason,
        open_application_required=result.decision == SubmissionDecision.ASSISTED_MANUAL,
    )
