"""Transactional per-candidate discovery/preparation. No submission client."""
import base64
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.ai.application_writing import generate_application_drafts
from app.ai.tailoring import prepare_tailored_resume
from app.applications.models import Application
from app.applications.policy import ApplicationPolicyService, SubmissionContext
from app.audit.models import AuditEvent
from app.job_sources.adapters import JobSourceAdapter
from app.job_sources.catalog import StoredCatalogAdapter, canonical_job
from app.jobs.discovery import are_reasonable_duplicates, job_fingerprint, normalized_text
from app.jobs.discovery_schemas import JobSearchQuery, NormalizedJob
from app.jobs.models import Job, JobMatch, UserJob
from app.matching.engine import CandidateMatchingProfile, match_internship
from app.preferences.models import InternshipPreference
from app.profiles.models import CandidateProfile
from app.resumes.facts import ResumeFactStore
from app.resumes.models import Resume
from app.resumes.router import fact_store_for_source
from app.scheduler.run_models import DailySearchRun
from app.security.encryption import encrypt_json
from app.settings.service import effective_settings
from app.users.models import User


def configured_adapters(session: Session) -> Sequence[JobSourceAdapter]:
    # Only server code can register implementations. A job/LLM cannot supply
    # an adapter, URL fetcher, authorization flag, or an executable tool.
    return [StoredCatalogAdapter(session)]


def audit(session: Session, user_id: uuid.UUID, event: str, entity_id: uuid.UUID, **metadata: Any) -> None:
    session.add(AuditEvent(user_id=user_id, event_type=event, entity_type="daily_search", entity_id=entity_id, event_metadata=metadata))


def persist_job(session: Session, job: NormalizedJob) -> Job:
    existing = session.scalar(select(Job).where(Job.fingerprint == job_fingerprint(job)))
    if existing is None:
        # Bound similarity candidates by indexed company; descriptions remain data.
        word = normalized_text(job.company).split()[0]
        candidates = session.scalars(select(Job).where(Job.company.ilike(f"%{word}%")).limit(200))
        existing = next((row for row in candidates if are_reasonable_duplicates(canonical_job(row), job)), None)
    if existing:
        existing.source_urls = list(dict.fromkeys([*existing.source_urls, existing.job_url, str(job.url)]))
        return existing
    row = Job(source=job.source, external_job_id=job.source_job_id, job_url=str(job.url), company=job.company, title=job.title, description=job.description, location=job.location, workplace_type=job.workplace_type, duration=f"{job.internship_duration.value} {job.internship_duration.unit}" if job.internship_duration else None, stipend=job.stipend_min, currency=job.currency, skills=job.required_skills, posted_at=job.posted_at, fingerprint=job_fingerprint(job), normalized_payload=job.model_dump(mode="json"), source_urls=[str(job.url)])
    try:
        with session.begin_nested():
            session.add(row)
            session.flush()
    except IntegrityError:
        winner = session.scalar(select(Job).where(Job.fingerprint == job_fingerprint(job)))
        if winner is None:
            raise
        return winner
    return row


