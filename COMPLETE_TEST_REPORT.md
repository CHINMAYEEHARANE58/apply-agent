# InternAgent QA report — release-path fixes

Date: 2026-10-14 (Asia/Calcutta). Supersedes the earlier 299-pass / 4-failure report.

## Result

**All executed tests pass: 329 passed, 0 failed, 0 skipped.**
The four originally failing release contracts are fixed, without deleting,
skipping, xfail-marking or relaxing their assertions. Full production release
readiness remains **PARTIAL**, not certified: live Clerk lifecycle tests,
authenticated browser journeys, deployment checks and integration prerequisites
below remain outstanding.

## Final clean run and counts

The disposable local PostgreSQL database was recreated and migrated from empty
through all seven revisions; Redis restarted; fresh native API and Celery worker
processes started. The complete pytest, Vitest and Playwright suites ran against
that environment. No Neon fixture writes, real applications, emails, recruiter
messages, LLM requests or restricted job-site automation occurred.

| Category | Passed | Failed | Skipped |
| --- | ---: | ---: | ---: |
| Backend unit | 168 | 0 | 0 |
| Backend integration/API/database/migrations/worker | 116 | 0 | 0 |
| Frontend Vitest | 33 | 0 | 0 |
| Playwright own-app security smoke | 12 | 0 | 0 |
| **Non-overlapping total** | **329** | **0** | **0** |
| Focused backend security subset, already included | 65 | 0 | 0 |

Integration classification includes TestClient/database fixtures, migrations,
HTTP restart, actual Redis-worker dispatch and actual shared-Redis limits.
Unit tests are the remainder. The security subset comprises authorization,
Clerk JWT, secure resume, fact verification, submission policy, transport,
body/rate limits, DB error and shared-rate test files; additional matrix cases
cover injection/fabrication and are not counted twice.

Counts come from qa-artifacts/backend.xml, qa-artifacts/frontend.json and
frontend/test-results/e2e-results.json. Two optional live Clerk setup/session
cases exist but were **not run** because .env.qa test keys remain blank. They are
not counted as passing or skipped.

## Commands actually run

| Check | Outcome |
| --- | --- |
| ruff check api scripts | PASS |
| mypy api/app | PASS, 91 source files |
| Complete pytest with coverage/JUnit | PASS, 284 tests |
| Fresh PostgreSQL alembic upgrade head | PASS, through 20261014_0007 |
| alembic check | PASS, no schema drift |
| pip check / pip-audit --local | PASS / no known advisories |
| Frontend lint / production build / subsequent typecheck | PASS |
| Vitest coverage | PASS, 33 tests |
| Playwright | PASS, 12 tests, no retries/skips/flaky results |
| npm audit --omit=dev | PASS, zero runtime advisories |
| Full npm audit | FAIL: 7 high / 2 moderate development-tree advisories |
| Source and built-browser secret scan | PASS, no findings |
| Both Docker Compose config --quiet | PASS, resolved secrets not printed |
| Docker image builds | NOT VERIFIED: daemon socket unavailable |
| Native production-mode API and beat startup | PASS startup; plaintext400, forwarded HTTPS health200+HSTS, unauthenticated401; not deployed TLS/identity certification |

Backend app statement coverage: **90.67%**. Frontend configured scope:
statements **64.00%**, branches **64.98%**, functions **50.00%**, lines **69.11%**.
Resumes/account-shell UI and complete authenticated responsive journeys still
have coverage gaps. A Starlette httpx TestClient deprecation warning remains.

## Architecture

Next.js15.5.27/React19/TypeScript/Tailwind3, Clerk server page guards and same-origin
allowlisted proxy; FastAPI/Pydantic, SQLAlchemy/psycopg, PostgreSQL, Alembic,
Redis/Celery. Existing Clerk/ORM choices were preserved, following the Neon
database skill's isolated/direct-migration guidance. QA used PostgreSQL16.13 on
127.0.0.1:55432 and Redis8.6.1 on127.0.0.1:56379, never the normal Neon connection.

Resumes and facts are privately encrypted; master history is immutable.
Generation is deterministic and source-backed, not a configured LLM provider.
The initial real discovery adapter reads already-imported catalogue records.
It performs no remote fetch, browser automation, scraping or external submission.

## Original four failures — now fixed

