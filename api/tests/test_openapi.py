from fastapi.testclient import TestClient


def test_openapi_documents_phase_two_routes(client: TestClient) -> None:
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/resumes" in paths
    assert "/api/v1/applications" in paths
    assert "/api/v1/preferences/me" in paths
