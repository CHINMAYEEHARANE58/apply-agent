"""Deterministic verification for generated, evidence-bound resume content.

An LLM may propose wording, but it does not decide whether that wording is
truthful.  This module resolves any supplied fact references and conservatively
checks material terms in the proposed text against trusted fact text before a
tailored resume is eligible for approval.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from collections.abc import Sequence
from typing import Literal

from pydantic import Field

from app.config.schemas import APIModel
from app.resumes.facts import GeneratedResumeBullet, ResumeFact, ResumeFactStore

VerificationIssueCode = Literal[
    "empty_content",
    "missing_fact_references",
    "unknown_fact_reference",
    "low_confidence_fact",
    "insufficient_evidence_overlap",
    "unsupported_terms",
]

# A metric is one material token, including its comparator, approximation,
# rank marker, sign, currency, unit, and a trailing ``+`` qualifier.  Splitting
# ``>10%`` into an ignored ``>`` plus ``10%`` would let a generated bullet turn
# a bound into an unsupported exact claim.
_TOKEN_RE = re.compile(
    r"(?:(?:[<>]=?|[≤≥~#≈=])\s*)?(?:[$€£₹]\s*)?[+\-−]?\d+(?:[.,]\d+)?(?:\+|%|[A-Za-z]+)?"
    r"|[A-Za-z][A-Za-z0-9+.#/\\-]*"
)
_NUMBER_RE = re.compile(r"^(?:[<>]=?|[≤≥~#≈=])?(?:[$€£₹])?[+\-]?\d")

# Only grammatical articles may be removed during a cosmetic rewrite.  Every
# ownership, relationship, negation, qualifier, and quantity-bearing token
# remains in the phrase comparison: dropping one can change a client,
# employer, responsibility, ownership, or qualification.
_IGNORABLE_TOKENS = frozenset({"a", "an", "the"})

# Small, intentionally conservative equivalence groups permit ordinary
# rewriting without letting a generator introduce new qualifications.
_PARAPHRASE_GROUPS = (
    frozenset({"built", "developed", "created", "implemented", "engineered", "authored"}),
    frozenset({"improved", "optimized", "enhanced"}),
    frozenset({"analyzed", "analysed", "evaluated", "researched", "investigated"}),
    frozenset({"designed", "crafted"}),
    frozenset({"collaborated", "partnered"}),
    frozenset({"application", "applications", "app", "apps"}),
)

_TOKEN_ALIASES = {
    "c++": "cplusplus",
    "c#": "csharp",
    ".net": "dotnet",
    "js": "javascript",
    "next.js": "nextjs",
    "node.js": "nodejs",
    "postgres": "postgresql",
    "react.js": "react",
    "ts": "typescript",
    "vue.js": "vue",
}


class ResumeVerificationIssue(APIModel):
    code: VerificationIssueCode
    message: str
    fact_id: uuid.UUID | None = None
    terms: list[str] = Field(default_factory=list)


class BulletVerificationResult(APIModel):
    approved: bool
    supporting_fact_ids: list[uuid.UUID] = Field(default_factory=list)
    unsupported_terms: list[str] = Field(default_factory=list)
    issues: list[ResumeVerificationIssue] = Field(default_factory=list)


class ResumeVerificationResult(APIModel):
    """Verification outcome that must gate tailored-resume approval."""

    approved: bool
    bullet_results: list[BulletVerificationResult] = Field(default_factory=list)


class ResumeVerificationError(ValueError):
    """Raised when an attempted approval contains unsupported generated text."""

    def __init__(self, result: ResumeVerificationResult) -> None:
        super().__init__("Generated resume content is not supported by trusted candidate facts.")
        self.result = result


def verify_generated_bullet(
    bullet: GeneratedResumeBullet,
    fact_store: ResumeFactStore,
    *,
    minimum_fact_confidence: float = 0.8,
    require_fact_references: bool = False,
) -> BulletVerificationResult:
    """Verify one generated bullet against resume/profile facts.

    If the bullet includes ``supporting_fact_ids``, only those facts are used as
    evidence.  Without citations the whole eligible store is considered, which
    preserves compatibility while still requiring the wording to be grounded.
    The result is deliberately fail-closed: callers must check ``approved``
    before storing an approved tailored resume.
    """

    _validate_minimum_confidence(minimum_fact_confidence)
    issues: list[ResumeVerificationIssue] = []
    supporting_ids = bullet.supporting_fact_ids

    if require_fact_references and not supporting_ids:
        issues.append(
            ResumeVerificationIssue(
                code="missing_fact_references",
                message="This generated bullet must cite at least one supporting fact.",
            )
        )

    missing_ids = fact_store.missing_ids(supporting_ids)
    for fact_id in missing_ids:
        issues.append(
            ResumeVerificationIssue(
                code="unknown_fact_reference",
                message="The generated bullet references a fact that is not in the fact store.",
                fact_id=fact_id,
            )
        )

    selected_facts = _selected_facts(supporting_ids, fact_store, minimum_fact_confidence)
    if supporting_ids:
        for fact in fact_store.resolve(supporting_ids):
            if fact.confidence < minimum_fact_confidence:
                issues.append(
                    ResumeVerificationIssue(
                        code="low_confidence_fact",
                        message="A cited fact is below the confidence required for automatic approval.",
                        fact_id=fact.fact_id,
                    )
                )
    else:
        selected_facts = tuple(
            fact for fact in fact_store.facts if fact.confidence >= minimum_fact_confidence
        )

    content_tokens = _material_tokens(bullet.text)
    if not content_tokens:
        issues.append(
            ResumeVerificationIssue(
                code="empty_content",
                message="The generated bullet does not contain a verifiable claim.",
            )
        )

    matching_facts = tuple(
        fact
        for fact in selected_facts
        if _fact_supports_claim(bullet.text, content_tokens, fact)
    )
    overlap_count = max(
        (_claim_overlap_count(content_tokens, fact) for fact in selected_facts), default=0
    )
    unsupported_terms = [] if matching_facts else [raw_token for raw_token, _ in content_tokens]

    if content_tokens and overlap_count == 0:
        issues.append(
            ResumeVerificationIssue(
                code="insufficient_evidence_overlap",
                message="The generated bullet has no material overlap with a selected trusted fact.",
            )
        )

    if unsupported_terms:
        issues.append(
            ResumeVerificationIssue(
                code="unsupported_terms",
                message=(
                    "The generated bullet is not a source-faithful claim from any one selected "
                    "trusted fact. Claims cannot combine details from separate facts."
                ),
                terms=_deduplicate(unsupported_terms),
            )
        )

    return BulletVerificationResult(
        approved=not issues,
        supporting_fact_ids=[fact.fact_id for fact in matching_facts],
        unsupported_terms=_deduplicate(unsupported_terms),
        issues=issues,
    )


def verify_generated_resume(
    bullets: Sequence[GeneratedResumeBullet],
    fact_store: ResumeFactStore,
    *,
    minimum_fact_confidence: float = 0.8,
    require_fact_references: bool = False,
) -> ResumeVerificationResult:
    """Verify all generated bullets before a tailored resume is approved."""

    _validate_minimum_confidence(minimum_fact_confidence)
    if not bullets:
        return ResumeVerificationResult(
            approved=False,
            bullet_results=[
                BulletVerificationResult(
                    approved=False,
                    issues=[
                        ResumeVerificationIssue(
                            code="empty_content",
                            message="A tailored resume must contain at least one generated bullet to verify.",
                        )
                    ],
                )
            ],
        )

    results = [
        verify_generated_bullet(
            bullet,
            fact_store,
            minimum_fact_confidence=minimum_fact_confidence,
            require_fact_references=require_fact_references,
        )
        for bullet in bullets
    ]
    return ResumeVerificationResult(approved=all(result.approved for result in results), bullet_results=results)


def verify_tailored_resume(
    bullets: Sequence[GeneratedResumeBullet],
    fact_store: ResumeFactStore,
    *,
    minimum_fact_confidence: float = 0.8,
    require_fact_references: bool = False,
) -> ResumeVerificationResult:
    """Explicit alias for the approval workflow's tailored-resume check."""

    return verify_generated_resume(
        bullets,
        fact_store,
        minimum_fact_confidence=minimum_fact_confidence,
        require_fact_references=require_fact_references,
    )


