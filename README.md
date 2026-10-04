# InternAgent

InternAgent is a policy-first internship discovery and application assistant. This repository currently contains the **foundation**, not a finished product: a typed API boundary, source-capability registry, deterministic submission policy, dashboard shell, containerized local services, and tests.

## Safety guarantees

- Every source declares `source_name`, discovery, application, messaging, confirmation, and authorization capabilities.
- A submission is permitted only when `authorization_verified` and `application_supported` are both true.
- The deterministic policy engine controls application paths. AI modules prepare evidence-bound content only; they cannot call submitters.
- Job descriptions and external content are untrusted data, not instructions or tool input.
- Credentials, third-party passwords, resume contents, tokens, and PII must never be logged or committed.

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
2. Run `docker compose up --build`.
3. Visit `http://localhost:3000`; API health is at `http://localhost:8000/api/v1/health`.

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

## Next-stage plan

1. Persist authenticated profiles, preferences, and encrypted resumes with migrations.
2. Implement only reviewed, permitted source adapters with normalized storage and idempotent de-duplication.
3. Add explainable matching plus evidence-bound tailoring and question review.
4. Build application tracking, authorized submitters, manual-open actions, and notifications.
5. Add OAuth, redacted audit logs, threat-model review, Playwright UI journeys, and deployment configuration.
