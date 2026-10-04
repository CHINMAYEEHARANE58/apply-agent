from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.auth.dependencies import CurrentUser, SessionDep
from app.users.models import User
from app.users.schemas import UserCreate, UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, session: SessionDep) -> User:
    user = User(email=str(payload.email).lower())
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="A user with this email already exists.") from exc
    session.refresh(user)
    return user


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: CurrentUser) -> User:
    return current_user


@router.patch("/me", response_model=UserRead)
def update_current_user(payload: UserUpdate, current_user: CurrentUser, session: SessionDep) -> User:
    current_user.email = str(payload.email).lower()
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="A user with this email already exists.") from exc
    session.refresh(current_user)
    return current_user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_current_user(current_user: CurrentUser, session: SessionDep) -> None:
    session.delete(current_user)
    session.commit()
