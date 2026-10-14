import io
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from test_authorization_isolation import create_user, headers
from test_secure_resume_api import docx_resume_payload, upload_master_resume

from app.config.settings import get_settings
from app.main import app
from app.resumes.models import Resume
from app.resumes.processing import DOCX_MIME_TYPE
from app.resumes.storage import private_resume_storage


@pytest.mark.parametrize("body", [{"email": "not-email"}, {}, {"email": ""}, {"email": "x" * 1000}, {"email": "valid@example.com", "is_active": False}])
def test_invalid_or_privilege_bearing_signup_bodies(client: TestClient, body) -> None:
    assert client.post("/api/v1/users", json=body).status_code == 422


def test_email_uniqueness_and_private_fields(client: TestClient) -> None:
    response = client.post("/api/v1/users", json={"email": "UNIQUE@example.com"})
    assert response.status_code == 201
    assert client.post("/api/v1/users", json={"email": "unique@example.com"}).status_code == 409
    assert "password_hash" not in response.json() and "clerk_user_id" not in response.json()


@pytest.mark.parametrize("payload", [
    {"full_name": ""}, {"full_name": "x" * 201}, {"full_name": "A", "phone": "x" * 41},
    {"full_name": "A", "linkedin_url": "javascript:alert(1)"}, {"full_name": "A", "graduation_year": 100},
    {"full_name": "A", "user_id": str(uuid4())},
])
def test_profile_validation(client: TestClient, payload) -> None:
    user_id = create_user(client, "profile-validation@example.com")
    assert client.put("/api/v1/profile/me", headers=headers(user_id), json=payload).status_code == 422


@pytest.mark.parametrize("payload", [
    {"minimum_stipend": -1}, {"min_duration": 6, "max_duration": 3}, {"minimum_match_score": 101},
    {"max_daily_applications": -1}, {"earliest_start_date": "not-a-date"},
    {"earliest_start_date": "2027-02-01", "latest_start_date": "2027-01-01"},
    {"preferred_search_time": "25:90"}, {"application_mode": "ignore-permissions"}, {"duration_unit": "years"},
])
def test_preference_validation(client: TestClient, payload) -> None:
    user_id = create_user(client, "preference-validation@example.com")
    assert client.put("/api/v1/preferences/me", headers=headers(user_id), json=payload).status_code == 422


def test_two_user_profile_preferences_and_application_isolation_both_directions(client: TestClient) -> None:
    users = [create_user(client, f"user-{index}@example.com") for index in range(2)]
    apps = []
    for index, user in enumerate(users):
        auth = headers(user)
        assert client.put("/api/v1/profile/me", headers=auth, json={"full_name": f"Candidate {index}", "phone": f"+1000000000{index}", "city": ["Pune", "London"][index], "relocation_allowed": bool(index)}).status_code == 200
        assert client.put("/api/v1/preferences/me", headers=auth, json={"roles": [["Software Intern"], ["Design Intern"]][index], "preferred_cities": [["Pune"], ["London"]][index], "minimum_stipend": 20000, "currency": "INR", "min_duration": 3, "max_duration": 6, "duration_unit": "months", "max_daily_applications": 8}).status_code == 200
        job = client.post("/api/v1/jobs", headers=auth, json={"source": "test", "external_job_id": str(index), "job_url": f"https://example.com/job{index}", "company": "Test", "title": "Intern", "description": "Fixture", "fingerprint": str(index) * 64}).json()
        apps.append(client.post("/api/v1/applications", headers=auth, json={"job_id": job["id"], "cover_letter": f"Private letter {index}"}).json())
    for index, user in enumerate(users):
        auth = headers(user)
        assert client.get("/api/v1/profile/me", headers=auth).json()["full_name"] == f"Candidate {index}"
        assert client.get("/api/v1/preferences/me", headers=auth).json()["user_id"] == user
        assert client.get("/api/v1/applications", headers=auth).json()["total"] == 1
        other = apps[1 - index]["id"]
        assert client.get(f"/api/v1/applications/{other}", headers=auth).status_code == 404
        assert client.patch(f"/api/v1/applications/{other}", headers=auth, json={"cover_letter": "stolen"}).status_code == 404
        assert client.delete(f"/api/v1/applications/{other}", headers=auth).status_code == 404


@pytest.mark.parametrize("filename,content,mime", [
    ("malware.pdf", b"MZfake executable", "application/pdf"),
    ("page.pdf", b"<html><script>alert(1)</script></html>", "application/pdf"),
    ("empty.pdf", b"", "application/pdf"), ("malformed.pdf", b"%PDF-1.7\n%%EOF", "application/pdf"),
    ("malware.exe.pdf", b"MZfake", "application/pdf"),
    ("x" * 256 + ".docx", docx_resume_payload(), DOCX_MIME_TYPE),
    ("resume.docx", docx_resume_payload(), "application/octet-stream"),
], ids=["renamed-exe", "renamed-html", "empty", "malformed", "double-extension", "long-filename", "unsupported-mime"])
def test_malicious_upload_matrix(client: TestClient, filename, content, mime) -> None:
    user_id = create_user(client, "upload-validation@example.com")
    response = client.post("/api/v1/resumes/upload", headers=headers(user_id), files={"file": (filename, content, mime)})
    assert response.status_code in {400, 413, 422}
    assert client.get("/api/v1/resumes", headers=headers(user_id)).json()["total"] == 0


