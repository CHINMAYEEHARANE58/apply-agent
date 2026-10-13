import uuid

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.config.database import get_session
from app.main import app


def test_database_outage_does_not_expose_queries_or_personal_data(client: TestClient) -> None:
    def unavailable() -> None:
        raise OperationalError("SELECT private_column FROM users", {"email": "private@example.com"}, RuntimeError("private connection failure"))

    app.dependency_overrides[get_session] = unavailable
    response = client.get("/api/v1/users/me", headers={"X-User-Id": str(uuid.uuid4())})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"
    assert "private" not in response.text
