import uuid

from app.scheduler.celery_app import celery_app


@celery_app.task(name="app.scheduler.tasks.discover_internships")  # type: ignore[untyped-decorator]
def discover_internships() -> str:
    """Placeholder for source-specific, permitted discovery tasks."""
    return "No source adapters configured."


@celery_app.task(
    name="app.scheduler.tasks.daily_internship_search",
    autoretry_for=(ConnectionError,),
    retry_backoff=True,
    max_retries=3,
)  # type: ignore[untyped-decorator]
def daily_internship_search(user_id: str) -> dict[str, str]:
    """Celery entrypoint; integrations are injected only after authorization review.

    Connection failures may retry. Authorization and policy failures are not
    exceptions here and therefore cannot be retried as source failures.
    """
    uuid.UUID(user_id)
    return {"status": "no_permitted_sources_configured", "user_id": user_id}
