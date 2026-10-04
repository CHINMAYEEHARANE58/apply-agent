import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.auth.dependencies import CurrentUser, SessionDep
from app.config.schemas import Page
from app.jobs.models import Job, JobMatch
from app.jobs.schemas_v2 import (
    JobCreate,
    JobMatchCreate,
    JobMatchRead,
    JobMatchUpdate,
    JobRead,
    JobUpdate,
)
from app.security.errors import not_found

router = APIRouter(tags=["jobs"])


def job_or_404(job_id: uuid.UUID, session: SessionDep) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise not_found("Job")
    return job


def owned_match_or_404(match_id: uuid.UUID, user_id: uuid.UUID, session: SessionDep) -> JobMatch:
    match = session.scalar(select(JobMatch).where(JobMatch.id == match_id, JobMatch.user_id == user_id))
    if match is None:
        raise not_found("Job match")
    return match


@router.get("/jobs", response_model=Page[JobRead])
def list_jobs(session: SessionDep, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), query: str | None = Query(default=None, min_length=1, max_length=200)) -> Page[JobRead]:
    where = []
    if query:
        term = f"%{query}%"
        where.append(or_(Job.title.ilike(term), Job.company.ilike(term), Job.location.ilike(term)))
    statement = select(Job).where(*where).order_by(Job.discovered_at.desc())
    total = session.scalar(select(func.count()).select_from(Job).where(*where)) or 0
    items = list(session.scalars(statement.limit(limit).offset(offset)))
    return Page(
        items=[JobRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/jobs", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def create_job(payload: JobCreate, _: CurrentUser, session: SessionDep) -> Job:
    values = payload.model_dump()
    values["job_url"] = str(payload.job_url)
    job = Job(**values)
    session.add(job)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="A job with this source ID or fingerprint already exists.") from exc
    session.refresh(job)
    return job


@router.get("/jobs/{job_id}", response_model=JobRead)
def get_job(job_id: uuid.UUID, session: SessionDep) -> Job:
    return job_or_404(job_id, session)


@router.patch("/jobs/{job_id}", response_model=JobRead)
def update_job(job_id: uuid.UUID, payload: JobUpdate, _: CurrentUser, session: SessionDep) -> Job:
    job = job_or_404(job_id, session)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(job, field, value)
    session.commit()
    session.refresh(job)
    return job


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: uuid.UUID, _: CurrentUser, session: SessionDep) -> None:
    session.delete(job_or_404(job_id, session))
    session.commit()


@router.get("/matches", response_model=Page[JobMatchRead])
def list_matches(current_user: CurrentUser, session: SessionDep, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)) -> Page[JobMatchRead]:
    statement = select(JobMatch).where(JobMatch.user_id == current_user.id).order_by(JobMatch.score.desc())
    total = session.scalar(select(func.count()).select_from(JobMatch).where(JobMatch.user_id == current_user.id)) or 0
    items = list(session.scalars(statement.limit(limit).offset(offset)))
    return Page(
        items=[JobMatchRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/matches", response_model=JobMatchRead, status_code=status.HTTP_201_CREATED)
def create_match(payload: JobMatchCreate, current_user: CurrentUser, session: SessionDep) -> JobMatch:
    job_or_404(payload.job_id, session)
    match = JobMatch(user_id=current_user.id, **payload.model_dump())
    session.add(match)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="A match already exists for this job.") from exc
    session.refresh(match)
    return match


@router.get("/matches/{match_id}", response_model=JobMatchRead)
def get_match(match_id: uuid.UUID, current_user: CurrentUser, session: SessionDep) -> JobMatch:
    return owned_match_or_404(match_id, current_user.id, session)


@router.patch("/matches/{match_id}", response_model=JobMatchRead)
def update_match(match_id: uuid.UUID, payload: JobMatchUpdate, current_user: CurrentUser, session: SessionDep) -> JobMatch:
    match = owned_match_or_404(match_id, current_user.id, session)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(match, field, value)
    session.commit()
    session.refresh(match)
    return match


@router.delete("/matches/{match_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_match(match_id: uuid.UUID, current_user: CurrentUser, session: SessionDep) -> None:
    session.delete(owned_match_or_404(match_id, current_user.id, session))
    session.commit()
