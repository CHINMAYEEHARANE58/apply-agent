# InternAgent security report

Verified2026-10-14 against an isolated local environment. No normal Neon fixture writes.

## Decision

**Not production-ready.** All executed tests pass (329 total;65 focused backend
security cases overlap that total), but live identity, deployment and remaining
operational prerequisites are not certified. COMPLETE_TEST_REPORT.md and
BUG_FIX_REPORT.md are the authoritative evidence.

## Implemented and tested controls

- Clerk JWT signature/issuer/expiry/session/authorized-party and verified-email
  checks; development identity never enabled by a missing production setting.
- Owner-scoped private data, strict input models, SQL bind parameters, generic
  errors, encoded outputs, CORS and exact-origin cookie-proxy mutation checks.
- Production HTTPS/HSTS guard. Native smoke: plaintext400; forwarded HTTPS
  health200+HSTS and unauthenticated identity401. This is not real TLS deployment.
- Production Redis-shared atomic request quotas/TTL, fail closed on Redis outage.
  Development fallback is bounded; shared behavior tested against actual Redis.
- Private encrypted resume bytes/facts/parsed data/rendered artifacts, immutable
  historical master sources and source-backed verification/approval.
- Authenticated no-store exports with attachment headers and exact owner
  namespace validation; unapproved/unverifiable tailored exports blocked.
- Server-recomputed package approval; PostgreSQL row locks and unique daily/
  application records prevent duplicated preparation across concurrent sessions
  and restarts. Preparation limits use persisted records.
- Untrusted job descriptions cannot invoke tools, read secrets, modify candidate
  preferences or grant permissions. Desired skills cannot become verified
  qualifications. Fabrication and injection matrices pass.
- No application submission or messaging network client exists. Catalogue
  discovery reads imported data and does not operate restricted websites.
  Unknown sensitive questions remain unresolved for manual review.
- Source/browser-bundle credential scans found no secret values. Backend and
  frontend runtime dependency audits reported no known advisories.

## Severity findings

| Severity | Finding | Status |
| --- | --- | --- |
| High | Original dashboard/settings/saved-job/daily pipeline failures | FIXED with real persistence/orchestration and regression tests |
| High | Process-local production rate limit and preparation lock | FIXED: shared Redis quota and transactional PostgreSQL lock/run record |
| High | Preferred skills promoted into qualifications/shared catalog write bypass | FIXED: verified-fact skill gates and server-only catalog mutations |
| High | Seven frontend dev-tree dependency advisories | OPEN: unpatched braces and propagated Tailwind/lint dependencies; runtime audit clean |
| High deployment prerequisite | Live Clerk lifecycle/cookie verification | PENDING dedicated test keys/users; .env.qa remains blank |
| High deployment prerequisite | Managed secrets/key rotation and future OAuth envelope encryption | OPEN; current local configuration uses environment key material, no OAuth credential store |
| High integration prerequisite | Durable successful-submission idempotency/atomic external submission quotas | NOT IMPLEMENTED; no submitter may be enabled yet; preparation safety is not a provider receipt |
| Medium | Two frontend dev-tree advisories | OPEN |
| Medium | Audit retention, personal-data export and atomic filesystem/DB deletion workflow | OPEN; account deletion cleans owned files but cannot provide atomic storage/DB guarantees |
| Medium | Object-storage signed links and production storage/delivery/outbox recovery | OPEN; current downloads are authenticated private streams, not public storage URLs |
| Medium | Full PDF visual/Unicode/long-text and authenticated UI coverage | PARTIAL; API content/export gates and selected components tested |
| Low | Test transport deprecation and Docker verification | OPEN; daemon unavailable, native Python3.13 is not Docker/Python3.12 certification |

No current executed critical authorization/fabrication gate fails. This is not
a claim of zero high production risks or externally verified candidate credentials.

## Required operations

Review/apply migration0007 to the intended deployment; QA has not changed normal
Neon data. Keep secrets gitignored/private, use managed secret delivery and
encrypted managed database/storage with least-privilege roles. Use a trusted TLS
proxy and explicit origins; protect Redis/broker access. Resume app-level
encryption is not a full per-record envelope-key service for future credentials.

Do not log tokens, passwords, resume text, phone/email contents or sensitive
answers. Current pipeline failure events store safe codes/counters, not raw
provider/source exception messages. Never store third-party passwords.

Configure a dedicated Clerk test app privately using QA_RUNBOOK.md. Verify
signup/password/cookies/logout/session restoration and actual authenticated
browser journeys before release. Do not enable OAuth, messaging or application
submission until authorized integrations and deterministic durable safeguards
are reviewed and tested.
