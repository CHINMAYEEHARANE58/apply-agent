import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config.database import get_session
from app.config.settings import get_settings
from app.users.models import User

SessionDep = Annotated[Session, Depends(get_session)]


def get_current_user(
    session: SessionDep,
    x_user_id: Annotated[uuid.UUID | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    """Verified Clerk identity; explicit development headers for tests only."""

    settings = get_settings()
    if settings.auth_provider == "clerk":
        from app.auth.clerk import clerk_user_for_session

        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="A Clerk sign-in session is required.")
        token = authorization.removeprefix("Bearer ")
        if not token or len(token) > 16_384:
            raise HTTPException(status_code=401, detail="Invalid sign-in session.")
        return clerk_user_for_session(token, session)
    if settings.auth_provider != "development" or settings.app_environment.casefold() not in {
        "development",
        "test",
    }:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "development_auth_disabled",
                "message": "Verified production authentication is not configured.",
            },
        )
    if x_user_id is None:
        raise HTTPException(status_code=401, detail="X-User-Id authentication header is required.")
    user = session.get(User, x_user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Authenticated user does not exist.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account is inactive.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
