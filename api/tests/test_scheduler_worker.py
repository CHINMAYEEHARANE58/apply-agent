import os
from uuid import uuid4

from celery import Celery
from redis import Redis

from app.scheduler.celery_app import celery_app


def test_beat_schedule_points_at_a_registered_task() -> None:
    celery_app.loader.import_default_modules()
    for entry in celery_app.conf.beat_schedule.values():
        assert entry["task"] in celery_app.tasks


def test_actual_redis_and_worker_execute_the_safe_no_source_task() -> None:
    url = os.environ.get("TEST_REDIS_URL", "")
    assert url.startswith("redis://127.0.0.1:"), "Set dedicated TEST_REDIS_URL, never use REDIS_URL from .env"
    redis = Redis.from_url(url)
    assert redis.ping()
    client = Celery("qa-test", broker=url, backend=url)
    try:
        result = client.send_task("app.scheduler.tasks.daily_internship_search", args=[str(uuid4())], queue="internagent-qa")
        response = result.get(timeout=10)
        # An unknown identity must not create a run or access another user.
        # This is transport testing; populated pipeline journeys are separate.
        assert response["status"] == "user_not_found"
        assert response["jobs_evaluated"] == response["applications_prepared"] == 0
        result.forget()
    finally:
        client.close()
