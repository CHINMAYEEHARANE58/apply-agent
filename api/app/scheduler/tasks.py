import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.config.database import SessionLocal
from app.scheduler.celery_app import celery_app
from app.scheduler.pipeline import run_daily_search


@celery_app.task(name="app.scheduler.tasks.discover_internships")  # type: ignore[untyped-decorator]
def discover_internships() -> str:
    """Dispatch due users in their configured timezone, never operate websites."""
    from zoneinfo import ZoneInfo

    from app.scheduler.run_models import DailySearchRun
    from app.settings.service import effective_settings
    from app.users.models import User

    dispatched = 0
    with SessionLocal() as session:
        for user_id in session.scalars(select(User.id).where(User.is_active.is_(True))):
            settings = effective_settings(session, user_id)
            now = datetime.now(ZoneInfo(settings.timezone))
            if not settings.search_enabled or now.strftime("%H:%M") < settings.search_time:
                continue
            previous = session.scalar(select(DailySearchRun).where(DailySearchRun.user_id == user_id, DailySearchRun.local_date == now.date()))
            if previous is None or previous.status == "failed" and int(previous.summary.get("failures", 0)) < 4:
                daily_internship_search.delay(str(user_id))
                dispatched += 1
    return f"Queued {dispatched} due candidates."


@celery_app.task(
    name="app.scheduler.tasks.daily_internship_search",
    autoretry_for=(ConnectionError, OperationalError),
    acks_late=True,
    reject_on_worker_lost=True,
    retry_backoff=True,
    max_retries=3,
)  # type: ignore[untyped-decorator]
def daily_internship_search(user_id: str) -> dict[str, Any]:
    with SessionLocal() as session:
        return run_daily_search(session, uuid.UUID(user_id))
