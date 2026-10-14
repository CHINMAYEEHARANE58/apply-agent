# InternAgent architecture

Updated2026-10-14 after release-path fixes. See COMPLETE_TEST_REPORT.md.

## Runtime modules and boundaries

Browser → Clerk → guarded Next pages → same-origin allowlisted proxy
→ bearer-only FastAPI authentication → owner-scoped services → SQLAlchemy/Postgres.

Existing Clerk, SQLAlchemy and psycopg are retained. Normal app queries use the
configured pooled TLS connection; migrations use the direct connection. QA uses
a separate disposable local database and never writes fixtures to normal Neon.

- settings: durable timezone/search/limits/source choices, synchronized with preferences.
- dashboard: real owner aggregates; authenticated manual search trigger.
- jobs/state: private save/ignore/restore and paginated candidate listings.
- scheduler/pipeline: persisted daily runs, normalization/dedup, hard filters,
  verified-fact scoring, tailored artifacts/drafts, policy review and safe audits.
- resumes: immutable master versions, encrypted facts/parsed data/artifacts,
  factual approval and authenticated private attachment downloads.
- applications: private tracker and atomic package approval using stored
  references and current server-recomputed matches.

## Daily data flow

Preferences + latest locked master facts + stored permitted catalogue
→ normalize/deduplicate/persist original URLs
→ deterministic hard filters
→ score verified facts against untrusted listing data
→ threshold and persisted preparation quota
→ verified tailored HTML/PDF and source-supported writing
→ deterministic policy check
→ awaiting user review
→ durable audit summary.

A PostgreSQL user-row transaction lock spans preparation. A unique user/local-
date run record and unique user/job application enforce restart/retry safety.
Celery handles bounded temporary retries; authorization failures are not retried.
Beat checks per-user timezones. Actual delivery/outbox/multi-host recovery is
not certified by native QA.

## Security

Descriptions, websites, email text, questions and uploaded content remain data,
never instructions/tool authority. No model gets shell, SQL, arbitrary URL,
secret or submission tools. Desired technologies are not verified skills.
Ordinary users cannot alter shared catalogue listings or source authorization.

Private bytes/facts/artifacts use authenticated encryption with environment-
supplied key material. Production middleware uses Redis-shared atomic limits,
fails closed on Redis failure and requires HTTPS. Cookie-proxy mutations require
exact-origin checks; backend receives verified bearer tokens, not browser cookies.
Outputs are encoded, requests bounded and user IDs derived from authentication.

## Limits before deployment

No live source fetcher, LLM provider, email sender or authorized submission client
is configured. Catalogue discovery is real DB work, not live website search.
All new packages remain for review/manual handoff, including authorized-auto mode.
Successful external submission/idempotency/quota reservation still needs a
reviewed integration; current application metadata is not a provider receipt.

Live Clerk lifecycle/cookie testing, Docker builds, secret-manager/key rotation,
future OAuth envelope encryption, object-storage signed links, export/retention/
atomic deletion and comprehensive PDF/UI verification remain deployment work.
Migration0007 is tested locally but has not modified the existing Neon database.