def require_verified_resume(
    bullets: Sequence[GeneratedResumeBullet],
    fact_store: ResumeFactStore,
    *,
    minimum_fact_confidence: float = 0.8,
    require_fact_references: bool = False,
) -> ResumeVerificationResult:
    """Return verification output or raise, providing a fail-closed approval gate."""

    result = verify_generated_resume(
        bullets,
        fact_store,
        minimum_fact_confidence=minimum_fact_confidence,
        require_fact_references=require_fact_references,
    )
    if not result.approved:
        raise ResumeVerificationError(result)
    return result


def _selected_facts(
    supporting_ids: Sequence[uuid.UUID],
    fact_store: ResumeFactStore,
    minimum_fact_confidence: float,
) -> tuple[ResumeFact, ...]:
    return tuple(
        fact
        for fact in fact_store.resolve(supporting_ids)
        if fact.confidence >= minimum_fact_confidence
    )


def _validate_minimum_confidence(value: float) -> None:
    if not 0 <= value <= 1:
        raise ValueError("minimum_fact_confidence must be between 0 and 1.")


def _material_tokens(text: str) -> tuple[tuple[str, str], ...]:
    tokens: list[tuple[str, str]] = []
    normalized_text = unicodedata.normalize("NFKC", text)
    for raw_token in _TOKEN_RE.findall(normalized_text):
        canonical_token = _canonicalize_token(raw_token)
        if canonical_token and canonical_token not in _IGNORABLE_TOKENS:
            tokens.append((raw_token, canonical_token))
    return tuple(tokens)


