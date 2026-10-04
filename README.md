# InternAgent

InternAgent is a policy-first internship discovery and application assistant. This repository currently contains the foundation, Phase 1 UI, Phase 2 persistence APIs, and Phase 3 secure resume processing—not job-site automation or AI workflows.

## Safety guarantees

- Every source declares `source_name`, discovery, application, messaging, confirmation, and authorization capabilities.
- A submission is permitted only when `authorization_verified` and `application_supported` are both true.
- The deterministic policy engine controls application paths. AI modules prepare evidence-bound content only; they cannot call submitters.
- Job descriptions and external content are untrusted data, not instructions or tool input.
- Credentials, third-party passwords, resume contents, tokens, and PII must never be logged or committed.
- Master resumes are private, versioned source-of-truth records. A new upload creates a new version; it never overwrites a prior master resume.
- Tailored-resume approval is fail-closed: every persisted generated bullet is rechecked against facts extracted from the master resume and explicitly supplied candidate-profile data.

## Layout

| Directory | Purpose |
| --- | --- |
| `frontend/` | Next.js, TypeScript, Tailwind dashboard shell |
| `api/app/auth` | Identity and OAuth boundary |
| `api/app/candidate_profile`, `preferences`, `resume` | Candidate-owned data boundaries |
| `api/app/jobs`, `job_sources`, `matching` | Listing normalization, discovery and matching |
| `api/app/ai` | Safe analysis and drafting boundary |
| `api/app/applications`, `messaging` | Application and outreach flows |
| `api/app/scheduler`, `notifications` | Celery scheduling and notifications |
| `api/app/audit`, `security` | Audit trail and deterministic policy controls |

## Local development

1. Copy `.env.example` to `.env`; replace the development values.
2. Set a strong `APP_ENCRYPTION_KEY` in your environment (it must be at least 32 characters).
3. Run `docker compose up --build`. The one-shot `migrate` service applies Alembic migrations before the API starts.

For a local, non-Docker API process, start the database services first and run
`cd api && .venv/bin/alembic upgrade head` with both `DATABASE_URL` and
`APP_ENCRYPTION_KEY` configured. Resume migrations intentionally fail closed
when their encryption key is unavailable. Visit `http://localhost:3000`; API
health is at `http://localhost:8000/api/v1/health`.

For direct development:

```bash
cd api && python -m venv .venv && .venv/bin/pip install -e '.[dev]' && .venv/bin/uvicorn app.main:app --reload
cd frontend && npm install && npm run dev
```

## Checks

```bash
cd api && .venv/bin/ruff check . && .venv/bin/mypy app && .venv/bin/pytest
cd frontend && npm run lint && npm run typecheck && npm run test
```

## Resume processing

`POST /api/v1/resumes/upload` accepts one master resume as multipart field `file`.

- Only PDF and DOCX are accepted, with an exact matching extension and MIME type.
- The maximum upload size is 5 MB. The processor rejects malformed, encrypted, macro-containing, unsafe-archive, and unsafe-XML documents before private storage.
- Files are parsed as data only: no uploaded content is executed, rendered, followed, or exposed through a public storage URL.
- `PRIVATE_RESUME_STORAGE_PATH` selects the private local-volume adapter. It encrypts every file with AES-256-GCM using `APP_ENCRYPTION_KEY`, stores opaque keys internally with owner-only filesystem permissions, and never exposes the key in API responses. Parsed master-resume JSON, persisted fact text, and tailored bullets are also authenticated-encrypted in the database; fact ciphertext and integrity tags are bound to their exact user, resume, and fact IDs. API serialization decrypts them only after owner scoping. Use a strong, unique `APP_ENCRYPTION_KEY` outside local development.
- The structured master-resume schema always contains `contact`, `summary`, `education`, `experience`, `internships`, `projects`, `skills`, `certifications`, `achievements`, and `links`.

The API exposes owner-scoped fact provenance at `GET /api/v1/resumes/{resume_id}/facts`. Facts contain an ID, category, exact source text, source, and confidence. Tailored drafts persist their generated bullets and supporting fact IDs; `POST /api/v1/resumes/{resume_id}/approve` verifies the persisted bullets, rather than trusting a new approval payload.

## Phase 2 and 3 API

The API provides UUID-based CRUD routes for users, profiles, preferences, resumes, jobs, job matches, applications, and audit events. OpenAPI is available at `http://localhost:8000/api/v1/docs`.

All user-owned routes require `X-User-Id: <user UUID>` only in explicitly configured `development` or `test` environments. The service fails closed outside those environments until verified session/OAuth authentication is installed; a deployment must never enable the development header as its identity mechanism. User-owned queries are scoped at the database-query level and are covered by isolation tests.

Resumes store only an opaque internal `file_reference`; public storage URLs are rejected and the reference is not serialized in API responses. Jobs are stored as untrusted external content and no job-site adapters or application submitters are included.

## Next-stage plan

1. Replace the development identity header with verified session/OAuth authentication and a production managed private-storage adapter with encryption-at-rest and retention controls.
2. Implement only reviewed, permitted source adapters with normalized storage and idempotent de-duplication.
3. Add explainable matching plus evidence-bound tailoring and question review.
4. Build application tracking, authorized submitters, manual-open actions, and notifications.
5. Add redacted audit logs, threat-model review, Playwright UI journeys, and deployment configuration.
