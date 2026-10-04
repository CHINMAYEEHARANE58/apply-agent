"""Evidence-bound facts extracted from a candidate's approved source material.

This module intentionally has no file, database, LLM, or network access.  It
works only with already-parsed structured resume data and profile values that
the candidate has explicitly supplied.  Keeping the fact store deterministic
means downstream resume generation can be checked without trusting generated
content.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping
from types import MappingProxyType
from typing import Any, Literal

from pydantic import ConfigDict, Field, field_validator

from app.config.schemas import APIModel

FactCategory = Literal[
    "contact",
    "summary",
    "education",
    "experience",
    "internships",
    "projects",
    "skills",
    "certifications",
    "achievements",
    "links",
    "candidate_profile",
]
FactSource = Literal["master_resume", "candidate_profile"]

RESUME_FACT_CATEGORIES: tuple[FactCategory, ...] = (
    "contact",
    "summary",
    "education",
    "experience",
    "internships",
    "projects",
    "skills",
    "certifications",
    "achievements",
    "links",
)

_FACT_NAMESPACE = uuid.UUID("6a7023dc-37a8-492b-837f-e94204f7a34a")
_MAX_FACTS = 1_000
_MAX_NESTING = 16


class ResumeFact(APIModel):
    """One atomic, attributable statement from a trusted candidate source."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, frozen=True)

    fact_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    category: FactCategory
    text: str = Field(min_length=1, max_length=5_000)
    source: FactSource
    confidence: float = Field(ge=0, le=1)

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Fact text cannot be blank.")
        return normalized


