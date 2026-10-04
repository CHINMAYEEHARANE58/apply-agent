from fastapi import APIRouter, status
from sqlalchemy import select

from app.auth.dependencies import CurrentUser, SessionDep
from app.preferences.models import InternshipPreference
from app.preferences.schemas import InternshipPreferenceRead, InternshipPreferenceUpsert
from app.security.errors import not_found

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.get("/me", response_model=InternshipPreferenceRead)
def get_preferences(current_user: CurrentUser, session: SessionDep) -> InternshipPreference:
    preference = session.scalar(select(InternshipPreference).where(InternshipPreference.user_id == current_user.id))
    if preference is None:
        raise not_found("Internship preference")
    return preference


@router.put("/me", response_model=InternshipPreferenceRead)
def upsert_preferences(payload: InternshipPreferenceUpsert, current_user: CurrentUser, session: SessionDep) -> InternshipPreference:
    preference = session.scalar(select(InternshipPreference).where(InternshipPreference.user_id == current_user.id))
    values = payload.model_dump()
    if preference is None:
        preference = InternshipPreference(user_id=current_user.id, **values)
        session.add(preference)
    else:
        for field, value in values.items():
            setattr(preference, field, value)
    session.commit()
    session.refresh(preference)
    return preference


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_preferences(current_user: CurrentUser, session: SessionDep) -> None:
    preference = session.scalar(select(InternshipPreference).where(InternshipPreference.user_id == current_user.id))
    if preference is None:
        raise not_found("Internship preference")
    session.delete(preference)
    session.commit()
