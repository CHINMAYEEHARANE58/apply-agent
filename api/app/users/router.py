from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.auth.dependencies import CurrentUser, SessionDep
from app.config.settings import get_settings
from app.resumes.models import Resume
from app.resumes.storage import private_resume_storage
from app.users.models import User
from app.users.schemas import UserCreate, UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, session: SessionDep) -> User:
    settings = get_settings()
    if settings.auth_provider != "development" or settings.app_environment not in {
        "development",
        "test",
    }:
        raise HTTPException(403, "Create accounts through Clerk sign-up.")
    user = User(email=str(payload.email).lower())
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409, detail="A user with this email already exists."
        ) from exc
    session.refresh(user)
    return user


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: CurrentUser) -> User:
    return current_user


@router.patch("/me", response_model=UserRead)
def update_current_user(
    payload: UserUpdate, current_user: CurrentUser, session: SessionDep
) -> User:
    if current_user.clerk_user_id:
        raise HTTPException(409, "Update and verify your email through Clerk account settings.")
    current_user.email = str(payload.email).lower()
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409, detail="A user with this email already exists."
        ) from exc
    session.refresh(current_user)
    return current_user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_current_user(current_user: CurrentUser, session: SessionDep) -> None:
    keys = list(session.scalars(select(Resume.file_reference).where(Resume.user_id == current_user.id, Resume.type == "master")))
    # Validate every object first; no tampered reference may delete another
    # user's file. DB cascades delete historical lineages together, rather
    # than ORM per-resume deletes that can trigger immutable FK updates.
    try:
        paths = [private_resume_storage.owned_path(key, current_user.id) for key in keys]
        session.execute(delete(User).where(User.id == current_user.id))
        for path in paths:
            path.unlink(missing_ok=True)
        session.commit()
    except (OSError, ValueError) as error:
        session.rollback()
        raise HTTPException(503, "Private data deletion could not be completed. Please retry.") from error
