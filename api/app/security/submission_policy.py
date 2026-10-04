from dataclasses import dataclass
from enum import StrEnum

from app.job_sources.schemas import SourceCapability


class SubmissionDecision(StrEnum):
    ASSISTED_MANUAL = "assisted_manual"
    AUTHORIZED_SUBMISSION = "authorized_submission"


@dataclass(frozen=True)
class PolicyResult:
    decision: SubmissionDecision
    reason: str


def evaluate_submission_policy(source: SourceCapability) -> PolicyResult:
    """Return the only permitted path; never call integrations from this layer."""
    if not source.authorization_verified:
        return PolicyResult(
            decision=SubmissionDecision.ASSISTED_MANUAL,
            reason="The source authorization has not been verified.",
        )
    if not source.application_supported:
        return PolicyResult(
            decision=SubmissionDecision.ASSISTED_MANUAL,
            reason="This source does not support authorized application submission.",
        )
    return PolicyResult(
        decision=SubmissionDecision.AUTHORIZED_SUBMISSION,
        reason="Source authorization and application capability are verified.",
    )
