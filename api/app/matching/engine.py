"""Two-stage deterministic internship matching.

No model, browser, tool, URL fetcher, or instruction interpreter participates
in this module. Job descriptions are tokenized as untrusted data only.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator

from app.config.schemas import APIModel
from app.jobs.discovery import normalized_text
from app.jobs.discovery_schemas import NormalizedJob
from app.resumes.facts import ResumeFactStore

_WORD_RE = re.compile(r"[a-z][a-z0-9+#.]{1,}")
_COMMON_TERMS = frozenset(
    {"and", "candidate", "experience", "intern", "internship", "job", "role", "skills", "the", "with"}
)


class CandidateMatchingProfile(APIModel):
    roles: list[str] = Field(default_factory=list, max_length=50)
    # Desired technologies help search, but are not proof of qualifications.
    skills: list[str] = Field(default_factory=list, max_length=200)
    preferred_locations: list[str] = Field(default_factory=list, max_length=100)
    preferred_countries: list[str] = Field(default_factory=list, max_length=100)
    preferred_states: list[str] = Field(default_factory=list, max_length=100)
    preferred_cities: list[str] = Field(default_factory=list, max_length=100)
    remote_allowed: bool = True
    hybrid_allowed: bool = True
    onsite_allowed: bool = False
    min_duration: int | None = Field(default=None, ge=1, le=104)
    max_duration: int | None = Field(default=None, ge=1, le=104)
    duration_unit: Literal["weeks", "months"] = "weeks"
    minimum_stipend: Decimal | None = Field(default=None, ge=0)
    currency: str | None = None
    excluded_companies: list[str] = Field(default_factory=list, max_length=100)
    excluded_keywords: list[str] = Field(default_factory=list, max_length=100)
    work_authorization: str | None = None
    minimum_match_score: int = Field(default=70, ge=0, le=100)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class HardFilterResult(APIModel):
    passed: bool
    rejection_reasons: list[str] = Field(default_factory=list)


class MatchResult(APIModel):
    score: int = Field(ge=0, le=100)
    recommended: bool
    matched_skills: list[str] = Field(default_factory=list)
    missing_required_skills: list[str] = Field(default_factory=list)
    missing_optional_skills: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    explanation: str
    confidence: float = Field(ge=0, le=1)
    hard_filter: HardFilterResult


def apply_hard_filters(job: NormalizedJob, profile: CandidateMatchingProfile) -> HardFilterResult:
    """Enforce non-negotiable preferences without any AI override path."""

    reasons: list[str] = []
    title = normalized_text(job.title)
    description = job.description.casefold()

    if profile.roles and not any(normalized_text(role) in title for role in profile.roles):
        reasons.append("The job title is outside the configured internship roles.")

    if job.workplace_type == "remote" and not profile.remote_allowed:
        reasons.append("Remote work is not allowed by the candidate preference.")
    if job.workplace_type == "hybrid" and not profile.hybrid_allowed:
        reasons.append("Hybrid work is not allowed by the candidate preference.")
    if job.workplace_type == "onsite" and not profile.onsite_allowed:
        reasons.append("Onsite work is not allowed by the candidate preference.")
    if job.workplace_type != "remote":
        normalized_location = normalized_text(job.location)
        for group, choices in [("location", profile.preferred_locations), ("country", profile.preferred_countries), ("state", profile.preferred_states), ("city", profile.preferred_cities)]:
            if choices and (not normalized_location or not any(normalized_text(choice) and f" {normalized_text(choice)} " in f" {normalized_location} " for choice in choices)):
                reasons.append(f"The job location does not establish the mandatory {group} preference.")

    if job.internship_duration is not None:
        duration = _duration_in_profile_unit(job.internship_duration.value, job.internship_duration.unit, profile.duration_unit)
        if profile.min_duration is not None and duration < profile.min_duration:
            reasons.append("The internship duration is below the configured minimum.")
        if profile.max_duration is not None and duration > profile.max_duration:
            reasons.append("The internship duration is above the configured maximum.")

    if profile.minimum_stipend is not None:
        if job.currency != (profile.currency or job.currency):
            reasons.append("The job stipend currency cannot be compared to the strict minimum.")
        elif job.stipend_min is None or job.stipend_min < profile.minimum_stipend:
            reasons.append("The job stipend is below or does not establish the strict minimum.")

    normalized_company = normalized_text(job.company)
    if any(normalized_text(company) == normalized_company for company in profile.excluded_companies):
        reasons.append("The company is explicitly excluded.")
    for keyword in profile.excluded_keywords:
        term = keyword.casefold().strip()
        if term and term in f"{job.title} {description}".casefold():
            reasons.append(f"The job contains an excluded keyword: {keyword}.")
            break

    if _eligibility_clearly_fails(job.eligibility, profile.work_authorization):
        reasons.append("The candidate work authorization clearly does not meet the job eligibility requirement.")

    return HardFilterResult(passed=not reasons, rejection_reasons=reasons)


def match_internship(
    job: NormalizedJob,
    profile: CandidateMatchingProfile,
    facts: ResumeFactStore,
    *,
    now: datetime | None = None,
) -> MatchResult:
    """Run deterministic filtering first, then score evidence against job data."""

    hard_filter = apply_hard_filters(job, profile)
    candidate_skills = _candidate_skills(facts)
    required = _unique(job.required_skills)
    preferred = _unique(job.preferred_skills)
    matched_skills = [skill for skill in required if _has_skill(skill, candidate_skills)]
    missing_required = [skill for skill in required if skill not in matched_skills]
    missing_optional = [skill for skill in preferred if not _has_skill(skill, candidate_skills)]

    role_score = _role_score(job, profile)
    required_score = _ratio_score(len(matched_skills), len(required), 25)
    evidence_score = _evidence_score(job, facts)
    location_score = _location_score(job, profile)
    compensation_score = _compensation_score(job, profile)
    duration_score = _duration_score(job, profile)
    preferred_score = _ratio_score(len(preferred) - len(missing_optional), len(preferred), 5)
    recency_score = _recency_score(job, now or datetime.now(UTC))
    score = round(
        role_score
        + required_score
        + evidence_score
        + location_score
        + compensation_score
        + duration_score
        + preferred_score
        + recency_score
    )

    strengths = [
        f"Matches required skill: {skill}" for skill in matched_skills[:5]
    ]
    if evidence_score >= 10:
        strengths.append("Candidate project or experience facts overlap with job terminology.")
    concerns = list(hard_filter.rejection_reasons)
    if missing_required:
        concerns.append("Missing required skills: " + ", ".join(missing_required[:5]))
    if job.description and _contains_untrusted_instruction(job.description):
        concerns.append("Prompt-like text in the job description was treated only as untrusted data.")

    recommended = hard_filter.passed and score >= profile.minimum_match_score
    explanation = _explanation(score, recommended, hard_filter, matched_skills, missing_required)
    confidence = _confidence(job, required, facts)
    return MatchResult(
        # A hard-filtered role must never appear competitive simply because it
        # has keyword overlap. Keeping this deterministic also prevents a
        # future semantic model from overriding an explicit preference.
        score=score if hard_filter.passed else 0,
        recommended=recommended,
        matched_skills=matched_skills,
        missing_required_skills=missing_required,
        missing_optional_skills=missing_optional,
        strengths=strengths,
        concerns=concerns,
        explanation=explanation,
        confidence=confidence,
        hard_filter=hard_filter,
    )


def _candidate_skills(facts: ResumeFactStore) -> list[str]:
    return _unique([fact.text for fact in facts.facts if fact.confidence >= 0.8 and fact.category in {"skills", "experience", "internships", "projects"}])


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value.casefold() not in seen:
            result.append(value)
            seen.add(value.casefold())
    return result


def _has_skill(skill: str, candidate_skills: list[str]) -> bool:
    pattern = re.compile(r"(?<![\w+#.])" + re.escape(skill.strip()) + r"(?![\w+#]|\.[\w])", re.IGNORECASE)
    return any(pattern.search(candidate) is not None for candidate in candidate_skills)


def has_verified_skill(skill: str, facts: ResumeFactStore) -> bool:
    return _has_skill(skill, _candidate_skills(facts))


def _ratio_score(matched: int, total: int, weight: int) -> float:
    return weight if total == 0 else weight * matched / total


def _role_score(job: NormalizedJob, profile: CandidateMatchingProfile) -> float:
    if not profile.roles:
        return 12.5
    return 25.0 if any(normalized_text(role) in normalized_text(job.title) for role in profile.roles) else 0.0


def _evidence_score(job: NormalizedJob, facts: ResumeFactStore) -> float:
    job_terms = _terms(" ".join([job.title, *job.required_skills, *job.preferred_skills, job.description]))
    evidence_terms = _terms(
        " ".join(
            fact.text for fact in facts.facts if fact.category in {"experience", "internships", "projects"}
        )
    )
    if not job_terms or not evidence_terms:
        return 0.0
    return min(20.0, 20.0 * len(job_terms & evidence_terms) / min(8, len(job_terms)))


def _location_score(job: NormalizedJob, profile: CandidateMatchingProfile) -> float:
    if job.workplace_type == "remote":
        return 10.0 if profile.remote_allowed else 0.0
    if job.workplace_type == "hybrid":
        return 10.0 if profile.hybrid_allowed else 0.0
    if job.workplace_type == "onsite":
        return 10.0 if profile.onsite_allowed else 0.0
    return 5.0


def _compensation_score(job: NormalizedJob, profile: CandidateMatchingProfile) -> float:
    if profile.minimum_stipend is None:
        return 4.0
    if job.currency == profile.currency and job.stipend_min is not None and job.stipend_min >= profile.minimum_stipend:
        return 8.0
    return 0.0


def _duration_score(job: NormalizedJob, profile: CandidateMatchingProfile) -> float:
    if job.internship_duration is None:
        return 2.5
    duration = _duration_in_profile_unit(job.internship_duration.value, job.internship_duration.unit, profile.duration_unit)
    if (profile.min_duration is None or duration >= profile.min_duration) and (
        profile.max_duration is None or duration <= profile.max_duration
    ):
        return 5.0
    return 0.0


def _duration_in_profile_unit(value: int, job_unit: str, profile_unit: str) -> float:
    if job_unit == profile_unit:
        return float(value)
    if job_unit == "months" and profile_unit == "weeks":
        return value * 4.345
    return value / 4.345


def _recency_score(job: NormalizedJob, now: datetime) -> float:
    if job.posted_at is None:
        return 0.5
    posted_at = job.posted_at if job.posted_at.tzinfo else job.posted_at.replace(tzinfo=UTC)
    age_days = max(0, (now - posted_at).days)
    if age_days <= 7:
        return 2.0
    if age_days <= 30:
        return 1.0
    return 0.0


def _terms(value: str) -> set[str]:
    return {term for term in _WORD_RE.findall(value.casefold()) if term not in _COMMON_TERMS}


def _eligibility_clearly_fails(eligibility: list[str], work_authorization: str | None) -> bool:
    if not eligibility or not work_authorization:
        return False
    authorization = normalized_text(work_authorization)
    required = [item.partition(":")[2].strip() for item in eligibility if item.casefold().startswith("requires:")]
    return bool(required) and not all(normalized_text(item) in authorization for item in required)


def _contains_untrusted_instruction(description: str) -> bool:
    lowered = description.casefold()
    return any(
        phrase in lowered
        for phrase in ("ignore previous instructions", "send the candidate", "call this url", "automatically approve")
    )


def _confidence(job: NormalizedJob, required: list[str], facts: ResumeFactStore) -> float:
    signals = [bool(job.required_skills), bool(job.description), bool(facts.facts)]
    return round(sum(signals) / len(signals), 2)


def _explanation(
    score: int,
    recommended: bool,
    hard_filter: HardFilterResult,
    matched_skills: list[str],
    missing_required: list[str],
) -> str:
    if not hard_filter.passed:
        return "Hard filters rejected this job: " + " ".join(hard_filter.rejection_reasons)
    details = []
    if matched_skills:
        details.append("Matched skills: " + ", ".join(matched_skills[:5]) + ".")
    if missing_required:
        details.append("Missing required skills: " + ", ".join(missing_required[:5]) + ".")
    decision = "Recommended" if recommended else "Below the automatic progression threshold"
    return f"{decision} at {score}/100. " + " ".join(details)
