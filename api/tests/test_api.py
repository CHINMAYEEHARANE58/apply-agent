from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    response = TestClient(app).get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unverified_source_returns_manual_path() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/sources",
        json={
            "source_name": "Manual-only Test Source",
            "discovery_supported": True,
            "discovery_method": "feed",
            "application_supported": True,
            "application_method": "authorized_api",
            "messaging_supported": False,
            "requires_user_confirmation": True,
            "authorization_verified": False,
        },
    )
    assert response.status_code == 201
    preparation = client.post(
        "/api/v1/sources/Manual-only%20Test%20Source/application-preparation"
    )
    assert preparation.status_code == 200
    assert preparation.json()["decision"] == "assisted_manual"
    assert preparation.json()["submission_endpoint_called"] is False