| Contract | Implementation and verified result |
| --- | --- |
| GET /dashboard | Owner-scoped SQL aggregates; zero and populated data; live UI counts |
| GET/PUT/PATCH /settings/me | Validated durable settings, timezone/limits/source selection; shared preference values synchronized |
| PATCH/GET /jobs/{id}/state; GET /jobs/mine | Private save/ignore/restore state; persistence, pagination and user isolation |
| daily_internship_search | Real preference/source/normalize/dedup/filter/match/tailor/write/policy/review/audit/summary pipeline |

The daily run has a unique user/local-date key. A PostgreSQL user-row lock
serializes browser requests and workers. Four concurrent independent SQL
sessions prepare exactly one package; retries in new sessions prepare none.
Preparation limits are counted from persisted applications, not caller flags.
Failures roll back partial work, record sanitized failure counts and stop after
four attempts. Temporary failures have bounded Celery retries; authorization
failures are not retried. Timezone-specific due dispatch has a separate test.

## Authentication

PASS: JWT signing/issuer/expiry/session/authorized-party checks, verified-email
provisioning, no silent linking, development-header bypass rejection, protected
APIs and signed-out page redirects. Development signup validation is not a
claim of live Clerk signup.

NOT VERIFIED: actual Clerk signup/password/reset, real browser cookies,
expiration/revocation and reload/logout/relogin. Passwords remain with Clerk;
no invented local password implementation or production credentials were used.
The opt-in official ticket-based session harness is documented in QA_RUNBOOK.md;
it does not test password UI/signup and retains no auth traces or passwords.

## Authorization

PASS: two-user profile/preferences/resume/facts/application isolation, private
settings and saved-job state, protected downloads and approval, foreign404s.
Shared catalog mutations remain forbidden to ordinary Clerk users. User IDs
come from authentication, never mass-assigned request fields.

## Profiles

PASS API: validation/upsert/read and real HTTP restart persistence. Onboarding
now sends an explicit full name and relocation preference; it preserves existing
profile fields instead of manufacturing legal/personal answers. Full
authenticated browser profile/logout-login persistence remains unverified.

## Preferences

PASS API: ranges, enums, URLs, limits and persistence. Onboarding now writes the
selected values and uploads the selected resume before navigating. Hourly/
monthly cadence is persisted when supplied; migration preserves unknown for
historical records. New default submitted limit is10/day; existing choices are
not overwritten. Settings and preference edits synchronize shared controls.

## Database

PASS: seven fresh PostgreSQL migrations, model/schema parity, legacy encryption
backfills, ownership/unique/FK constraints, immutable master/fact triggers,
concurrent application uniqueness, durable daily runs and backend restart.
The concurrency fixture follows the real upload lifecycle: insert facts while
the master is unlocked, then lock in the same transaction. DB protections were
not weakened. Migration0007 is tested locally, not applied to normal Neon data.

## Resumes

PASS: PDF/DOCX validation, malformed/empty/disguised/oversized uploads, traversal
filenames, random private objects, encryption/integrity, version preservation,
fact verification and approval. Added authenticated no-store downloads with
fixed attachment filenames; draft/unverifiable tailored exports are blocked.
Namespace traversal is rejected even for a tampered internal reference.

The HTTP journey prepares and approves a package and downloads an actual PDF.
This establishes private export and source-backed content gates, not complete
PDF visual/Unicode/long-text formatting or independent credential verification.
Short-lived object-storage signed links remain a future deployment feature.

## AI

PASS deterministic matching/tailoring/writing and fabrication/injection tests.
Desired technologies no longer count as verified qualifications; related names
such as C/C++, Java/JavaScript and SQL/NoSQL do not manufacture missing skills.
Only sufficiently confident resume/project/experience facts support skill
claims. Fact consistency is checked against supplied sources, not independently
against the real world. No provider model or model tool bridge was exercised.

## Jobs

PASS: all existing fixture/manual adapters, normalization, reasonable dedup
with persisted source URLs, hard filters and scored gaps. The real catalogue
adapter consumes stored data without operating job websites. Users can disable
it but cannot grant source permissions through settings or job content.
Live job API/RSS/email integrations remain unconfigured.

## Applications

PASS: private CRUD, references/status dates, duplicate records, drafting,
sensitive-answer review, policy denials, populated pipeline persistence and
atomic package approval. Approval verifies the stored resume reference and
rechecks current hard filters/score before committing. The user-approved audit
event explicitly records no external submission. UI offers manual Open
Application handoff, not automatic website operation.

