import time
import uuid
from collections.abc import Callable
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.auth import clerk
from app.config.settings import get_settings
from app.main import app
from app.users.models import User


@pytest.fixture
def clerk_token(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> Callable[..., str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    monkeypatch.setenv("AUTH_PROVIDER", "clerk")
    monkeypatch.setenv("CLERK_ISSUER", "https://internagent-test.clerk.accounts.dev")
    monkeypatch.setenv("CLERK_JWT_KEY", public_key)
    monkeypatch.setenv("CLERK_AUTHORIZED_PARTIES", '["https://testserver"]')
    monkeypatch.setattr(clerk, "verified_clerk_email", lambda subject: f"{subject}@example.com")
    get_settings.cache_clear()

    def make_token(**overrides: Any) -> str:
        now = int(time.time())
        claims = {
            "iss": "https://internagent-test.clerk.accounts.dev",
            "sub": "user_owner",
            "sid": "sess_owner",
            "azp": "https://testserver",
            "iat": now - 1,
            "nbf": now - 1,
            "exp": now + 300,
        }
        claims.update(overrides)
        return jwt.encode(claims, private_key, algorithm="RS256")

    return make_token


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("claims", [
    {"exp": 1}, {"iss": "https://attacker.example"},
    {"azp": "https://attacker.example"}, {"sid": None},
    {"sub": "not-a-clerk-user"}, {"sts": "pending"},
    {"nbf": int(time.time()) + 86400},
])
def test_invalid_sessions_are_rejected(
    client: TestClient, clerk_token: Callable[..., str], claims: dict[str, Any]
) -> None:
    token = clerk_token(**claims)
    response = client.get("/api/v1/users/me", headers=bearer(token))
    assert response.status_code == 401
    assert token not in response.text


def test_unverified_signatures_and_unsigned_tokens_are_rejected(
    client: TestClient, clerk_token: Callable[..., str]
) -> None:
    claims = jwt.decode(clerk_token(), options={"verify_signature": False})
    forged = jwt.encode(claims, "attacker-secret-at-least-32-characters", algorithm="HS256")
    unsigned = jwt.encode(claims, key=None, algorithm="none")
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    for token in (forged, unsigned, jwt.encode(claims, other_key, algorithm="RS256")):
        assert client.get("/api/v1/users/me", headers=bearer(token)).status_code == 401


def test_clerk_disables_uuid_auth_and_local_signups(
    client: TestClient, clerk_token: Callable[..., str]
) -> None:
    assert client.get("/api/v1/users/me", headers={"X-User-Id": str(uuid.uuid4())}).status_code == 401
    assert client.post("/api/v1/users", json={"email": "attacker@example.com"}).status_code == 403
    assert client.get("/api/v1/users/me", headers=bearer("x" * 16385)).status_code == 401
    source = {"source_name": "attacker", "discovery_supported": True, "discovery_method": "api", "application_supported": True, "application_method": "api", "messaging_supported": True, "requires_user_confirmation": False, "authorization_verified": True}
    assert client.post("/api/v1/sources", json=source).status_code == 403


def test_first_signin_creates_one_stable_uuid_account(
    client: TestClient, clerk_token: Callable[..., str]
) -> None:
    first = client.get("/api/v1/users/me", headers=bearer(clerk_token()))
    assert first.status_code == 200
    assert uuid.UUID(first.json()["id"])
    assert first.json()["email"] == "user_owner@example.com"
    second = client.get("/api/v1/users/me", headers=bearer(clerk_token()))
    assert second.json()["id"] == first.json()["id"]
    with app.state.test_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(User)) == 1
    assert client.patch("/api/v1/users/me", headers=bearer(clerk_token()), json={"email": "new@example.com"}).status_code == 409


def test_clerk_identity_cannot_be_overridden_with_another_users_uuid(
    client: TestClient, clerk_token: Callable[..., str]
) -> None:
    owner_headers = bearer(clerk_token())
    other_headers = bearer(clerk_token(sub="user_other", sid="sess_other"))
    owner = client.get("/api/v1/users/me", headers=owner_headers).json()
    client.get("/api/v1/users/me", headers=other_headers)
    assert client.put("/api/v1/profile/me", headers=owner_headers, json={"full_name": "Owner"}).status_code == 200
    other_headers["X-User-Id"] = owner["id"]
    assert client.get("/api/v1/profile/me", headers=other_headers).status_code == 404
    assert client.get("/api/v1/users/me", headers=other_headers).json()["id"] != owner["id"]


def test_existing_email_is_not_automatically_linked(
    client: TestClient, clerk_token: Callable[..., str]
) -> None:
    with app.state.test_session_factory() as session:
        session.add(User(email="user_owner@example.com"))
        session.commit()
    assert client.get("/api/v1/users/me", headers=bearer(clerk_token())).status_code == 409


def test_inactive_account_is_rejected(
    client: TestClient, clerk_token: Callable[..., str]
) -> None:
    client.get("/api/v1/users/me", headers=bearer(clerk_token()))
    with app.state.test_session_factory() as session:
        user = session.scalar(select(User).where(User.clerk_user_id == "user_owner"))
        assert user is not None
        user.is_active = False
        session.commit()
    assert client.get("/api/v1/users/me", headers=bearer(clerk_token())).status_code == 403


def test_missing_configuration_fails_closed(
    client: TestClient, clerk_token: Callable[..., str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLERK_ISSUER", "")
    get_settings.cache_clear()
    assert client.get("/api/v1/users/me", headers=bearer(clerk_token())).status_code == 503


def test_jwks_outage_does_not_accept_an_unverified_token(
    client: TestClient, clerk_token: Callable[..., str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLERK_JWT_KEY", "")
    get_settings.cache_clear()

    def unavailable(issuer: str) -> Any:
        raise jwt.PyJWKClientConnectionError("network unavailable")

    monkeypatch.setattr(clerk, "_jwks_client", unavailable)
    assert client.get("/api/v1/users/me", headers=bearer(clerk_token())).status_code == 503


def test_unverified_primary_email_cannot_create_an_account(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    monkeypatch.setenv("CLERK_SECRET_KEY", "test-only-not-a-real-secret")
    get_settings.cache_clear()
    monkeypatch.setattr(clerk.httpx, "get", lambda *args, **kwargs: httpx.Response(
        200, request=httpx.Request("GET", "https://api.clerk.com/v1/users/user_owner"),
        json={"id": "user_owner", "primary_email_address_id": "email_1", "email_addresses": [
            {"id": "email_1", "email_address": "owner@example.com", "verification": {"status": "unverified"}}
        ]},
    ))
    with pytest.raises(HTTPException) as error:
        clerk.verified_clerk_email("user_owner")
    assert error.value.status_code == 403
    get_settings.cache_clear()