def _run_daily_search(session: Session, user_id: uuid.UUID, *, now: datetime | None = None, adapters: Sequence[JobSourceAdapter] | None = None) -> dict[str, Any]:
    # This shared row lock serializes browser requests AND workers across all
    # processes. The unique daily record makes retries/restarts durable.
    user = session.scalar(select(User).where(User.id == user_id).with_for_update())
    counts = dict(jobs_discovered=0, jobs_evaluated=0, strong_matches=0, applications_prepared=0, applications_submitted=0)
    if user is None or not user.is_active:
        return {"status": "user_not_found", **counts}
    settings = effective_settings(session, user_id)
    if not settings.search_enabled:
        return {"status": "disabled", **counts}
    current = now or datetime.now(UTC)
    zone = ZoneInfo(settings.timezone)
    day = current.astimezone(zone).date()
    run = session.scalar(select(DailySearchRun).where(DailySearchRun.user_id == user_id, DailySearchRun.local_date == day))
    if run and run.status == "completed":
        return {"status": "already_completed", **counts, "previous_summary": run.summary}
    if run and int(run.summary.get("failures", 0)) >= 4:
        return {"status": "retry_limit_reached", **counts}
    if run is None:
        run = DailySearchRun(user_id=user_id, local_date=day, timezone=settings.timezone, status="running", summary={})
        session.add(run)
        session.flush()
    audit(session, user_id, "daily_search_started", run.id)
    preference = session.scalar(select(InternshipPreference).where(InternshipPreference.user_id == user_id))
    if preference is None:
        run.status, run.summary = "needs_preferences", {"status": "needs_preferences", **counts}
        session.commit()
        return run.summary
    master = session.scalar(select(Resume).where(Resume.user_id == user_id, Resume.type == "master", Resume.parser_status == "completed", Resume.source_of_truth_locked_at.is_not(None)).order_by(Resume.version.desc()).limit(1))
    profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user_id))
    facts = fact_store_for_source(master, user_id, session) if master else ResumeFactStore([])
    fields = {field: getattr(preference, field) for field in CandidateMatchingProfile.model_fields if hasattr(preference, field)}
    fields.update(work_authorization=profile.work_authorization if profile else None, minimum_match_score=settings.minimum_match_score)
    candidate = CandidateMatchingProfile(**fields)
    start = datetime.combine(day, time.min, zone).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time.min, zone).astimezone(UTC)
    prepared_today = session.scalar(select(func.count()).select_from(Application).where(Application.user_id == user_id, Application.created_at >= start, Application.created_at < end, Application.resume_id.is_not(None))) or 0
    submitted_today = session.scalar(select(func.count()).select_from(Application).where(Application.user_id == user_id, Application.submitted_at >= start, Application.submitted_at < end)) or 0
    seen: set[uuid.UUID] = set()
    for adapter in adapters if adapters is not None else configured_adapters(session):
        capability = adapter.get_capabilities()
        if capability.source_name not in settings.enabled_sources or not capability.discovery_supported:
            continue
        if capability.discovery_method not in {"manual", "email"} and not capability.authorization_verified:
            audit(session, user_id, "source_permission_blocked", run.id)
            continue
        remaining = settings.maximum_jobs_evaluated_daily - counts["jobs_evaluated"]
        if remaining <= 0:
            break
        try:
            payloads = adapter.search_jobs(JobSearchQuery(roles=preference.roles, limit=min(remaining, 100)))
        except PermissionError:
            audit(session, user_id, "source_authorization_failed", run.id)
            continue  # Never retry authorization errors.
        for raw in payloads[:remaining]:
            normalized = adapter.normalize_job(raw)
            job = persist_job(session, normalized)
            if job.id in seen:
                continue
            seen.add(job.id)
            state = session.scalar(select(UserJob).where(UserJob.user_id == user_id, UserJob.job_id == job.id))
            if state is None:
                state = UserJob(user_id=user_id, job_id=job.id, saved=False, ignored=False)
                session.add(state)
                counts["jobs_discovered"] += 1
                audit(session, user_id, "job_discovered", job.id)
            if state.ignored:
                continue
            match = match_internship(normalized, candidate, facts, now=current)
            counts["jobs_evaluated"] += 1
            state.match_score, state.match_explanation = match.score, match.explanation
            stored = session.scalar(select(JobMatch).where(JobMatch.user_id == user_id, JobMatch.job_id == job.id))
            values = dict(score=match.score, hard_filter_passed=match.hard_filter.passed, matched_skills=match.matched_skills, missing_skills=match.missing_required_skills, explanation=match.explanation)
            if stored is None:
                session.add(JobMatch(user_id=user_id, job_id=job.id, **values))
            else:
                for field, value in values.items():
                    setattr(stored, field, value)
            audit(session, user_id, "job_matched" if match.hard_filter.passed else "job_rejected", job.id, score=match.score)
            if not match.recommended:
                continue
            counts["strong_matches"] += 1
            if master is None or prepared_today >= settings.maximum_applications_prepared_daily:
                continue
            if session.scalar(select(Application.id).where(Application.user_id == user_id, Application.job_id == job.id)):
                continue
            artifact = prepare_tailored_resume(source_resume_id=master.id, job=normalized, match=match, fact_store=facts)
            if not artifact.verification or not artifact.verification.approved or artifact.status != "READY":
                audit(session, user_id, "resume_requires_review", job.id)
                continue
            resume_id = uuid.uuid4()
            payload = {"generated_bullets": [bullet.model_dump(mode="json") for bullet in artifact.generated_bullets], "resume_html": artifact.resume_html, "resume_pdf_base64": base64.b64encode(artifact.resume_pdf or b"").decode(), "change_summary": artifact.change_summary.model_dump(), "keyword_coverage": artifact.keyword_coverage.model_dump()}
            tailored = Resume(id=resume_id, user_id=user_id, type="tailored", file_reference=f"tailored/{resume_id}", source_resume_id=master.id, version=1, parser_status="completed", approval_status="draft", generated_bullets_encrypted=encrypt_json(payload, purpose=f"resume:{resume_id}:generated-bullets"))
            session.add(tailored)
            drafts = generate_application_drafts(candidate_name=profile.full_name if profile else "", job=normalized, match=match, fact_store=facts)
            if drafts.status != "READY_FOR_REVIEW":
                continue
            decision = ApplicationPolicyService().evaluate_submission(SubmissionContext(job_exists=True, hard_filters_passed=match.hard_filter.passed, match_score=match.score, minimum_match_score=settings.minimum_match_score, resume_verified=False, already_applied=False, daily_limit_exceeded=submitted_today >= settings.max_daily_applications, required_questions_answered=False, uncertain_sensitive_answers=True, captcha_present=False, platform_restriction_blocks_automation=not capability.authorization_verified, idempotency_key=f"daily:{user_id}:{job.id}"), capability)
            # Factually verified is not user-approved. Unknown questions are
            # never guessed; all packages await review, regardless of auto mode.
            application = Application(id=uuid.uuid4(), user_id=user_id, job_id=job.id, resume_id=resume_id, status="awaiting_approval", cover_letter=drafts.cover_letter, application_message=drafts.recruiter_message)
            session.add(application)
            prepared_today += 1
            counts["applications_prepared"] += 1
            audit(session, user_id, "resume_generated", resume_id)
            audit(session, user_id, "application_prepared", application.id)
            audit(session, user_id, "submission_policy_evaluated", application.id, allowed=decision.allowed, reason=decision.reason)
            session.flush()
    final_status = "completed" if master else "needs_resume"
    summary = {"status": final_status, **counts}
    run.status, run.summary = final_status, summary
    audit(session, user_id, "daily_summary_recorded", run.id, **counts)
    session.commit()
    return summary