Required form questions are not imported from platforms. Unknown sensitive
answers remain unresolved and block automatic submission. No official
submission client exists, so successful external submissions and subsequent
worker retry/durable provider idempotency are **NOT VERIFIED**. Manual tracker
metadata is not an authorized-API receipt.

## Scheduler

PASS: registration/worker/beat startup, actual Redis task transport, per-user
timezone due selection, disabled/completed suppression, persisted pipeline,
cross-connection serialization, counters, safe failure persistence and bounded
retries. Summaries are stored as audit data, not sent by a real email provider.
Queue/outbox recovery, multi-host deployment and provider outage delivery
guarantees remain unverified.

## Security

PASS executed controls: signed JWT boundaries, IDOR checks, SQL bind parameters,
output encoding, CORS/proxy CSRF guards, streaming limits, encrypted private
uploads, factual gates and source/CAPTCHA/limit policy denials. Production limits
now share atomic Redis counters/TTL across middleware instances and fail closed
on Redis failure; development retains a bounded local limiter.

Release blockers remain: dev-tool advisories; managed secrets/key rotation;
future OAuth envelope encryption; real provider integration/idempotency/quota
reservations; export/audit-retention/atomic deletion workflow and deployment
verification. There are no source-code credential findings or known runtime
dependency advisories in the executed scans. No zero-high/production-ready claim.

## Frontend

Production screens no longer import demo datasets. Dashboard/search, jobs,
settings, onboarding, resume upload/review/export and application review use the
authenticated proxy. Errors do not become invented success/counts; save failures
retain prior state. Seven new component cases prove wiring/payloads and approval
does not call a submission endpoint. These are component tests with API
fixtures, not live-provider or full browser persistence results.

## API

PASS: validation, authentication, ownership, pagination, safe errors, body/rate
bounds, new owner APIs and atomic approval. Worker exceptions record safe codes
rather than raw source/provider messages. Resume downloads expose no filesystem
path or raw storage URL. Dashboard counts use real owner records.

## E2E and remaining verification

| Flow | Outcome |
| --- | --- |
| Profile/preferences/master resume/settings/saved-job persistence | PASS API and actual HTTP restart |
| Discovery to strong match to fact-checked draft to user approval to prepared package/PDF | PASS API with controlled stored listings |
| Wrong stipend/location; missing skill; malicious description; fabricated qualification | PASS tested components/pipeline |
| Duplicate prepared application and concurrent daily execution | PASS PostgreSQL |
| Actual fourth preparation beyond configured3/day | BLOCKED in real persisted pipeline |
| Fourth external submission; successful external worker retry | NOT VERIFIED, no authorized submitter configured |
| CAPTCHA/restricted-source submission | BLOCKED by policy; no external browser automation performed |
| Signup/login/session/logout-relogin | NOT VERIFIED, dedicated Clerk keys absent |
| Full authenticated 25-step/two-user Playwright journeys | NOT VERIFIED; cannot replace Clerk with fake production auth |
| Signed-out protection and login375/768/1440px | PASS,12 Playwright checks |
| Full responsive/account/empty/loading/PDF visual coverage | PARTIAL |

## Artifacts and changed files

Generated artifacts: qa-artifacts/backend.xml, backend HTML/JSON coverage,
frontend JSON, frontend/coverage, browser JSON and dependency audits. They are
gitignored. Full change details and remaining severity findings are in
BUG_FIX_REPORT.md; exact reproduction steps are in QA_RUNBOOK.md.

New implementation modules: app/settings (schemas/service/router), app/dashboard,
app/jobs/state.py, app/job_sources/catalog.py, app/scheduler/pipeline.py and
run_models.py; migration20261014_0007_daily_pipeline.py; frontend/lib/resources.ts
and components/resource-notice.tsx.

New tests from this fix: api/tests/test_persistent_release_paths.py,
test_shared_rate_limit.py, test_due_scheduler.py,
api/tests/integration/test_daily_concurrency.py and
frontend/tests/persistent-screens.test.tsx. Existing tests were retained.

Updated: ORM models/preferences/profile/resume/application/scheduler/security/
main modules; frontend dashboard/jobs/settings/onboarding/resumes/applications/
job-card/types; fixtures, HTTP restart and migration-head assertions; docs.
Earlier QA test additions and safe Clerk/secret-scan harnesses remain present.

## Verdict

**Implemented test suite passing; full release review incomplete.**
Do not enable automatic submissions or declare production readiness from these
results. Live Clerk, deployment and integration prerequisites still need review.
