# InternAgent

## Release-path repair status (2026-10-14)

Persistent dashboard/settings/saved-job APIs and the stored-catalogue daily
pipeline are implemented; screens now use the authenticated backend. The latest
clean run passes 284 backend, 33 frontend and 12 browser checks (329 total).
See [COMPLETE_TEST_REPORT.md](COMPLETE_TEST_REPORT.md) for scope and unverified
requirements, and [BUG_FIX_REPORT.md](BUG_FIX_REPORT.md) for fixes.

Migration `20261014_0007` adds scheduler state/limits, discovery metadata and
timestamps. It has been tested on disposable PostgreSQL but has not changed
your normal Neon database; review/apply it to the intended deployment before
using these endpoints there. Historical cadence remains unknown rather than
invented. Existing master versions and user choices are preserved.

Discovery currently processes legitimately imported catalogue records. It does
not fetch job websites. Strong matches become fact-checked drafts awaiting user
review; all external submissions remain disabled, including authorized-auto
mode until a reviewed integration exists. Summaries are stored, not emailed.
Production API limits now require shared Redis and fail closed on Redis failure.

Live Clerk, Docker/deployment, managed secrets and remaining dev-tool advisories
still prevent a production-ready claim. Configure dedicated test keys privately
in `.env.qa` using [QA_RUNBOOK.md](QA_RUNBOOK.md); never paste secrets into chat.

InternAgent is a policy-first internship discovery and application assistant. This repository currently contains the foundation, Phase 1 UI, Phase 2 persistence APIs, Phase 3 secure resume processing, and safe Phase 4–7 service foundations—not job-site automation or application-submission integrations.

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

1. Copy `.env.example` to `.env` only if one does not already exist; replace the placeholders. Keep both it and `frontend/.env.local` private and gitignored.
2. Set a strong `APP_ENCRYPTION_KEY` in your environment (it must be at least 32 characters).
3. For local PostgreSQL run `docker compose up --build`. For Neon run
   `docker compose -f docker-compose.neon.yml up --build`, or use the
   direct-development instructions below. The one-shot `migrate` service applies Alembic migrations before the API starts.

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

## Clerk sign-in + Neon PostgreSQL

The Neon plugin provisioned an **InternAgent** project (`jolly-dew-33263772`),
`development` branch (`br-dark-butterfly-b3xxl18k`), and `internagent` database
in Singapore. Its credentials are in the private root `.env`, not source code.
`DATABASE_URL` uses the pooled host; `DATABASE_DIRECT_URL` uses the direct host
for Alembic. Both require TLS. SQLAlchemy uses psycopg with connection health checks.
There is no browser-facing database connection or Neon Data API.

Clerk manages passwords, sign-up, sign-in, OAuth providers, and account sessions.
InternAgent does not handle or store Clerk passwords. Enable the desired email
and social sign-in options in your Clerk application's dashboard.

1. Create/select a Clerk app and obtain its keys from **API Keys**.
2. In `frontend/.env.local` (template: `frontend/.env.example`), set
   `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` and `CLERK_SECRET_KEY` from that same app.
3. In the root `.env`, set `CLERK_SECRET_KEY` and `CLERK_ISSUER` to that app's
   exact HTTPS Frontend API URL / JWT issuer (no path). Set
   `CLERK_AUTHORIZED_PARTIES=["http://localhost:3000"]` for development; use only
   trusted HTTPS frontend origins in production. Optionally supply a PEM
   **public** key in `CLERK_JWT_KEY`; otherwise the backend uses the pinned issuer's JWKS.
4. Keep `AUTH_PROVIDER=clerk`. For Docker also put the publishable key in the
   root `.env` so Compose can pass it as a build argument (secrets are runtime-only).
   From `api/`, run `.venv/bin/alembic upgrade head`,
   then `.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`.
   From `frontend/`, run `npm run dev`. Restart/rebuild after changing Clerk keys.
5. Visit `/sign-up` or `/login`. A verified primary email is required. The first
   authenticated `/users/me` call creates a stable local UUID bound to the Clerk
   subject; the dashboard performs that synchronization and shows connection errors.

