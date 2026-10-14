# InternAgent Test Report

Latest verification: 2026-10-14. Authoritative results are in
`COMPLETE_TEST_REPORT.md`: 329 passed / zero failed / zero skipped. All four
original release failures are fixed with real persistence and orchestration.
Live Clerk/session and full deployment checks remain pending. `BUG_FIX_REPORT.md`
documents fixes and limits. The older review below is historical, not a current
full-product or production-readiness claim.

## Commands run

| Area | Command | Result |
| --- | --- | --- |
| Frontend lint | `npm run lint` | Passed |
| Frontend type check | `npm run typecheck` | Passed |
| Frontend tests | `npm run test` | Passed: 15 tests |
| Frontend production build | `npm run build` | Passed |
| Backend lint | `.venv/bin/ruff check .` | Passed |
| Backend type check | `.venv/bin/mypy app` | Passed |
| Backend/unit/integration tests | `.venv/bin/pytest` | Passed: 105 tests (one third-party deprecation warning) |
| Neon schema creation | `.venv/bin/alembic upgrade head` | Passed on the initially empty development database, through `20261010_0006` |
| Neon schema parity | `.venv/bin/alembic check` | Passed: no upgrade operations detected |
| Pooled Neon connection | SQLAlchemy `SELECT 1` | Passed |
| Neon plugin verification | List tables / read Alembic version | Passed: 12 tables including migration metadata |
| Compose configuration | `docker compose -f docker-compose.neon.yml config --quiet` | Passed; containers not built/run |
| Runtime dependency audit | `npm audit --omit=dev` | 0 vulnerabilities |
| Full dependency audit | `npm audit` | 9 development-tool advisories (7 high, 2 moderate), no critical |

## Clerk/Neon security coverage

Signed RSA test sessions cover invalid signatures, unsigned and wrong-algorithm
tokens, expiry, future validity, wrong issuer/origin, pending sessions, missing
session claims, user-ID-header impersonation, inactive users, stable UUID
provisioning, unsafe email linking, unverified provider email, and JWKS outages.
Browser-facing tests cover resource-level page guards, authenticated proxy
allowlists, CSRF origin checks, no forwarding of browser identities/cookies,
oversized request bodies, and safe outage errors. Source capability writes are
disabled in Clerk mode. Migration tests preserve legacy accounts/profiles and
never use a developer's private cloud URL or encryption key.

Local smoke checks: `/login` returns 200; an unconfigured `/dashboard` redirects
to `/login`; backend `/health` returns OK; unauthenticated `/users/me` returns 401;
the unconfigured frontend proxy returns 503 rather than impersonating a user.

**Not tested live:** Clerk signup/signin/signout, social login, browser refresh
or backend-restart persistence under actual Clerk identities. The application
keys/issuer remain blank. RSA test identities are not real Clerk sessions.

## Files changed for this integration

- Authentication: `api/app/auth/clerk.py`, `auth/dependencies.py`,
  `users/models.py`, `users/router.py`; frontend `middleware.ts`, `app/layout.tsx`,
  login/sign-up pages, `lib/auth-config.ts`, `lib/auth-server.ts`,
  `components/clerk-account.tsx`, and `components/app-shell.tsx`.
- Protected routes: applications, dashboard, jobs, onboarding, resumes, and
  settings retain their existing UI in `page-content.tsx`; `page.tsx` now checks sign-in.
- API bridge: `frontend/app/api/backend/[...path]/route.ts`, `lib/api.ts`,
  and `lib/request-body.ts`.
- Database/security: `api/app/config/{settings,database,connection}.py`,
  `api/alembic/env.py`, migration `20261010_0006_clerk_identity.py`,
  `api/app/resumes/models.py`, `api/app/main.py`, `api/app/security/errors.py`.
- Tests: backend `conftest.py`, Clerk authentication/migration, Neon connection,
  and database-error tests; frontend proxy, page-auth, and body-limit tests.
- Configuration/docs: environment examples, `.gitignore`, Docker ignore files,
  frontend Dockerfile, both Compose files, dependency manifests/lockfile,
  `README.md`, `ARCHITECTURE.md`, `SECURITY_REPORT.md`, and this report.

Other dirty files were already present and have not been reverted. Private
environment files contain local credentials, remain gitignored, and are not report artifacts.

## Security scenarios

| Scenario | Result | Evidence |
| --- | --- | --- |
| Below-minimum stipend | Passed | deterministic hard-filter tests |
| Wrong location | Covered by deterministic location filter; dedicated end-to-end route is not yet present | matching engine |
| Missing required skill | Passed | structured missing-skill output tests |
| Prompt injection in job text | Passed | matching/tailoring tests treat text as data only |
| Fabricated resume skill | Passed | resume fact-verification tests |
| Duplicate application | Passed | unique user/job constraint and API conflict handling |
| Daily application limit | Passed at policy-service level | submission context blocks over-limit requests |
| Restricted source | Passed | source capability/submission policy tests |
| CAPTCHA | Passed at policy-service level | CAPTCHA forces manual application status |
| Cross-user resume/application access | Passed | owner-scoped authorization isolation tests |
| Worker retry/idempotency | Passed at executor foundation level | repeated idempotency key returns stored result |
| Malicious filename / oversized upload | Passed | secure resume/request-body-limit tests |

## End-to-end journey status

The full production job-discovery-to-submission journey is intentionally not executable:
production source integrations and submitters are not implemented. Clerk authentication
is wired in but awaits provider configuration/live testing. The earlier mock UI remains;
the forms and dashboard still need authenticated API wiring. Backend upload, matching,
verified tailoring, and preparation are covered by automated foundation tests, not a
completed browser journey. No test claims that an external application was submitted.
