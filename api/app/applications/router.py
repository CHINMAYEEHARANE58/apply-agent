import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.applications.models import Application
from app.applications.schemas import ApplicationCreate, ApplicationRead, ApplicationUpdate
from app.auth.dependencies import CurrentUser, SessionDep
from app.config.schemas import Page
from app.jobs.models import Job
from app.resumes.models import Resume
from app.security.errors import not_found

router = APIRouter(prefix="/applications", tags=["applications"])


def owned_application_or_404(application_id: uuid.UUID, user_id: uuid.UUID, session: SessionDep) -> Application:
    application = session.scalar(select(Application).where(Application.id == application_id, Application.user_id == user_id))
    if application is None:
        raise not_found("Application")
    return application


def validate_references(job_id: uuid.UUID, resume_id: uuid.UUID | None, user_id: uuid.UUID, session: SessionDep) -> None:
    if session.get(Job, job_id) is None:
        raise not_found("Job")
    if resume_id is not None:
        resume = session.scalar(select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id))
        if resume is None:
            raise not_found("Resume")


@router.get("", response_model=Page[ApplicationRead])
def list_applications(current_user: CurrentUser, session: SessionDep, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)) -> Page[ApplicationRead]:
    statement = select(Application).where(Application.user_id == current_user.id).order_by(Application.submitted_at.desc())
    total = session.scalar(select(func.count()).select_from(Application).where(Application.user_id == current_user.id)) or 0
    items = list(session.scalars(statement.limit(limit).offset(offset)))
    return Page(
        items=[ApplicationRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=ApplicationRead, status_code=status.HTTP_201_CREATED)
def create_application(payload: ApplicationCreate, current_user: CurrentUser, session: SessionDep) -> Application:
    validate_references(payload.job_id, payload.resume_id, current_user.id, session)
    application = Application(user_id=current_user.id, **payload.model_dump())
    session.add(application)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="An application already exists for this job.") from exc
    session.refresh(application)
    return application


@router.get("/{application_id}", response_model=ApplicationRead)
def get_application(application_id: uuid.UUID, current_user: CurrentUser, session: SessionDep) -> Application:
    return owned_application_or_404(application_id, current_user.id, session)


@router.patch("/{application_id}", response_model=ApplicationRead)
def update_application(application_id: uuid.UUID, payload: ApplicationUpdate, current_user: CurrentUser, session: SessionDep) -> Application:
    application = owned_application_or_404(application_id, current_user.id, session)
    updates = payload.model_dump(exclude_unset=True)
    if "resume_id" in updates:
        validate_references(application.job_id, updates["resume_id"], current_user.id, session)
    for field, value in updates.items():
        setattr(application, field, value)
    session.commit()
    session.refresh(application)
    return application


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(application_id: uuid.UUID, current_user: CurrentUser, session: SessionDep) -> None:
    session.delete(owned_application_or_404(application_id, current_user.id, session))
    session.commit()
