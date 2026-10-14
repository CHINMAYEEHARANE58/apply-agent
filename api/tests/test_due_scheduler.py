from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import UUID

from test_authorization_isolation import create_user, headers

from app.main import app
from app.scheduler import tasks
from app.scheduler.run_models import DailySearchRun


def test_scheduler_uses_each_timezone_and_avoids_completed_or_disabled_candidates(client, monkeypatch):
    first = create_user(client, "due-india@example.com")
    second = create_user(client, "not-due-us@example.com")
    disabled = create_user(client, "disabled-due@example.com")
    for user, timezone in [(first, "Asia/Kolkata"), (second, "America/New_York"), (disabled, "Asia/Kolkata")]:
        assert client.put("/api/v1/settings/me", headers=headers(user), json={"timezone": timezone, "search_time": "09:00", "search_enabled": user != disabled}).status_code == 200
    fixed = datetime(2026, 10, 14, 4, 0, tzinfo=UTC)
    class Clock:
        @staticmethod
        def now(zone):
            return fixed.astimezone(zone)
    dispatch = Mock()
    monkeypatch.setattr(tasks, "datetime", Clock)
    monkeypatch.setattr(tasks.daily_internship_search, "delay", dispatch)
    assert tasks.discover_internships.run() == "Queued 1 due candidates."
    dispatch.assert_called_once_with(first)
    with app.state.test_session_factory() as session:
        session.add(DailySearchRun(user_id=UUID(first), local_date=fixed.date(), timezone="Asia/Kolkata", status="completed", summary={}))
        session.commit()
    dispatch.reset_mock()
    assert tasks.discover_internships.run() == "Queued 0 due candidates."
    dispatch.assert_not_called()
