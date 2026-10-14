# Isolated QA environment

Use only disposable local services. Do not use the root `.env` / Neon URL for
test migrations or fixture writes. No email, recruiter-message, LLM, or external
application integration is enabled by this suite. Browser tests block all
non-local requests. They do not operate Clerk or job websites.

Prerequisites: Node 24+, Python 3.12+, PostgreSQL 16 tools, Redis, installed
`api/.[dev]` and `frontend` dependencies, `npx playwright install chromium`.

Create a dedicated directory with `mktemp -d /private/tmp/internagent-qa.XXXXXX`.
Use its exact returned path as `<QA_DIR>` below (not a home/workspace root):

```sh
initdb -D <QA_DIR>/postgres --username=qa --auth-local=trust --auth-host=trust --encoding=UTF8 --locale=C
pg_ctl -D <QA_DIR>/postgres -l <QA_DIR>/postgres.log -o '-h 127.0.0.1 -p 55432 -k <QA_DIR>' start
createdb -h 127.0.0.1 -p 55432 -U qa internagent_test_utf8
redis-server --bind 127.0.0.1 --port 56379 --dir <QA_DIR> --save '' --appendonly no
```

Trust authentication is acceptable **only** for this disposable loopback-bound
test database. Never copy this authentication configuration to a deployment.

In a QA-only shell, override configuration explicitly before migration/server commands:

```sh
export APP_ENVIRONMENT=test AUTH_PROVIDER=development
export DATABASE_URL=postgresql+psycopg://qa@127.0.0.1:55432/internagent_test_utf8
export DATABASE_DIRECT_URL=$DATABASE_URL TEST_DATABASE_URL=$DATABASE_URL
export REDIS_URL=redis://127.0.0.1:56379/0 TEST_REDIS_URL=redis://127.0.0.1:56379/0
export APP_ENCRYPTION_KEY=test-only-qa-encryption-key-with-at-least-32-chars
export CLERK_SECRET_KEY= CLERK_ISSUER= CLERK_JWT_KEY=
export PRIVATE_RESUME_STORAGE_PATH=<QA_DIR>/private-resumes
cd api
.venv/bin/alembic upgrade head
.venv/bin/alembic check
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8100 --no-access-log
# Separate terminal with the same QA environment:
.venv/bin/celery -A app.scheduler.celery_app worker --pool=solo --concurrency=1 --queues=internagent-qa --loglevel=WARNING
```

The test bootstrap disables dotenv and supplies test-only credentials. PostgreSQL
tests additionally require a loopback host and `internagent_test*` database name.
They use savepoint rollback or delete only their exact fixture UUIDs. The HTTP
restart test starts its own backend on 8123 and terminates only that process.

## Complete checks (run sequentially where build/typecheck share `.next`)

```sh
cd api
.venv/bin/ruff check .
.venv/bin/mypy app
.venv/bin/pytest --cov=app --cov-report=term --cov-report=html:../qa-artifacts/backend-coverage --cov-report=json:../qa-artifacts/backend-coverage.json --junitxml=../qa-artifacts/backend.xml
cd ../frontend
npm run lint
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY= CLERK_SECRET_KEY= INTERNAGENT_API_URL=http://127.0.0.1:8100/api/v1 npm run build
npm run typecheck
npm run test:coverage
npm run test:e2e
cd ..
api/.venv/bin/python scripts/scan_secrets.py
```

The four original release contracts now pass with persistent dashboard/settings/
saved-job APIs and the actual stored-catalogue pipeline. They were not skipped,
expected-failure-marked or relaxed. New pipeline, PostgreSQL concurrency, shared
Redis-rate and HTTP restart tests prove persistence and preparation safety.
Component tests prove UI/API wiring, not live Clerk persistence. Playwright still
covers signed-out security and login responsiveness, not full authenticated
signup-to-submission journeys. Live Clerk requires a separate **test** instance.

The current migration head is 20261014_0007. Apply migrations only against your
intended deployment connection after reviewing them; QA does not migrate normal
Neon data. Production now requires shared Redis for protected requests and fails
closed when Redis is unavailable. Stored catalogue discovery never fetches job
websites; summaries are recorded, not sent by an email provider.

## Optional live Clerk session checks

The private `.env.qa` template is ignored by Git. Supply only `pk_test_` /
`sk_test_` keys and the matching issuer there. Keep the database and API targets
on the disposable local ports shown in `.env.qa.example`. Create two new,
verified fixture users in that Clerk **test** application with distinct email
addresses containing `+clerk_test@`; set `QA_CLERK_USER_A/B` privately.

Run `api/.venv/bin/python scripts/run_clerk_qa.py`. This runner rebuilds Next
with test public configuration, starts a separate API on 8110, uses Clerk's
official ticket-based testing helper, and tests session reload/logout/relogin,
real token verification/proxying and two-user profile isolation. It does not
prove UI signup/password/reset flows. No traces, screenshots, passwords or
session storage files are retained. It deletes only the local fixture profile;
the Clerk test users remain for reuse. Stop any existing server on 3100 first.
Missing test configuration is a failure to run, never a passing or skipped test.

Docker Compose configuration can be validated with `config --quiet`, avoiding
printing resolved secrets. Image builds require a running Docker daemon, which
was unavailable during this QA run. Production-mode startup was separately
verified against the local test database: HTTP is rejected and HTTPS-origin
requests still require a Clerk session.

After testing, stop only the QA-owned processes and the PostgreSQL cluster at
the exact `<QA_DIR>/postgres` path. Do not delete or reset the Neon database.
