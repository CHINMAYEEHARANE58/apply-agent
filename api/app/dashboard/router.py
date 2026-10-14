from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select
from sqlalchemy.sql.elements import ColumnElement

from app.applications.models import Application
from app.auth.dependencies import CurrentUser, SessionDep
from app.config.schemas import APIModel
from app.jobs.models import JobMatch, UserJob
from app.settings.service import effective_settings

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class DashboardRead(APIModel):
    jobs_discovered_today: int
    strong_matches: int
    applications_prepared: int
    applications_submitted: int
    interviews: int
    responses: int
    offers: int


@router.get("", response_model=DashboardRead)
def dashboard(current_user: CurrentUser, session: SessionDep) -> DashboardRead:
    settings = effective_settings(session, current_user.id)
    zone = ZoneInfo(settings.timezone)
    day = datetime.now(zone).date()
    start = datetime.combine(day, time.min, zone).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time.min, zone).astimezone(UTC)
    def count_apps(*conditions: ColumnElement[bool]) -> int:
        return session.scalar(select(func.count()).select_from(Application).where(Application.user_id == current_user.id, *conditions)) or 0
    discovered = session.scalar(select(func.count()).select_from(UserJob).where(UserJob.user_id == current_user.id, UserJob.created_at >= start, UserJob.created_at < end)) or 0
    strong = session.scalar(select(func.count()).select_from(JobMatch).where(JobMatch.user_id == current_user.id, JobMatch.hard_filter_passed.is_(True), JobMatch.score >= settings.minimum_match_score)) or 0
    return DashboardRead(jobs_discovered_today=discovered, strong_matches=strong, applications_prepared=count_apps(Application.status.in_(["prepared", "awaiting_approval"])), applications_submitted=count_apps(Application.submitted_at.is_not(None)), interviews=count_apps(Application.status == "interview"), responses=count_apps(Application.status.in_(["assessment", "interview", "rejected", "offer"])), offers=count_apps(Application.status == "offer"))


@router.post("/search")
def run_search(current_user: CurrentUser, session: SessionDep) -> dict[str, object]:
    from app.scheduler.pipeline import run_daily_search
    try:
        return run_daily_search(session, current_user.id)
    except (RuntimeError, ConnectionError) as error:
        raise HTTPException(503, "Search could not complete safely. No application was submitted.") from error
