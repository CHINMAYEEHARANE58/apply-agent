import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.preferences.models import InternshipPreference
from app.profiles.models import CandidateProfile
from app.settings.schemas import SettingsRead
from app.users.settings_models import UserSettings

SHARED_FIELDS = ("search_enabled", "minimum_match_score", "max_daily_applications", "application_mode")


def effective_settings(session: Session, user_id: uuid.UUID) -> SettingsRead:
    record = session.scalar(select(UserSettings).where(UserSettings.user_id == user_id))
    if record:
        values = {field: getattr(record, field) for field in SettingsRead.model_fields if field != "user_id"}
        values["search_time"] = values["search_time"] or "09:00"
        return SettingsRead(user_id=user_id, **values)
    values = {}
    preference = session.scalar(select(InternshipPreference).where(InternshipPreference.user_id == user_id))
    profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user_id))
    if preference:
        values.update({field: getattr(preference, field) for field in SHARED_FIELDS})
        values["search_time"] = preference.preferred_search_time or "09:00"
    if profile and profile.timezone:
        values["timezone"] = profile.timezone
    return SettingsRead(user_id=user_id, **values)
