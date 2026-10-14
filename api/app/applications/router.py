import uuid

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.applications.models import Application
from app.applications.schemas import ApplicationCreate, ApplicationRead, ApplicationUpdate
from app.audit.models import AuditEvent
from app.auth.dependencies import CurrentUser, SessionDep
from app.config.schemas import Page
from app.job_sources.catalog import canonical_job
from app.jobs.models import Job
from app.matching.engine import CandidateMatchingProfile, match_internship
from app.preferences.models import InternshipPreference
from app.profiles.models import CandidateProfile
from app.resumes.models import Resume
from app.resumes.router import (
    approve_tailored_resume_if_unchanged,
    fact_store_for_source,
    master_resume_or_404,
    owned_resume_for_update_or_404,
    verification_for_tailored_resume,
)
from app.resumes.schemas import ResumeVerificationRequest
from app.security.errors import not_found
from app.settings.service import effective_settings
from app.users.models import User

router = APIRouter(prefix="/applications", tags=["applications"])


def owned_application_or_404(
    application_id: uuid.UUID, user_id: uuid.UUID, session: SessionDep
) -> Application:
    application = session.scalar(
        select(Application).where(Application.id == application_id, Application.user_id == user_id)
    )
    if application is None:
        raise not_found("Application")
    return application


def validate_references(
    job_id: uuid.UUID, resume_id: uuid.UUID | None, user_id: uuid.UUID, session: SessionDep
) -> None:
    if session.get(Job, job_id) is None:
        raise not_found("Job")
    if resume_id is not None:
        resume = session.scalar(
            select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id)
        )
        if resume is None:
            raise not_found("Resume")


@router.get("", response_model=Page[ApplicationRead])
def list_applications(
    current_user: CurrentUser,
    session: SessionDep,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Page[ApplicationRead]:
    statement = (
        select(Application)
        .where(Application.user_id == current_user.id)
        .order_by(Application.created_at.desc(), Application.id)
    )
    total = (
        session.scalar(
            select(func.count())
            .select_from(Application)
            .where(Application.user_id == current_user.id)
        )
        or 0
    )
    items = list(session.scalars(statement.limit(limit).offset(offset)))
    return Page(
        items=[ApplicationRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=ApplicationRead, status_code=status.HTTP_201_CREATED)
def create_application(
    payload: ApplicationCreate, current_user: CurrentUser, session: SessionDep
) -> Application:
    validate_references(payload.job_id, payload.resume_id, current_user.id, session)
    application = Application(user_id=current_user.id, **payload.model_dump())
    session.add(application)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409, detail="An application already exists for this job."
        ) from exc
    session.refresh(application)
    return application


@router.get("/{application_id}", response_model=ApplicationRead)
def get_application(
    application_id: uuid.UUID, current_user: CurrentUser, session: SessionDep
) -> Application:
    return owned_application_or_404(application_id, current_user.id, session)


@router.patch("/{application_id}", response_model=ApplicationRead)
def update_application(
    application_id: uuid.UUID,
    payload: ApplicationUpdate,
    current_user: CurrentUser,
    session: SessionDep,
) -> Application:
    application = owned_application_or_404(application_id, current_user.id, session)
    updates = payload.model_dump(exclude_unset=True)
    merged = {field: getattr(application, field) for field in ApplicationCreate.model_fields}
    merged.update(updates)
    try:
        ApplicationCreate.model_validate(merged)
    except ValidationError as error:
        raise HTTPException(422, "Application status and submission metadata are inconsistent.") from error
    if "resume_id" in updates:
        validate_references(application.job_id, updates["resume_id"], current_user.id, session)
    for field, value in updates.items():
        setattr(application, field, value)
    session.commit()
    session.refresh(application)
    return application


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(
    application_id: uuid.UUID, current_user: CurrentUser, session: SessionDep
) -> None:
    session.delete(owned_application_or_404(application_id, current_user.id, session))
    session.commit()


@router.post("/{application_id}/approve", response_model=ApplicationRead)
def approve_package(application_id: uuid.UUID, current_user: CurrentUser, session: SessionDep) -> Application:
    session.scalar(select(User.id).where(User.id == current_user.id).with_for_update())
    application = session.scalar(select(Application).where(Application.id == application_id, Application.user_id == current_user.id).with_for_update())
    if application is None:
        raise not_found("Application")
    if application.status != "awaiting_approval" or application.resume_id is None:
        raise HTTPException(409, "This application is not awaiting package approval.")
    resume = owned_resume_for_update_or_404(application.resume_id, current_user.id, session)
    verification = verification_for_tailored_resume(resume, ResumeVerificationRequest(), current_user.id, session, require_fact_references=True)
    if not verification.approved or resume.source_resume_id is None:
        raise HTTPException(422, "The application resume is not factually verifiable.")
    preference = session.scalar(select(InternshipPreference).where(InternshipPreference.user_id == current_user.id))
    profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == current_user.id))
    job = session.get(Job, application.job_id)
    if preference is None or job is None:
        raise HTTPException(409, "Preferences and a current job are required for approval.")
    settings = effective_settings(session, current_user.id)
    fields = {field: getattr(preference, field) for field in CandidateMatchingProfile.model_fields if hasattr(preference, field)}
    fields.update(preferred_locations=list(dict.fromkeys([*preference.preferred_locations, *preference.preferred_cities, *preference.preferred_countries])), work_authorization=profile.work_authorization if profile else None, minimum_match_score=settings.minimum_match_score)
    source = master_resume_or_404(resume.source_resume_id, current_user.id, session)
    match = match_internship(canonical_job(job), CandidateMatchingProfile(**fields), fact_store_for_source(source, current_user.id, session))
    if not match.recommended:
        raise HTTPException(409, "The job no longer meets your current preferences or match threshold.")
    approve_tailored_resume_if_unchanged(resume, current_user.id, session, commit=False)
    application.status = "prepared"
    session.add(AuditEvent(user_id=current_user.id, event_type="user_approved", entity_type="application", entity_id=application.id, event_metadata={"external_submission": False}))
    session.commit()
    session.refresh(application)
    return application