class SearchTemporaryFailure(ConnectionError):
    pass


def run_daily_search(session: Session, user_id: uuid.UUID, *, now: datetime | None = None, adapters: Sequence[JobSourceAdapter] | None = None) -> dict[str, Any]:
    try:
        return _run_daily_search(session, user_id, now=now, adapters=adapters)
    except Exception as error:
        session.rollback()
        # Rollback all partial drafts. Persist only a safe code/counter, never
        # source text, resume content, credentials or exception messages.
        try:
            user = session.scalar(select(User).where(User.id == user_id).with_for_update())
            if user:
                settings = effective_settings(session, user_id)
                day = (now or datetime.now(UTC)).astimezone(ZoneInfo(settings.timezone)).date()
                run = session.scalar(select(DailySearchRun).where(DailySearchRun.user_id == user_id, DailySearchRun.local_date == day))
                if run is None:
                    run = DailySearchRun(user_id=user_id, local_date=day, timezone=settings.timezone, status="failed", summary={})
                    session.add(run)
                    session.flush()
                failures = int(run.summary.get("failures", 0)) + 1
                run.status, run.summary = "failed", {"status": "failed", "failures": failures}
                audit(session, user_id, "daily_search_failed", run.id, failures=failures)
                session.commit()
        except (SQLAlchemyError, ValueError):
            session.rollback()
        if isinstance(error, HTTPException):
            raise error from None
        if isinstance(error, (ConnectionError, OperationalError)):
            raise SearchTemporaryFailure("A temporary search failure occurred; no application was submitted.") from None
        raise RuntimeError("Search failed safely; no application was submitted.") from None
