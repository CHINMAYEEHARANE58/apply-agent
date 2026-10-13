"""Verify Clerk session JWTs and bind them to local UUID accounts.

No identity is accepted from a browser-supplied UUID or email address. Keys
are fetched only from the configured Clerk issuer, never a JWT-supplied URL.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any
from urllib.parse import urlsplit

import httpx
import jwt
from fastapi import HTTPException
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.users.models import User


@lru_cache(maxsize=8)
def _jwks_client(issuer: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{issuer}/.well-known/jwks.json", timeout=5, lifespan=300)


def verify_clerk_session(token: str) -> dict[str, Any]:
    settings = get_settings()
    issuer = settings.clerk_issuer.rstrip("/")
    issuer_url = urlsplit(issuer)
    if (
        issuer_url.scheme != "https"
        or not issuer_url.hostname
        or issuer_url.username
        or issuer_url.password
        or issuer_url.path
        or issuer_url.query
        or issuer_url.fragment
        or not settings.clerk_authorized_parties
    ):
        raise HTTPException(503, "Clerk authentication is not configured.")
    try:
        key = (
            settings.clerk_jwt_key.replace("\\n", "\n")
            if settings.clerk_jwt_key
            else _jwks_client(issuer).get_signing_key_from_jwt(token).key
        )
        claims: dict[str, Any] = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=issuer,
            options={
                "require": ["exp", "iat", "nbf", "iss", "sub", "sid", "azp"],
                "verify_aud": False,
            },
        )
        if claims.get("azp") not in settings.clerk_authorized_parties:
            raise jwt.InvalidTokenError("Unauthorized party")
        if not isinstance(claims.get("sub"), str) or not re.fullmatch(
            r"user_[A-Za-z0-9]+", claims["sub"]
        ):
            raise jwt.InvalidTokenError("Invalid subject")
        if not isinstance(claims.get("sid"), str) or not re.fullmatch(
            r"sess_[A-Za-z0-9]+", claims["sid"]
        ):
            raise jwt.InvalidTokenError("A session token is required")
        if claims.get("sts") == "pending":
            raise jwt.InvalidTokenError("Pending session")
        return claims
    except jwt.PyJWKClientConnectionError as error:
        raise HTTPException(503, "Clerk verification is temporarily unavailable.") from error
    except jwt.PyJWTError as error:
        # Never return the JWT or raw provider error to the browser/logs.
        raise HTTPException(401, "Invalid or expired sign-in session.") from error


def verified_clerk_email(subject: str) -> str:
    """Fetch verified email using the server credential, not token custom claims."""
    key = get_settings().clerk_secret_key
    if not key or key.startswith("replace-"):
        raise HTTPException(503, "Clerk account synchronization is not configured.")
    try:
        response = httpx.get(
            f"https://api.clerk.com/v1/users/{subject}",
            headers={"Authorization": f"Bearer {key}"},
            timeout=5,
            follow_redirects=False,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("id") != subject or data.get("banned") or data.get("locked"):
            raise HTTPException(403, "This account is unavailable.")
        for email in data.get("email_addresses", []):
            if (
                email.get("id") == data.get("primary_email_address_id")
                and email.get("verification", {}).get("status") == "verified"
            ):
                return str(
                    TypeAdapter(EmailStr).validate_python(email.get("email_address"))
                ).lower()
        raise HTTPException(403, "Verify your primary email address before continuing.")
    except (httpx.HTTPError, ValueError, ValidationError) as error:
        raise HTTPException(
            503, "Clerk account synchronization is temporarily unavailable."
        ) from error


def clerk_user_for_session(token: str, session: Session) -> User:
    claims = verify_clerk_session(token)
    subject = claims["sub"]
    user = session.scalar(select(User).where(User.clerk_user_id == subject))
    if user is None:
        email = verified_clerk_email(subject)
        # Never auto-link by email: old local accounts require an explicit,
        # authenticated migration rather than takeover through matching email.
        if session.scalar(select(User.id).where(User.email == email)):
            raise HTTPException(409, "An existing account requires an explicit identity migration.")
        user = User(
            email=email, clerk_user_id=subject, is_active=True, last_login_at=datetime.now(UTC)
        )
        session.add(user)
        try:
            session.commit()
            session.refresh(user)
        except IntegrityError as error:
            session.rollback()
            user = session.scalar(select(User).where(User.clerk_user_id == subject))
            if user is None:
                raise HTTPException(
                    409, "Account synchronization conflict. Try signing in again."
                ) from error
    if not user.is_active:
        raise HTTPException(403, "This account is inactive.")
    return user