Each protected page checks sign-in at the server resource (not only via middleware),
following [Clerk's resource protection guide](https://clerk.com/docs/guides/development/upgrading/upgrade-guides/migrate-from-create-route-matcher).
The Next.js proxy `/api/backend/*` retrieves the Clerk bearer token server-side,
checks mutation origins, limits upload buffering, and forwards only allowlisted
API paths. The FastAPI backend verifies RS256 signatures, issuer, expiry, active
session claims, and authorized party independently before querying owner-scoped
records. Browser-supplied UUIDs and emails cannot override the Clerk identity.
Existing local email accounts are **not** automatically linked; they require an
explicit authenticated account-migration process.

Without Clerk configuration, public login/sign-up pages show a setup notice,
protected pages redirect to login, and the API refuses unauthenticated access.
Never put secret keys, database credentials, or encryption keys in `NEXT_PUBLIC_*`.
Production must inject secrets through its secret manager and back up the resume
encryption key; replacing that key makes existing encrypted resumes unreadable.

**Remaining integration work:** onboarding and the jobs/applications/resumes/settings
screens still use the earlier mocked UI data. Authenticated backend CRUD is persistent,
but these screens must be wired to `apiFetch` before claiming end-to-end UI persistence.
The local resume adapter remains encrypted private filesystem storage, not cloud storage.

## Checks

For the complete isolated QA pass (PostgreSQL, Redis worker, browser tests,
coverage, and known release-contract failures), follow [QA_RUNBOOK.md](QA_RUNBOOK.md).
The full backend suite now needs dedicated `TEST_DATABASE_URL` and
`TEST_REDIS_URL` services; it deliberately fails rather than using a developer's cloud database.

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

All user-owned routes use verified Clerk bearer sessions by default. The legacy
`X-User-Id: <user UUID>` path is accepted only with **both** `AUTH_PROVIDER=development`
and `APP_ENVIRONMENT=development|test`; it is rejected in Clerk mode and in production.
User-owned queries are scoped at the database-query level and covered by isolation tests.

Resumes store only an opaque internal `file_reference`; public storage URLs are rejected and the reference is not serialized in API responses. Jobs are stored as untrusted external content. Only in-memory/mock discovery adapters are included; no job-site browser automation, scraper, credential store, or application submitter is present.

## Discovery, matching, and application-draft foundations

- `app.job_sources.adapters.JobSourceAdapter` is the required four-method contract for future reviewed sources: `search_jobs`, `get_job`, `normalize_job`, and `get_capabilities`. The included development adapters are in-memory mocks only.
- LinkedIn, Indeed, Glassdoor, and Naukri adapters are deliberately link/manual-discovery adapters. They do not drive a browser, scrape, log in, evade protections, or claim application permission.
- `NormalizedJob` is the common listing contract. `JobDeduplicator` uses normalized company, title, location, and conservative description similarity; its output carries every original source URL for persistence by a later repository adapter.
- `app.matching.engine` first enforces hard filters and only then calculates a deterministic 0–100 score. Description text is tokenized as untrusted data and cannot influence policies, permissions, tools, or submission.
- `app.ai.tailoring` produces a local HTML/PDF preview only after fact-cited bullets pass `verify_tailored_resume`. Low-scoring jobs stop before tailoring; unverifiable output is `REQUIRES_REVIEW`.
- `app.ai.application_writing` prepares reviewable cover-letter, recruiter-message, and introduction drafts only. It has no send client. A future sender must separately require a verified messaging capability, a user messaging opt-in, and deduplication.

## Next-stage plan

1. Configure the Clerk app keys, connect mocked screens to the authenticated API, and add a production managed private-storage adapter with retention controls.
2. Persist normalized source URLs and idempotent de-duplication results, then add only reviewed, permitted production discovery adapters.
3. Add authenticated API/UI flows for matching, tailored-resume review, and application-writing drafts.
4. Build application tracking, authorized submitters, manual-open actions, messaging consent, and notifications.
5. Add redacted audit logs, threat-model review, Playwright UI journeys, and deployment configuration.
