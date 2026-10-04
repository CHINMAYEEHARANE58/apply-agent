from app.scheduler.celery_app import celery_app


@celery_app.task(name="app.scheduler.tasks.discover_internships")  # type: ignore[untyped-decorator]
def discover_internships() -> str:
    """Placeholder for source-specific, permitted discovery tasks."""
    return "No source adapters configured."
