import io
import uuid
import zipfile
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.main import app
from app.resumes.models import Resume, ResumeFactRecord
from app.resumes.processing import DOCX_MIME_TYPE, MAX_RESUME_UPLOAD_REQUEST_BYTES, PDF_MIME_TYPE
from app.resumes.router import approve_tailored_resume_if_unchanged
from app.resumes.storage import private_resume_storage


def create_user(client: TestClient, email: str) -> str:
    response = client.post("/api/v1/users", json={"email": email})
    assert response.status_code == 201
    return response.json()["id"]


def headers(user_id: str) -> dict[str, str]:
    return {"X-User-Id": user_id}


def docx_resume_payload(*, skills: str = "Python, TypeScript") -> bytes:
    """Create a minimally valid DOCX containing candidate-provided facts only."""

    document = f"""<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">
      <w:body>
        <w:p><w:r><w:t>SUMMARY</w:t></w:r></w:p>
        <w:p><w:r><w:t>Built FastAPI services at Acme.</w:t></w:r></w:p>
        <w:p><w:r><w:t>EXPERIENCE</w:t></w:r></w:p>
        <w:p><w:r><w:t>Built a FastAPI service at Acme.</w:t></w:r></w:p>
        <w:p><w:r><w:t>SKILLS</w:t></w:r></w:p>
        <w:p><w:r><w:t>{skills}</w:t></w:r></w:p>
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


def upload_master_resume(
    client: TestClient,
    user_id: str,
    *,
    filename: str = "master-resume.docx",
    content: bytes | None = None,
    content_type: str = DOCX_MIME_TYPE,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/resumes/upload",
        headers=headers(user_id),
        files={"file": (filename, content or docx_resume_payload(), content_type)},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_uploads_a_private_master_resume_and_never_exposes_its_storage_key(
    client: TestClient,
) -> None:
    user_id = create_user(client, "resume-owner@example.com")
    source_bytes = docx_resume_payload()

    uploaded = upload_master_resume(client, user_id, content=source_bytes)

    assert uploaded["type"] == "master"
    assert uploaded["version"] == 1
    assert uploaded["parser_status"] == "completed"
    assert uploaded["original_filename"] == "master-resume.docx"
    assert uploaded["content_type"] == DOCX_MIME_TYPE
    assert "file_reference" not in uploaded
    assert set(uploaded["parsed_resume_json"]) == {
        "contact",
        "summary",
        "education",
        "experience",
        "internships",
        "projects",
        "skills",
        "certifications",
        "achievements",
        "links",
    }
    assert uploaded["parsed_resume_json"]["skills"] == ["Python", "TypeScript"]

    stored_files = list(Path(private_resume_storage.root).rglob("*.docx"))
    assert len(stored_files) == 1
    assert stored_files[0].parent.name == user_id
    assert stored_files[0].read_bytes() != source_bytes
    assert private_resume_storage.read(f"{user_id}/{uploaded['id']}.docx") == source_bytes
    assert str(private_resume_storage.root) not in str(uploaded)

    with app.state.test_session_factory() as session:
        raw_resume = session.execute(
            text("SELECT parsed_resume_json, parsed_resume_encrypted FROM resumes")
        ).one()
        raw_fact_texts = list(session.execute(text("SELECT text FROM resume_facts")).scalars())

    assert raw_resume.parsed_resume_json in {None, "null"}
    assert raw_resume.parsed_resume_encrypted.startswith("internagent:v1:")
    assert "Python" not in raw_resume.parsed_resume_encrypted
    assert raw_fact_texts
    assert all(value.startswith("internagent:v1:") for value in raw_fact_texts)
    assert all("Python" not in value for value in raw_fact_texts)


def test_rejects_malformed_and_mime_mismatched_resume_uploads(client: TestClient) -> None:
    user_id = create_user(client, "invalid-upload@example.com")

    malformed = client.post(
        "/api/v1/resumes/upload",
        headers=headers(user_id),
        files={"file": ("resume.docx", b"not an Office file", DOCX_MIME_TYPE)},
    )
    assert malformed.status_code == 422
    assert malformed.json()["error"]["code"] == "invalid_file_signature"

    mismatched_mime = client.post(
        "/api/v1/resumes/upload",
        headers=headers(user_id),
        files={"file": ("resume.docx", docx_resume_payload(), PDF_MIME_TYPE)},
    )
    assert mismatched_mime.status_code == 422
    assert mismatched_mime.json()["error"]["code"] == "invalid_content_type"


def test_request_body_guard_rejects_oversized_multipart_before_parsing(client: TestClient) -> None:
    user_id = create_user(client, "body-limit@example.com")

    response = client.post(
        "/api/v1/resumes/upload",
        headers=headers(user_id),
        files={
            "file": (
                "oversized.docx",
                b"x" * MAX_RESUME_UPLOAD_REQUEST_BYTES,
                DOCX_MIME_TYPE,
            )
        },
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "request_body_too_large"


def test_resume_with_too_many_facts_is_rejected_before_private_storage(client: TestClient) -> None:
    user_id = create_user(client, "bounded-facts@example.com")
    many_skills = ", ".join(f"Skill{index}" for index in range(1_001))

    response = client.post(
        "/api/v1/resumes/upload",
        headers=headers(user_id),
        files={"file": ("bounded.docx", docx_resume_payload(skills=many_skills), DOCX_MIME_TYPE)},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "resume_fact_limit_exceeded"
    assert not list(Path(private_resume_storage.root).rglob("*"))


def test_master_resume_versions_are_append_only_and_immutable(client: TestClient) -> None:
    user_id = create_user(client, "versioned-resume@example.com")
    first = upload_master_resume(client, user_id, filename="first.docx")
    second = upload_master_resume(client, user_id, filename="second.docx")

    assert first["id"] != second["id"]
    assert first["version"] == 1
    assert second["version"] == 2
    assert second["supersedes_resume_id"] == first["id"]
    assert len(list(Path(private_resume_storage.root).rglob("*.docx"))) == 2

    patch_response = client.patch(
        f"/api/v1/resumes/{first['id']}",
        headers=headers(user_id),
        json={"generated_bullets": [{"text": "Rewritten content"}]},
    )
    delete_response = client.delete(f"/api/v1/resumes/{first['id']}", headers=headers(user_id))
    assert patch_response.status_code == 409
    assert delete_response.status_code == 409


def test_resume_fact_list_is_scoped_to_the_owner(client: TestClient) -> None:
    owner_id = create_user(client, "facts-owner@example.com")
    other_id = create_user(client, "facts-other@example.com")
    master = upload_master_resume(client, owner_id)

    owner_facts = client.get(f"/api/v1/resumes/{master['id']}/facts", headers=headers(owner_id))
    assert owner_facts.status_code == 200
    fact_items = owner_facts.json()["items"]
    assert fact_items
    assert {"fact_id", "category", "text", "source", "confidence"}.issubset(fact_items[0])
    assert {fact["source"] for fact in fact_items} == {"master_resume"}

    assert client.get(f"/api/v1/resumes/{master['id']}/facts", headers=headers(other_id)).status_code == 404
    assert client.get(f"/api/v1/resumes/{master['id']}", headers=headers(other_id)).status_code == 404


def test_fabricated_tailored_bullet_cannot_be_approved(client: TestClient) -> None:
    user_id = create_user(client, "truthful-resume@example.com")
    master = upload_master_resume(client, user_id)
    facts_response = client.get(f"/api/v1/resumes/{master['id']}/facts", headers=headers(user_id))
    assert facts_response.status_code == 200
    python_fact = next(fact for fact in facts_response.json()["items"] if fact["text"] == "Python")

    tailored = client.post(
        "/api/v1/resumes/tailored",
        headers=headers(user_id),
        json={
            "source_resume_id": master["id"],
            "generated_bullets": [
                {
                    "text": "Led a machine learning team at Google and earned an AWS certification.",
                    "supporting_fact_ids": [python_fact["fact_id"]],
                }
            ],
        },
    )
    assert tailored.status_code == 201, tailored.text

    approval = client.post(
        f"/api/v1/resumes/{tailored.json()['id']}/approve",
        headers=headers(user_id),
        json={},
    )
    assert approval.status_code == 422
    assert approval.json()["error"]["code"] == "resume_verification_failed"

    stored = client.get(f"/api/v1/resumes/{tailored.json()['id']}", headers=headers(user_id))
    assert stored.status_code == 200
    assert stored.json()["approval_status"] == "draft"


def test_supported_tailored_resume_is_approved_from_its_persisted_content(
    client: TestClient,
) -> None:
    user_id = create_user(client, "approved-tailored@example.com")
    master = upload_master_resume(client, user_id)
    facts_response = client.get(f"/api/v1/resumes/{master['id']}/facts", headers=headers(user_id))
    experience_fact = next(
        fact
        for fact in facts_response.json()["items"]
        if fact["text"] == "Built a FastAPI service at Acme."
    )
    tailored = client.post(
        "/api/v1/resumes/tailored",
        headers=headers(user_id),
        json={
            "source_resume_id": master["id"],
            "generated_bullets": [
                {
                    "text": "Built a FastAPI service at Acme.",
                    "supporting_fact_ids": [experience_fact["fact_id"]],
                }
            ],
        },
    )
    assert tailored.status_code == 201, tailored.text

    approval = client.post(
        f"/api/v1/resumes/{tailored.json()['id']}/approve",
        headers=headers(user_id),
        json={},
    )
    assert approval.status_code == 200, approval.text
    assert approval.json()["resume"]["approval_status"] == "approved"


def test_stale_verification_cannot_approve_replaced_tailored_content(client: TestClient) -> None:
    user_id = create_user(client, "approval-race@example.com")
    user_uuid = uuid.UUID(user_id)
    master = upload_master_resume(client, user_id)
    facts_response = client.get(f"/api/v1/resumes/{master['id']}/facts", headers=headers(user_id))
    experience_fact = next(
        fact
        for fact in facts_response.json()["items"]
        if fact["text"] == "Built a FastAPI service at Acme."
    )
    tailored_response = client.post(
        "/api/v1/resumes/tailored",
        headers=headers(user_id),
        json={
            "source_resume_id": master["id"],
            "generated_bullets": [
                {
                    "text": "Built a FastAPI service at Acme.",
                    "supporting_fact_ids": [experience_fact["fact_id"]],
                }
            ],
        },
    )
    assert tailored_response.status_code == 201, tailored_response.text
    tailored_id = uuid.UUID(tailored_response.json()["id"])

    # This represents the ciphertext observed and verified by an approval
    # transaction immediately before another request updates the draft.
    with app.state.test_session_factory() as session:
        stale_ciphertext = session.scalar(
            select(Resume.generated_bullets_encrypted).where(Resume.id == tailored_id)
        )
    assert stale_ciphertext is not None

    replacement = client.patch(
        f"/api/v1/resumes/{tailored_id}",
        headers=headers(user_id),
        json={
            "generated_bullets": [
                {
                    "text": "Led a Kubernetes platform team at Google.",
                    "supporting_fact_ids": [experience_fact["fact_id"]],
                }
            ]
        },
    )
    assert replacement.status_code == 200, replacement.text

    with app.state.test_session_factory() as session:
        stale_resume = Resume(
            id=tailored_id,
            user_id=user_uuid,
            type="tailored",
            file_reference="unused-in-compare-and-set",
            generated_bullets_encrypted=stale_ciphertext,
        )
        with pytest.raises(HTTPException) as error:
            approve_tailored_resume_if_unchanged(stale_resume, user_uuid, session)
    assert error.value.status_code == 409
    assert error.value.detail["code"] == "tailored_resume_changed_during_approval"

    stored = client.get(f"/api/v1/resumes/{tailored_id}", headers=headers(user_id))
    assert stored.status_code == 200
    assert stored.json()["approval_status"] == "draft"


def test_tailored_content_and_facts_are_record_bound_encrypted_data(client: TestClient) -> None:
    user_id = create_user(client, "bound-encryption@example.com")
    master = upload_master_resume(client, user_id)
    facts_response = client.get(f"/api/v1/resumes/{master['id']}/facts", headers=headers(user_id))
    assert facts_response.status_code == 200
    experience_fact = next(
        fact
        for fact in facts_response.json()["items"]
        if fact["text"] == "Built a FastAPI service at Acme."
    )

    tailored_response = client.post(
        "/api/v1/resumes/tailored",
        headers=headers(user_id),
        json={
            "source_resume_id": master["id"],
            "generated_bullets": [
                {
                    "text": "Built a FastAPI service at Acme.",
                    "supporting_fact_ids": [experience_fact["fact_id"]],
                }
            ],
        },
    )
    assert tailored_response.status_code == 201, tailored_response.text
    tailored = tailored_response.json()
    assert tailored["generated_bullets"][0]["text"] == "Built a FastAPI service at Acme."

    with app.state.test_session_factory() as session:
        raw_tailored = session.scalar(
            select(Resume).where(Resume.id == uuid.UUID(tailored["id"]))
        )
        assert raw_tailored is not None
        assert raw_tailored.generated_bullets_json in {None, "null"}
        assert raw_tailored.generated_bullets_encrypted.startswith("internagent:v1:")
        assert "FastAPI" not in raw_tailored.generated_bullets_encrypted

        records = list(
            session.scalars(
                select(ResumeFactRecord)
                .where(ResumeFactRecord.resume_id == uuid.UUID(master["id"]))
                .order_by(ResumeFactRecord.created_at)
            )
        )
        assert len(records) >= 2
        cited = next(record for record in records if str(record.fact_id) == experience_fact["fact_id"])
        donor = next(record for record in records if record.fact_id != cited.fact_id)
        # Simulate a privileged storage attacker transplanting a valid ciphertext.
        # Its record-bound AAD must prevent it from being interpreted as a fact.
        cited.text = donor.text
        session.commit()

    approval = client.post(
        f"/api/v1/resumes/{tailored['id']}/approve",
        headers=headers(user_id),
        json={},
    )
    assert approval.status_code == 409
    assert approval.json()["error"]["code"] == "resume_fact_integrity_failed"


def test_plaintext_or_metadata_tampering_cannot_become_a_resume_fact(client: TestClient) -> None:
    user_id = create_user(client, "fact-integrity@example.com")
    master = upload_master_resume(client, user_id)

    with app.state.test_session_factory() as session:
        record = session.scalar(
            select(ResumeFactRecord)
            .where(ResumeFactRecord.resume_id == uuid.UUID(master["id"]))
            .order_by(ResumeFactRecord.created_at)
        )
        assert record is not None
        # A non-encrypted string must never be accepted as a legacy fact.
        record.text = "AWS certified Kubernetes architect"
        session.commit()

    fact_list = client.get(f"/api/v1/resumes/{master['id']}/facts", headers=headers(user_id))
    assert fact_list.status_code == 409
    assert fact_list.json()["error"]["code"] == "resume_fact_integrity_failed"


def test_orm_schema_prohibits_plaintext_tailored_bullet_storage(client: TestClient) -> None:
    user_id = uuid.UUID(create_user(client, "tailored-constraint@example.com"))
    with app.state.test_session_factory() as session:
        session.add(
            Resume(
                id=uuid.uuid4(),
                user_id=user_id,
                type="tailored",
                file_reference="tailored/plaintext-should-fail",
                parsed_resume_json=None,
                version=1,
                parser_status="completed",
                approval_status="draft",
                generated_bullets_json=[{"text": "Plaintext candidate content"}],
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
