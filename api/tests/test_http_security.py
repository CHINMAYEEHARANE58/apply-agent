from fastapi.testclient import TestClient

from app.main import app


def test_https_response_has_browser_security_headers() -> None:
    response = TestClient(app, base_url="https://testserver").get("/api/v1/health")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


def test_production_rejects_plain_http(monkeypatch) -> None:
    from app.config.settings import get_settings

    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    get_settings.cache_clear()
    try:
        response = TestClient(app).get("/api/v1/health")
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "https_required"
    finally:
        get_settings.cache_clear()
