"""Evidence-bound application-question answers; sensitive values are never inferred."""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping
from typing import Literal

from pydantic import Field

from app.config.schemas import APIModel
from app.resumes.facts import ResumeFactStore

AnswerKind = Literal["static", "fact_backed", "requires_user_review"]
_STATIC_TOPICS = {
    "work_authorization",
    "visa",
    "citizenship",
    "relocation",
    "start_date",
    "compensation",
    "salary",
    "notice_period",
    "age",
    "location",
}


class CandidateAnswer(APIModel):
    answer: str | None = Field(default=None, max_length=5_000)
    confidence: float = Field(ge=0, le=1)
    requires_user_review: bool
    kind: AnswerKind
    supporting_fact_ids: list[uuid.UUID] = Field(default_factory=list)


class CandidateAnswerVault:
    """Candidate-controlled static answers plus verified source facts.

    Static answers are supplied by the candidate/application workflow, never
    produced or completed by an LLM.
    """

    def __init__(self, static_answers: Mapping[str, str] | None = None) -> None:
        self._static = {
            self._topic(key): value.strip()
            for key, value in (static_answers or {}).items()
            if value.strip()
        }

    def answer(self, question: str, facts: ResumeFactStore) -> CandidateAnswer:
        topic = self._topic(question)
        if topic in _STATIC_TOPICS:
            value = self._static.get(topic)
            return CandidateAnswer(
                answer=value,
                confidence=1.0 if value else 0.0,
                requires_user_review=not bool(value),
                kind="static",
            )
        relevant = [
            fact
            for fact in facts.facts
            if fact.confidence >= 0.8 and self._overlaps(question, fact.text)
        ]
        if not relevant:
            return CandidateAnswer(
                answer=None, confidence=0.0, requires_user_review=True, kind="requires_user_review"
            )
        fact = relevant[0]
        return CandidateAnswer(
            answer=fact.text,
            confidence=fact.confidence,
            requires_user_review=fact.confidence < 0.8,
            kind="fact_backed",
            supporting_fact_ids=[fact.fact_id],
        )

    @staticmethod
    def _topic(value: str) -> str:
        lowered = " ".join(value.casefold().replace("_", " ").replace("-", " ").split())
        canonical = {topic.replace("_", " "): topic for topic in _STATIC_TOPICS}
        if lowered in canonical:
            return "compensation" if canonical[lowered] == "salary" else canonical[lowered]
        if any(word in lowered for word in ("authorized to work", "work authorization", "eligible to work", "right to work")):
            return "work_authorization"
        if "sponsor" in lowered or "visa" in lowered:
            return "visa"
        if "citizen" in lowered or "citizenship" in lowered:
            return "citizenship"
        if "relocat" in lowered:
            return "relocation"
        if "start date" in lowered or "available" in lowered or "can you start" in lowered or "can you join" in lowered:
            return "start_date"
        if re.search(r"\b(salary|compensation|pay|stipend)\b", lowered):
            return "compensation"
        if "notice" in lowered:
            return "notice_period"
        if re.search(r"\bage\b|\bhow old\b|\bdate of birth\b", lowered):
            return "age"
        if "location" in lowered or "currently based" in lowered or "where do you live" in lowered:
            return "location"
        return "fact_backed"

    @staticmethod
    def _overlaps(question: str, fact: str) -> bool:
        terms = {term for term in question.casefold().split() if len(term) > 3}
        return bool(terms & set(fact.casefold().split()))