@pytest.mark.parametrize("filename", ["../../secret.docx", "..\\..\\secret.docx"])
def test_traversal_filenames_are_sanitized_and_never_used_as_paths(client: TestClient, filename) -> None:
    user_id = create_user(client, "traversal@example.com")
    resume = upload_master_resume(client, user_id, filename=filename)
    assert resume["original_filename"] == "secret.docx"
    with app.state.test_session_factory() as session:
        row = session.get(Resume, UUID(str(resume["id"])))
        assert row.file_reference == f'{user_id}/{resume["id"]}.docx'
        assert private_resume_storage.owned_path(row.file_reference, UUID(user_id)).is_file()
    assert "file_reference" not in resume


def test_valid_pdf_upload_is_private(client: TestClient) -> None:
    user_id = create_user(client, "pdf-upload@example.com")
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    payload = io.BytesIO()
    writer.write(payload)
    response = client.post("/api/v1/resumes/upload", headers=headers(user_id), files={"file": ("resume.pdf", payload.getvalue(), "application/pdf")})
    assert response.status_code == 201
    assert response.json()["parsed_resume_json"]["skills"] == []
    assert "file_reference" not in response.json()


def test_storage_failure_is_safe_and_creates_no_record(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = create_user(client, "storage-failure@example.com")
    def unavailable(*args, **kwargs):
        raise OSError("/private/internal/path credential")
    monkeypatch.setattr(private_resume_storage, "save", unavailable)
    response = client.post("/api/v1/resumes/upload", headers=headers(user_id), files={"file": ("resume.docx", docx_resume_payload(), DOCX_MIME_TYPE)})
    assert response.status_code == 503
    assert "internal/path" not in response.text and "credential" not in response.text
    assert client.get("/api/v1/resumes", headers=headers(user_id)).json()["total"] == 0


def test_account_deletion_removes_only_owners_private_objects(client: TestClient) -> None:
    users = [create_user(client, f"delete-{index}@example.com") for index in range(2)]
    objects = []
    for user in users:
        resume = upload_master_resume(client, user)
        with app.state.test_session_factory() as session:
            row = session.get(Resume, UUID(str(resume["id"])))
            objects.append(private_resume_storage._path_for_key(row.file_reference))
    assert all(path.exists() for path in objects)
    assert client.delete("/api/v1/users/me", headers=headers(users[0])).status_code == 204
    assert not objects[0].exists() and objects[1].exists()


def test_parameterized_sql_and_standard_api_errors(client: TestClient) -> None:
    user_id = create_user(client, "injection@example.com")
    auth = headers(user_id)
    payload = "' OR '1'='1"
    assert client.put("/api/v1/profile/me", headers=auth, json={"full_name": payload}).status_code == 200
    assert client.get("/api/v1/profile/me", headers=auth).json()["full_name"] == payload
    assert client.get("/api/v1/jobs", headers=auth, params={"query": payload}).json()["total"] == 0
    assert client.get("/api/v1/resumes/not-a-uuid", headers=auth).status_code == 422
    assert client.get("/api/v1/resumes?limit=0", headers=auth).status_code == 422
    assert client.put("/api/v1/preferences/me", headers={**auth, "content-type": "application/json"}, content="{bad json").status_code == 422


def test_json_body_limit_rejects_oversized_input(client: TestClient) -> None:
    response = client.post("/api/v1/users", content=b"x" * (1024 * 1024 + 1), headers={"content-type": "application/json"})
    assert response.status_code == 413


def test_strict_cors_preflight(client: TestClient) -> None:
    allowed = client.options("/api/v1/profile/me", headers={"Origin": "https://testserver", "Access-Control-Request-Method": "PUT", "Access-Control-Request-Headers": "authorization,content-type"})
    assert allowed.status_code == 200 and allowed.headers["access-control-allow-origin"] == "https://testserver"
    denied = client.options("/api/v1/profile/me", headers={"Origin": "https://attacker.example", "Access-Control-Request-Method": "PUT"})
    assert denied.status_code == 400 and "access-control-allow-origin" not in denied.headers


def test_rate_limit_is_bounded_without_breaking_normal_requests(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "2")
    get_settings.cache_clear()
    assert client.get("/api/v1/users/me").status_code == 401
    assert client.get("/api/v1/users/me").status_code == 401
    response = client.get("/api/v1/users/me")
    assert response.status_code == 429 and response.headers["retry-after"] == "60"