def _fact_supports_claim(
    claim_text: str, claim_tokens: Sequence[tuple[str, str]], fact: ResumeFact
) -> bool:
    """Require one fact to support the complete claim in source order.

    Treating a collection of facts as a bag of words permits false joins such
    as taking an employer from one fact and a responsibility from another.
    A tailored bullet is therefore approved only when all of its material
    tokens match one complete fact in source order.  Accepting a substring
    would allow a generator to omit a qualifier or negation (for example,
    turning "No experience with Kubernetes" into an experience claim). This
    is intentionally stricter than ordinary prose summarization: uncertainty
    should result in review, never an invented relationship.
    """

    # Metrics, dates, ranges, ranks, ratios, and signs are too easy to alter
    # by dropping punctuation (for example ``10/10`` -> ``10 10`` or
    # ``2020–2023`` -> ``2020 2023``). Any digit in either side therefore
    # requires source-faithful normalized text instead of token paraphrasing.
    if _contains_digit(claim_text) or _contains_digit(fact.text):
        return _normalize_numeric_claim(claim_text) == _normalize_numeric_claim(fact.text)

    claim = [canonical_token for _, canonical_token in claim_tokens]
    evidence = [canonical_token for _, canonical_token in _material_tokens(fact.text)]
    if not claim or len(claim) != len(evidence):
        return False
    return all(
        _tokens_equivalent(claim_token, evidence_token)
        for claim_token, evidence_token in zip(claim, evidence, strict=True)
    )


def _contains_digit(value: str) -> bool:
    return any(character.isdigit() for character in value)


def _normalize_numeric_claim(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _claim_overlap_count(claim_tokens: Sequence[tuple[str, str]], fact: ResumeFact) -> int:
    evidence = {canonical_token for _, canonical_token in _material_tokens(fact.text)}
    return sum(_token_is_present(canonical_token, evidence) for _, canonical_token in claim_tokens)


def _canonicalize_token(token: str) -> str:
    # Normalise a typographic minus and optional formatting space in values
    # such as ``$ 10`` without dropping the sign or currency symbol. Both are
    # material evidence and must not be allowed to change a metric's meaning.
    canonical = token.casefold().replace("−", "-").replace(" ", "").strip("._/")
    return _TOKEN_ALIASES.get(canonical, canonical)


def _tokens_equivalent(left: str, right: str) -> bool:
    if left == right:
        return True
    if _NUMBER_RE.match(left) or _NUMBER_RE.match(right):
        return False
    return any(left in group and right in group for group in _PARAPHRASE_GROUPS)


def _token_is_present(token: str, evidence: set[str]) -> bool:
    return any(_tokens_equivalent(token, evidence_token) for evidence_token in evidence)


def _deduplicate(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(values))
