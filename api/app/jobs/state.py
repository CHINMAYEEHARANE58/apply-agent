import uuid

from fastapi import APIRouter, Query
from sqlalchemy import and_, func, select

from app.auth.dependencies import CurrentUser, SessionDep
from app.config.schemas import APIModel, Page
from app.jobs.models import Job, JobMatch, UserJob
from app.jobs.schemas_v2 import JobRead
from app.security.errors import not_found
from app.users.models import User

router = APIRouter(prefix="/jobs", tags=["job state"])


class JobStateUpdate(APIModel):
    saved: bool | None = None
    ignored: bool | None = None


class JobStateRead(APIModel):
    job_id: uuid.UUID
    saved: bool
    ignored: bool


class CandidateJobRead(JobRead):
    saved: bool = False
    ignored: bool = False
    match_score: int | None = None
    match_explanation: str | None = None
    matched_skills: list[str] = []
    missing_skills: list[str] = []


@router.get("/mine", response_model=Page[CandidateJobRead])
def my_jobs(current_user: CurrentUser, session: SessionDep, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), include_ignored: bool = False) -> Page[CandidateJobRead]:
    where = [UserJob.user_id == current_user.id]
    if not include_ignored:
        where.append(UserJob.ignored.is_(False))
    rows = session.execute(select(Job, UserJob, JobMatch).join(UserJob, UserJob.job_id == Job.id).outerjoin(JobMatch, and_(JobMatch.job_id == Job.id, JobMatch.user_id == UserJob.user_id)).where(*where).order_by(UserJob.created_at.desc(), Job.id).limit(limit).offset(offset)).all()
    total = session.scalar(select(func.count()).select_from(UserJob).where(*where)) or 0
    return Page(items=[CandidateJobRead(**JobRead.model_validate(job).model_dump(), saved=state.saved, ignored=state.ignored, match_score=state.match_score, match_explanation=state.match_explanation, matched_skills=match.matched_skills if match else [], missing_skills=match.missing_skills if match else []) for job, state, match in rows], total=total, limit=limit, offset=offset)


@router.get("/{job_id}/state", response_model=JobStateRead)
def get_state(job_id: uuid.UUID, current_user: CurrentUser, session: SessionDep) -> JobStateRead:
    if session.get(Job, job_id) is None:
        raise not_found("Job")
    state = session.scalar(select(UserJob).where(UserJob.user_id == current_user.id, UserJob.job_id == job_id))
    return JobStateRead(job_id=job_id, saved=state.saved if state else False, ignored=state.ignored if state else False)


@router.patch("/{job_id}/state", response_model=JobStateRead)
def set_state(job_id: uuid.UUID, payload: JobStateUpdate, current_user: CurrentUser, session: SessionDep) -> JobStateRead:
    session.scalar(select(User.id).where(User.id == current_user.id).with_for_update())
    if session.get(Job, job_id) is None:
        raise not_found("Job")
    state = session.scalar(select(UserJob).where(UserJob.user_id == current_user.id, UserJob.job_id == job_id))
    if state is None:
        state = UserJob(user_id=current_user.id, job_id=job_id, saved=False, ignored=False)
        session.add(state)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is None:
            from fastapi import HTTPException
            raise HTTPException(422, "Saved and ignored states must be boolean.")
        setattr(state, field, value)
    session.commit()
    return JobStateRead(job_id=job_id, saved=state.saved, ignored=state.ignored)
