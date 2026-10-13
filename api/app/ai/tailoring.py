"""Evidence-bound, deterministic tailored-resume preparation.

This is deliberately a conservative foundation rather than an autonomous
writer. It produces a truthful ordering of source facts, verifies every
displayed claim, and renders only after verification has passed. A future
model may suggest a rewrite, but it must pass the same verification gate.
"""

from __future__ import annotations

import html
import re
import uuid
from typing import Literal

from pydantic import Field

from app.config.schemas import APIModel
from app.jobs.discovery_schemas import NormalizedJob
from app.matching.engine import MatchResult
from app.resumes.facts import GeneratedResumeBullet, ResumeFact, ResumeFactStore
from app.resumes.verification import ResumeVerificationResult, verify_tailored_resume

TailoredResumeStatus = Literal["READY", "REQUIRES_REVIEW", "SKIPPED_LOW_MATCH"]
_TERM_RE = re.compile(r"[a-z][a-z0-9+#.]{1,}")


class TailoredResumeDiff(APIModel):
    summary_changes: list[str] = Field(default_factory=list)
    skills_reordered: list[str] = Field(default_factory=list)
    projects_prioritized: list[str] = Field(default_factory=list)
    bullet_changes: list[str] = Field(default_factory=list)


class KeywordCoverageReport(APIModel):
    covered_keywords: list[str] = Field(default_factory=list)
    missing_required_keywords: list[str] = Field(default_factory=list)
    missing_optional_keywords: list[str] = Field(default_factory=list)


class TailoredResumeArtifact(APIModel):
    """A reviewable artifact; no artifact is approved without verification."""

    status: TailoredResumeStatus
    source_resume_id: uuid.UUID | None = None
    resume_html: str | None = None
    resume_pdf: bytes | None = None
    change_summary: TailoredResumeDiff
    keyword_coverage: KeywordCoverageReport
    generated_bullets: list[GeneratedResumeBullet] = Field(default_factory=list)
    verification: ResumeVerificationResult | None = None
    review_reason: str | None = None


def prepare_tailored_resume(
    *,
    source_resume_id: uuid.UUID | None,
    fact_store: ResumeFactStore,
    job: NormalizedJob,
    match: MatchResult,
) -> TailoredResumeArtifact:
    """Prepare an evidence-only resume view after a qualifying match.

    Job text contributes only keywords for ordering. It is never rendered as
    instructions and cannot alter the candidate fact store, approval state, or
    any application action.
    """

    coverage = KeywordCoverageReport(
        covered_keywords=match.matched_skills,
        missing_required_keywords=match.missing_required_skills,
        missing_optional_keywords=match.missing_optional_skills,
    )
    empty_diff = TailoredResumeDiff()
    if not match.recommended:
        return TailoredResumeArtifact(
            status="SKIPPED_LOW_MATCH",
            source_resume_id=source_resume_id,
            change_summary=empty_diff,
            keyword_coverage=coverage,
            review_reason="The job did not meet the configured automatic progression threshold.",
        )

    ordered_facts = _prioritized_facts(fact_store, job, match)
    bullets = [
        GeneratedResumeBullet(text=fact.text, supporting_fact_ids=[fact.fact_id])
        for fact in ordered_facts
    ]
    verification = verify_tailored_resume(bullets, fact_store, require_fact_references=True)
    change_summary = _change_summary(ordered_facts, match)
    if not verification.approved:
        return TailoredResumeArtifact(
            status="REQUIRES_REVIEW",
            source_resume_id=source_resume_id,
            change_summary=change_summary,
            keyword_coverage=coverage,
            generated_bullets=bullets,
            verification=verification,
            review_reason="One or more generated claims could not be verified against trusted facts.",
        )

    resume_html = _render_html(job, ordered_facts)
    return TailoredResumeArtifact(
        status="READY",
        source_resume_id=source_resume_id,
        resume_html=resume_html,
        resume_pdf=_render_pdf(job, ordered_facts),
        change_summary=change_summary,
        keyword_coverage=coverage,
        generated_bullets=bullets,
        verification=verification,
    )


def _prioritized_facts(
    fact_store: ResumeFactStore,
    job: NormalizedJob,
    match: MatchResult,
) -> list[ResumeFact]:
    job_terms = _terms(" ".join([job.title, *job.required_skills, *job.preferred_skills]))
    relevant_categories = {"summary", "skills", "experience", "internships", "projects", "education", "certifications"}
    facts = [fact for fact in fact_store.facts if fact.category in relevant_categories and fact.confidence >= 0.8]

    def sort_key(fact: ResumeFact) -> tuple[int, int, str]:
        overlap = len(_terms(fact.text) & job_terms)
        category_priority = {"summary": 0, "skills": 1, "projects": 2, "experience": 3, "internships": 4}.get(
            fact.category, 5
        )
        return (-overlap, category_priority, fact.text.casefold())

    # Always retain facts exactly as they were supplied; only their display
    # order changes. Limiting protects generated previews from excessive size.
    return sorted(facts, key=sort_key)[:40]


def _change_summary(facts: list[ResumeFact], match: MatchResult) -> TailoredResumeDiff:
    skills = [fact.text for fact in facts if fact.category == "skills"]
    projects = [fact.text for fact in facts if fact.category in {"projects", "experience", "internships"}]
    return TailoredResumeDiff(
        summary_changes=["Retained factual summary content and prioritized job-relevant source facts."],
        skills_reordered=skills[:20],
        projects_prioritized=projects[:20],
        bullet_changes=[f"Retained source-backed statement for {fact.category}." for fact in facts[:20]],
    )


def _render_html(job: NormalizedJob, facts: list[ResumeFact]) -> str:
    items = "".join(
        f'<li data-fact-id="{fact.fact_id}">{html.escape(fact.text)}</li>' for fact in facts
    )
    # Title/company are listing metadata, not claims about the candidate. The
    # untrusted job description is intentionally excluded from rendered output.
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\"><title>Tailored resume</title></head>"
        f"<body><h1>Tailored resume for {html.escape(job.title)}</h1>"
        f"<p>Prepared for {html.escape(job.company)}</p><ul>{items}</ul></body></html>"
    )


def _render_pdf(job: NormalizedJob, facts: list[ResumeFact]) -> bytes:
    """Create a small self-contained PDF without executing or loading uploads."""

    lines = [f"Tailored resume for {job.title}", f"Prepared for {job.company}"]
    lines.extend(f"- {fact.text}" for fact in facts)
    content_lines = ["BT", "/F1 10 Tf", "72 760 Td"]
    for index, line in enumerate(lines[:45]):
        if index:
            content_lines.append("0 -14 Td")
        content_lines.append(f"({_pdf_escape(line[:180])}) Tj")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, payload in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode())
        output.extend(payload)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        output.extend(f"{offset:010} 00000 n \n".encode())
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode()
    )
    return bytes(output)


def _pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _terms(value: str) -> set[str]:
    return set(_TERM_RE.findall(value.casefold()))
