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
) -> User:
    """Development-only identity boundary.

    Header-selected identities are intentionally disabled outside development
    and test environments. A production deployment must install verified
    session, JWT, or authorized OAuth authentication before enabling these
    user-owned routes.
    """

    if get_settings().app_environment.casefold() not in {"development", "test"}:
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
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
