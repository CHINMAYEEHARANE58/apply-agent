"""Truthful application-writing drafts with explicit messaging permission gates.

This module only prepares text. It has no network client and no submission or
messaging endpoint, so an LLM/draft cannot directly contact an employer.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from pydantic import Field

from app.config.schemas import APIModel
from app.job_sources.schemas import SourceCapability
from app.jobs.discovery_schemas import NormalizedJob
from app.matching.engine import MatchResult
from app.resumes.facts import ResumeFact, ResumeFactStore


class ApplicationWritingDraft(APIModel):
    status: str
    cover_letter: str | None = None
    recruiter_message: str | None = None
    application_introduction: str | None = None
    supporting_fact_ids: list[uuid.UUID] = Field(default_factory=list)
    review_reason: str | None = None


@dataclass
class MessageDeduplicationRegistry:
    """Small deterministic guard; persistent sending must enforce this too."""

    _sent_keys: set[tuple[uuid.UUID, str, str]] = field(default_factory=set)

    def can_send(self, *, user_id: uuid.UUID, job_url: str, recruiter_identity: str) -> bool:
        return (user_id, job_url.casefold(), recruiter_identity.casefold()) not in self._sent_keys

    def record_sent(self, *, user_id: uuid.UUID, job_url: str, recruiter_identity: str) -> None:
        self._sent_keys.add((user_id, job_url.casefold(), recruiter_identity.casefold()))


def may_send_recruiter_message(
    *,
    capability: SourceCapability,
    messaging_enabled: bool,
    user_id: uuid.UUID,
    job_url: str,
    recruiter_identity: str,
    deduplication: MessageDeduplicationRegistry,
) -> bool:
    """Return permission only; the caller still needs a permitted send path."""

    return (
        messaging_enabled
        and capability.messaging_supported
        and capability.authorization_verified
        and deduplication.can_send(
            user_id=user_id, job_url=job_url, recruiter_identity=recruiter_identity
        )
    )


def generate_application_drafts(
    *,
    candidate_name: str,
    job: NormalizedJob,
    match: MatchResult,
    fact_store: ResumeFactStore,
) -> ApplicationWritingDraft:
    """Generate reviewable drafts grounded only in cited candidate facts."""

    if not match.recommended:
        return ApplicationWritingDraft(
            status="SKIPPED_LOW_MATCH",
            review_reason="The job did not meet the configured application-writing threshold.",
        )

    facts = _relevant_facts(fact_store, match)
    if not facts:
        return ApplicationWritingDraft(
            status="REQUIRES_REVIEW",
            review_reason="No trusted candidate facts are available for a truthful application draft.",
        )
    skill_text = ", ".join(match.matched_skills[:4]) or "the relevant skills in my background"
    evidence = facts[0].text
    requested = ", ".join(job.required_skills[:4]) or "the role requirements"
    name = candidate_name.strip() or "the candidate"
    cover_letter = _cover_letter(
        name=name,
        title=job.title,
        company=job.company,
        skills=skill_text,
        evidence=evidence,
        requested=requested,
    )
    recruiter_message = _recruiter_message(name, job.title, job.company, skill_text, evidence)
    introduction = _introduction(name, job.title, skill_text, evidence)
    return ApplicationWritingDraft(
        status="READY_FOR_REVIEW",
        cover_letter=cover_letter,
        recruiter_message=recruiter_message,
        application_introduction=introduction,
        supporting_fact_ids=[fact.fact_id for fact in facts],
    )


def _relevant_facts(fact_store: ResumeFactStore, match: MatchResult) -> list[ResumeFact]:
    wanted = {skill.casefold() for skill in match.matched_skills}
    eligible = [
        fact
        for fact in fact_store.facts
        if fact.confidence >= 0.8
        and fact.category in {"skills", "experience", "internships", "projects", "achievements", "summary"}
    ]
    return sorted(
        eligible,
        key=lambda fact: (
            -sum(skill in fact.text.casefold() for skill in wanted),
            fact.category,
            fact.text.casefold(),
        ),
    )[:5]


def _cover_letter(*, name: str, title: str, company: str, skills: str, evidence: str, requested: str) -> str:
    """Keep this company-neutral unless information was actually supplied."""

    return (
        f"Dear Hiring Team,\n\n"
        f"I am writing to express my interest in the {title} opportunity at {company}. "
        f"The role aligns with my interest in {skills}. My source resume includes the following "
        f"relevant experience or project detail: {evidence}. I would welcome the chance to bring "
        f"that foundation to an internship setting while learning from the team.\n\n"
        f"I reviewed the role requirements, including {requested}, and I have focused my preparation "
        f"on applying my existing skills carefully, communicating clearly, and improving through "
        f"feedback. I value opportunities where I can contribute dependable work, ask thoughtful "
        f"questions, and collaborate constructively with others. I am especially interested in this "
        f"position because it provides a focused way to develop the skills most relevant to the work "
        f"described in the listing, without overstating experience I do not have.\n\n"
        f"Thank you for considering my application. I would appreciate the opportunity to discuss how "
        f"my background and interest in this internship could support the role.\n\nSincerely,\n{name}"
    )


def _recruiter_message(name: str, title: str, company: str, skills: str, evidence: str) -> str:
    message = (
        f"Hi, I came across the {title} internship at {company}. It aligns with my background in "
        f"{skills}; my resume includes: {evidence}. I have applied and would appreciate your "
        f"consideration. Thanks, {name}"
    )
    return message[:500]


def _introduction(name: str, title: str, skills: str, evidence: str) -> str:
    return (
        f"I am {name}, applying for the {title} role. My relevant background includes {skills} "
        f"and this source-backed experience: {evidence}."
    )
