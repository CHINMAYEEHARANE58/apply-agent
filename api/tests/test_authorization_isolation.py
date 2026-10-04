import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.config.settings import get_settings
from app.resumes.processing import DOCX_MIME_TYPE


def create_user(client: TestClient, email: str) -> str:
    response = client.post("/api/v1/users", json={"email": email})
    assert response.status_code == 201
    return response.json()["id"]


def headers(user_id: str) -> dict[str, str]:
    return {"X-User-Id": user_id}


def master_resume_upload(client: TestClient, user_id: str, *, filename: str = "master.docx") -> dict[str, object]:
    response = client.post(
        "/api/v1/resumes/upload",
        headers=headers(user_id),
        files={"file": (filename, docx_resume_payload(), DOCX_MIME_TYPE)},
    )
    assert response.status_code == 201
    return response.json()


def docx_resume_payload() -> bytes:
    document = """<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">
      <w:body>
        <w:p><w:r><w:t>SKILLS</w:t></w:r></w:p>
        <w:p><w:r><w:t>Python, TypeScript</w:t></w:r></w:p>
      </w:body>
    </w:document>"""
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
            <Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">
              <Override PartName=\"/word/document.xml\"
                ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\" />
            </Types>""",
        )
        archive.writestr("word/document.xml", document)
    return payload.getvalue()


def test_requests_require_an_authenticated_user(client: TestClient) -> None:
    response = client.get("/api/v1/resumes")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "request_error"


def test_development_identity_header_fails_closed_outside_development(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    get_settings.cache_clear()

    response = client.get("/api/v1/resumes", headers={"X-User-Id": "00000000-0000-0000-0000-000000000001"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "development_auth_disabled"


def test_user_owned_profile_and_resume_cannot_be_read_by_another_user(client: TestClient) -> None:
    owner_id = create_user(client, "owner@example.com")
    other_id = create_user(client, "other@example.com")
    owner_headers = headers(owner_id)

    profile_response = client.put("/api/v1/profile/me", headers=owner_headers, json={"full_name": "Owner Example", "relocation_allowed": True})
    assert profile_response.status_code == 200
    assert client.get("/api/v1/profile/me", headers=headers(other_id)).status_code == 404

    resume_id = master_resume_upload(client, owner_id)["id"]
    assert client.get(f"/api/v1/resumes/{resume_id}", headers=headers(other_id)).status_code == 404
    other_list = client.get("/api/v1/resumes", headers=headers(other_id)).json()
    assert other_list == {"items": [], "total": 0, "limit": 20, "offset": 0}


def test_resume_pagination_is_scoped_to_the_current_user(client: TestClient) -> None:
    user_id = create_user(client, "paging@example.com")
    user_headers = headers(user_id)
    master_resume_upload(client, user_id, filename="one.docx")
    master_resume_upload(client, user_id, filename="two.docx")
    page = client.get("/api/v1/resumes?limit=1&offset=1", headers=user_headers).json()
    assert len(page["items"]) == 1
    assert page["total"] == 2


def test_user_owned_application_is_isolated_and_preferences_are_validated(client: TestClient) -> None:
    owner_id = create_user(client, "application-owner@example.com")
    other_id = create_user(client, "application-other@example.com")
    owner_headers = headers(owner_id)
    invalid_preferences = client.put(
        "/api/v1/preferences/me",
        headers=owner_headers,
        json={"min_duration": 16, "max_duration": 8},
    )
    assert invalid_preferences.status_code == 422
    job = client.post(
        "/api/v1/jobs",
        headers=owner_headers,
        json={
            "source": "fixture",
            "external_job_id": "job-1",
            "job_url": "https://example.com/jobs/1",
            "company": "Example",
            "title": "Software Engineering Intern",
            "description": "Untrusted fixture content.",
            "fingerprint": "a" * 64,
        },
    )
    assert job.status_code == 201
    application = client.post("/api/v1/applications", headers=owner_headers, json={"job_id": job.json()["id"], "status": "prepared"})
    assert application.status_code == 201
    application_id = application.json()["id"]
    assert client.get(f"/api/v1/applications/{application_id}", headers=headers(other_id)).status_code == 404
    audit = client.post(
        "/api/v1/audit-events",
        headers=owner_headers,
        json={"event_type": "application_created", "entity_type": "application", "entity_id": application_id, "metadata": {"source": "test"}},
    )
    assert audit.status_code == 201
    assert audit.json()["metadata"] == {"source": "test"}
