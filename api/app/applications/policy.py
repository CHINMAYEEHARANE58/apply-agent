"""Fail-closed application policy gateway. This service never submits."""

from __future__ import annotations

from pydantic import Field

from app.config.schemas import APIModel
from app.job_sources.schemas import SourceCapability


class SubmissionContext(APIModel):
    job_exists: bool
    hard_filters_passed: bool
    match_score: int = Field(ge=0, le=100)
    minimum_match_score: int = Field(default=75, ge=0, le=100)
    resume_verified: bool
    already_applied: bool
    daily_limit_exceeded: bool
    required_questions_answered: bool
    uncertain_sensitive_answers: bool
    captcha_present: bool
    platform_restriction_blocks_automation: bool
    idempotency_key: str = Field(min_length=16, max_length=255)


class SubmissionPolicyResult(APIModel):
    allowed: bool
    reason: str
    requires_user_confirmation: bool
    next_status: str


class ApplicationPolicyService:
    def evaluate_submission(
        self, application: SubmissionContext, source: SourceCapability
    ) -> SubmissionPolicyResult:
        failures = (
            (not application.job_exists, "The job no longer exists."),
            (not application.hard_filters_passed, "The candidate did not pass hard filters."),
            (
                application.match_score < application.minimum_match_score,
                "The match score is below the configured threshold.",
            ),
            (
                not application.resume_verified,
                "The tailored resume has not passed factual verification.",
            ),
            (application.already_applied, "An application already exists for this job."),
            (application.daily_limit_exceeded, "The daily application limit has been reached."),
            (
                not application.required_questions_answered,
                "Required application questions are incomplete.",
            ),
            (application.uncertain_sensitive_answers, "Sensitive answers require user review."),
            (
                not source.application_supported or not source.authorization_verified,
                "The source lacks verified application authorization.",
            ),
            (application.captcha_present, "CAPTCHA is present; automation is prohibited."),
            (
                application.platform_restriction_blocks_automation,
                "Platform restrictions block automation.",
            ),
        )
        for failed, reason in failures:
            if failed:
                manual = (
                    "authorization" in reason or "CAPTCHA" in reason or "restrictions" in reason
                )
                return SubmissionPolicyResult(
                    allowed=False,
                    reason=reason,
                    requires_user_confirmation=True,
                    next_status="manual_application_required" if manual else "awaiting_user",
                )
        return SubmissionPolicyResult(
            allowed=True,
            reason="All deterministic submission checks passed.",
            requires_user_confirmation=source.requires_user_confirmation,
            next_status="awaiting_user" if source.requires_user_confirmation else "ready_to_submit",
        )
