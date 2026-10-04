from celery import Celery  # type: ignore[import-untyped]

from app.core.config import get_settings

settings = get_settings()
celery_app = Celery("internagent", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.beat_schedule = {
    "daily-internship-discovery": {
        "task": "app.scheduler.tasks.discover_internships",
        "schedule": 60 * 60 * 24,
    }
}
