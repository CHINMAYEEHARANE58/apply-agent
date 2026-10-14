import subprocess
import sys
import time
from pathlib import Path
from uuid import UUID, uuid4

import httpx
from sqlalchemy import text
from test_secure_resume_api import docx_resume_payload


def test_http_profile_preferences_and_private_resume_survive_backend_restart(postgres_engine, tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    base = "http://127.0.0.1:8123/api/v1"
    environment = {
        "PATH": "/opt/homebrew/bin:/usr/bin:/bin", "APP_ENVIRONMENT": "test", "AUTH_PROVIDER": "development",
        "DATABASE_URL": postgres_engine.url.render_as_string(hide_password=False), "DATABASE_DIRECT_URL": "",
        "APP_ENCRYPTION_KEY": "test-only-http-restart-key-at-least-32-characters",
        "PRIVATE_RESUME_STORAGE_PATH": str(tmp_path / "private-resumes"),
        "CLERK_SECRET_KEY": "", "CLERK_ISSUER": "", "CLERK_JWT_KEY": "",
        "ALLOWED_ORIGINS": "[]", "CLERK_AUTHORIZED_PARTIES": "[]",
        "REDIS_URL": "redis://127.0.0.1:56379/0",
    }
    def start():
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8123", "--no-access-log"], cwd=root, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            if process.poll() is not None:
                raise AssertionError("Isolated HTTP backend failed to start")
            try:
                if httpx.get(f"{base}/health", timeout=0.2, trust_env=False).status_code == 200:
                    return process
            except httpx.HTTPError:
                pass
            time.sleep(0.1)
        process.terminate()
        process.wait(timeout=5)
        raise AssertionError("Isolated backend startup timed out")
    process = start()
    users = []
    jobs = []
    try:
        with httpx.Client(base_url=base + "/", trust_env=False) as client:
            for suffix in ["a", "b"]:
                response = client.post("users", json={"email": f"http-restart-{tmp_path.name}-{suffix}@example.com"})
                assert response.status_code == 201
                users.append(response.json()["id"])
            auth = {"X-User-Id": users[0]}
            assert client.put("profile/me", headers=auth, json={"full_name": "Test User A", "city": "Pune"}).status_code == 200
            assert client.put("preferences/me", headers=auth, json={"roles": ["Software Engineering Intern", "Frontend Intern"], "skills": ["React", "JavaScript", "Node.js", "Python"], "preferred_cities": ["Pune", "Bengaluru"], "minimum_stipend": 20000, "currency": "INR", "min_duration": 3, "max_duration": 6, "duration_unit": "months", "max_daily_applications": 8}).status_code == 200
            upload = client.post("resumes/upload", headers=auth, files={"file": ("master.docx", docx_resume_payload(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
            assert upload.status_code == 201
            resume_id = upload.json()["id"]
            assert client.put("settings/me", headers=auth, json={"timezone": "Asia/Kolkata", "application_mode": "batch", "maximum_applications_prepared_daily": 3, "max_daily_applications": 8}).status_code == 200
            job = client.post("jobs", headers=auth, json={"source": "manual", "external_job_id": uuid4().hex, "job_url": "https://example.com/restart-fixture", "company": "Restart QA", "title": "Software Engineering Intern", "description": "Build Python FastAPI services.", "skills": ["Python"], "location": "Pune", "workplace_type": "remote", "duration": "4 months", "stipend": 20000, "currency": "INR", "fingerprint": uuid4().hex * 2})
            assert job.status_code == 201
            jobs.append(job.json()["id"])
            assert client.patch(f"jobs/{jobs[0]}/state", headers=auth, json={"saved": True}).status_code == 200
            searched = client.post("dashboard/search", headers=auth)
            assert searched.status_code == 200 and searched.json()["applications_prepared"] == 1
            application = client.get("applications", headers=auth).json()["items"][0]
            process.terminate()
            process.wait(timeout=5)
            process = start()
            assert client.get("profile/me", headers=auth).json()["full_name"] == "Test User A"
            preferences = client.get("preferences/me", headers=auth).json()
            assert preferences["minimum_stipend"] == "20000.00" and preferences["max_daily_applications"] == 8
            assert client.get(f"resumes/{resume_id}", headers=auth).json()["original_filename"] == "master.docx"
            settings = client.get("settings/me", headers=auth).json()
            assert settings["timezone"] == "Asia/Kolkata" and settings["maximum_applications_prepared_daily"] == 3
            assert client.get(f"jobs/{jobs[0]}/state", headers=auth).json()["saved"]
            assert client.get("dashboard", headers=auth).json()["applications_prepared"] == 1
            assert client.get("applications", headers=auth).json()["items"][0]["id"] == application["id"]
            assert client.post("dashboard/search", headers=auth).json()["status"] == "already_completed"
            assert client.post(f'applications/{application["id"]}/approve', headers=auth).status_code == 200
            download = client.get(f'resumes/{application["resume_id"]}/download', headers=auth)
            assert download.status_code == 200 and download.content.startswith(b"%PDF-")
            assert client.get(f'applications/{application["id"]}', headers={"X-User-Id": users[1]}).status_code == 404
            assert client.get(f"resumes/{resume_id}", headers={"X-User-Id": users[1]}).status_code == 404
            assert client.get("profile/me", headers={"X-User-Id": users[1]}).status_code == 404
            assert client.get("profile/me").status_code == 401
            for user in users:
                assert client.delete("users/me", headers={"X-User-Id": user}).status_code == 204
    finally:
        process.terminate()
        process.wait(timeout=5)
        with postgres_engine.begin() as connection:
            for user_id in users:
                connection.execute(text("DELETE FROM users WHERE id=:id"), {"id": UUID(user_id)})
            for job_id in jobs:
                connection.execute(text("DELETE FROM jobs WHERE id=:id"), {"id": UUID(job_id)})
