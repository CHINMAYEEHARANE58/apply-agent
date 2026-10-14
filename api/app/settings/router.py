from fastapi import APIRouter
from sqlalchemy import select

from app.auth.dependencies import CurrentUser, SessionDep
from app.preferences.models import InternshipPreference
from app.settings.schemas import SettingsRead, SettingsUpdate
from app.settings.service import SHARED_FIELDS, effective_settings
from app.users.models import User
from app.users.settings_models import UserSettings

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/me", response_model=SettingsRead)
def get_settings(current_user: CurrentUser, session: SessionDep) -> SettingsRead:
    return effective_settings(session, current_user.id)


@router.put("/me", response_model=SettingsRead)
@router.patch("/me", response_model=SettingsRead)
def save_settings(payload: SettingsUpdate, current_user: CurrentUser, session: SessionDep) -> SettingsRead:
    session.scalar(select(User.id).where(User.id == current_user.id).with_for_update())
    settings = session.scalar(select(UserSettings).where(UserSettings.user_id == current_user.id))
    values = effective_settings(session, current_user.id).model_dump(exclude={"user_id"})
    values.update(payload.model_dump(exclude_unset=True))
    if settings is None:
        settings = UserSettings(user_id=current_user.id, **values)
        session.add(settings)
    else:
        for field, value in values.items():
            setattr(settings, field, value)
    # One authoritative preference: edits from either screen must agree.
    preference = session.scalar(select(InternshipPreference).where(InternshipPreference.user_id == current_user.id))
    if preference:
        for field in SHARED_FIELDS:
            setattr(preference, field, values[field])
        preference.preferred_search_time = values["search_time"]
    session.commit()
    return effective_settings(session, current_user.id)
