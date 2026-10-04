from fastapi import APIRouter, status
from sqlalchemy import select

from app.auth.dependencies import CurrentUser, SessionDep
from app.profiles.models import CandidateProfile
from app.profiles.schemas import CandidateProfileRead, CandidateProfileUpsert
from app.security.errors import not_found

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/me", response_model=CandidateProfileRead)
def get_profile(current_user: CurrentUser, session: SessionDep) -> CandidateProfile:
    profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == current_user.id))
    if profile is None:
        raise not_found("Candidate profile")
    return profile


@router.put("/me", response_model=CandidateProfileRead)
def upsert_profile(payload: CandidateProfileUpsert, current_user: CurrentUser, session: SessionDep) -> CandidateProfile:
    profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == current_user.id))
    values = payload.model_dump(mode="json")
    if profile is None:
        profile = CandidateProfile(user_id=current_user.id, **values)
        session.add(profile)
    else:
        for field, value in values.items():
            setattr(profile, field, value)
    session.commit()
    session.refresh(profile)
    return profile


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(current_user: CurrentUser, session: SessionDep) -> None:
    profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == current_user.id))
    if profile is None:
        raise not_found("Candidate profile")
    session.delete(profile)
    session.commit()