class GeneratedResumeBullet(APIModel):
    """Generated text plus optional explicit evidence references.

    References are optional to support legacy generation prompts, but callers
    should provide them whenever possible.  When present, verification uses
    only the cited facts as evidence.
    """

    text: str = Field(min_length=1, max_length=2_000)
    supporting_fact_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Generated bullet text cannot be blank.")
        return normalized

    @field_validator("supporting_fact_ids")
    @classmethod
    def require_unique_references(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(set(value)) != len(value):
            raise ValueError("supporting_fact_ids must not contain duplicate fact IDs.")
        return value


class ResumeFactStore:
    """Immutable lookup of facts usable as evidence for a tailored resume."""

    def __init__(self, facts: Iterable[ResumeFact | Mapping[str, Any]]) -> None:
        supplied_facts = tuple(
            fact if isinstance(fact, ResumeFact) else ResumeFact.model_validate(fact) for fact in facts
        )
        if len(supplied_facts) > _MAX_FACTS:
            raise ValueError(f"A fact store cannot contain more than {_MAX_FACTS} facts.")

        facts_by_id = {fact.fact_id: fact for fact in supplied_facts}
        if len(facts_by_id) != len(supplied_facts):
            raise ValueError("Each resume fact must have a unique fact_id.")

        # A repeated line in a source resume is still one candidate fact.  This
        # mirrors the database's provenance uniqueness constraint and avoids a
        # failed upload solely because a PDF repeated a header or skill.
        normalized_facts: list[ResumeFact] = []
        seen_content: set[tuple[str, str, str]] = set()
        for fact in supplied_facts:
            content_key = (fact.category, fact.source, fact.text.casefold())
            if content_key not in seen_content:
                normalized_facts.append(fact)
                seen_content.add(content_key)

        self._facts = tuple(normalized_facts)
        self._facts_by_id = MappingProxyType({fact.fact_id: fact for fact in self._facts})

    @property
    def facts(self) -> tuple[ResumeFact, ...]:
        return self._facts

    def get(self, fact_id: uuid.UUID) -> ResumeFact | None:
        return self._facts_by_id.get(fact_id)

    def resolve(self, fact_ids: Iterable[uuid.UUID]) -> tuple[ResumeFact, ...]:
        return tuple(fact for fact_id in fact_ids if (fact := self.get(fact_id)) is not None)

    def missing_ids(self, fact_ids: Iterable[uuid.UUID]) -> tuple[uuid.UUID, ...]:
        return tuple(fact_id for fact_id in fact_ids if self.get(fact_id) is None)

    @classmethod
    def from_parsed_resume(
        cls,
        parsed_resume_json: Mapping[str, Any],
        candidate_profile: Mapping[str, Any] | None = None,
        *,
        resume_confidence: float = 1.0,
        profile_confidence: float = 1.0,
    ) -> ResumeFactStore:
        """Create facts from the supported structured-resume schema.

        The extractor only traverses JSON-compatible primitives, mappings, and
        lists.  It never calls ``str`` on arbitrary objects or evaluates input.
        Unknown top-level resume fields are deliberately ignored so only the
        documented source-of-truth schema reaches downstream generation.
        """

        if not isinstance(parsed_resume_json, Mapping):
            raise ValueError("parsed_resume_json must be a mapping.")

        _validate_confidence(resume_confidence, field_name="resume_confidence")
        _validate_confidence(profile_confidence, field_name="profile_confidence")

        facts: list[ResumeFact] = []
        for category in RESUME_FACT_CATEGORIES:
            if category not in parsed_resume_json:
                continue
            _append_json_facts(
                facts,
                value=parsed_resume_json[category],
                category=category,
                source="master_resume",
                confidence=resume_confidence,
                path=category,
                depth=0,
            )

        if candidate_profile is not None:
            if not isinstance(candidate_profile, Mapping):
                raise ValueError("candidate_profile must be a mapping when provided.")
            _append_candidate_profile_facts(facts, candidate_profile, profile_confidence)

        return cls(facts)


def _validate_confidence(value: float, *, field_name: str) -> None:
    if not 0 <= value <= 1:
        raise ValueError(f"{field_name} must be between 0 and 1.")


def _append_json_facts(
    facts: list[ResumeFact],
    *,
    value: Any,
    category: FactCategory,
    source: FactSource,
    confidence: float,
    path: str,
    depth: int,
) -> None:
    if depth > _MAX_NESTING:
        raise ValueError("Parsed resume exceeds the maximum supported nesting depth.")
    if len(facts) >= _MAX_FACTS:
        raise ValueError(f"A fact store cannot contain more than {_MAX_FACTS} facts.")

    if value is None:
        return
    if isinstance(value, str):
        if value.strip():
            facts.append(_make_fact(category, value, source, confidence, path))
        return
    if isinstance(value, bool):
        facts.append(_make_fact(category, "true" if value else "false", source, confidence, path))
        return
    if isinstance(value, int | float):
        facts.append(_make_fact(category, str(value), source, confidence, path))
        return
    if isinstance(value, Mapping):
        for key, nested_value in value.items():
            if not isinstance(key, str):
                raise ValueError("Parsed resume object keys must be strings.")
            _append_json_facts(
                facts,
                value=nested_value,
                category=category,
                source=source,
                confidence=confidence,
                path=f"{path}.{key}",
                depth=depth + 1,
            )
        return
    if isinstance(value, list | tuple):
        for index, nested_value in enumerate(value):
            _append_json_facts(
                facts,
                value=nested_value,
                category=category,
                source=source,
                confidence=confidence,
                path=f"{path}[{index}]",
                depth=depth + 1,
            )
        return

    raise ValueError("Parsed resume values must be JSON-compatible primitives, mappings, or lists.")


def _append_candidate_profile_facts(
    facts: list[ResumeFact], candidate_profile: Mapping[str, Any], confidence: float
) -> None:
    supported_fields = (
        "full_name",
        "phone",
        "location",
        "work_authorization",
        "relocation_allowed",
        "linkedin_url",
        "github_url",
        "portfolio_url",
    )
    for field_name in supported_fields:
        value = candidate_profile.get(field_name)
        if value is None:
            continue
        _append_json_facts(
            facts,
            value=value,
            category="candidate_profile",
            source="candidate_profile",
            confidence=confidence,
            path=f"candidate_profile.{field_name}",
            depth=0,
        )


def _make_fact(
    category: FactCategory,
    text: str,
    source: FactSource,
    confidence: float,
    path: str,
) -> ResumeFact:
    normalized_text = " ".join(text.split())
    fact_id = uuid.uuid5(_FACT_NAMESPACE, f"{source}:{category}:{path}:{normalized_text}")
    return ResumeFact(
        fact_id=fact_id,
        category=category,
        text=normalized_text,
        source=source,
        confidence=confidence,
    )
