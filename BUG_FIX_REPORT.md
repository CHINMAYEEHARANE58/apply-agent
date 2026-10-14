# InternAgent bug fixes and open findings

Date: 2026-10-14. Latest clean run: **329 passed / zero failed / zero skipped**.
See `COMPLETE_TEST_REPORT.md` for limits, counts, architecture and file inventory.
No production-ready claim is made.

## Fixed issues

| Issue / severity | Root cause | Fix and modified files | Test proving fix |
| --- | --- | --- | --- |
| High: ordinary Clerk user could alter/delete shared jobs | Identity check without catalog-write authority | Authenticate reads; deny Clerk user writes before lookup. `api/app/jobs/router.py` | `test_jobs_api_requires_authentication`; `test_clerk_users_cannot_mutate_the_shared_job_catalog` |
| High: preferred skills became invented qualifications | Drafts trusted match skills, not verified facts | Require confident skill evidence. `api/app/ai/application_writing.py` | `test_preferred_skills_cannot_become_unverified_candidate_claims` |
| High: private resume files survived account deletion | DB cascades did not clean filesystem | Validate owner paths, cascade historical lineages, remove exact owned objects, safe storage errors. `api/app/users/router.py`, `api/app/resumes/storage.py` | `test_account_deletion_removes_only_owners_private_objects`; real-PG `test_account_deletion_cascades_historical_resumes_and_private_files` |
| High: multiple mandatory eligibility clauses passed if one matched | `any` and case-sensitive prefix | Require all explicit clauses; normalize prefix, trim exclusions. `api/app/matching/engine.py` | `test_each_mandatory_filter_cannot_be_overridden`; `test_eligibility_prefix_is_case_insensitive` |
| High: vulnerable crypto/test dependencies | Old dependency caps | Require cryptography>=50.0.2,<51 and pytest>=9.0.3,<10; local pip26.2.1; coverage/audit tools. `api/pyproject.toml` | Full encryption/JWT/parser suite after upgrade; final pip audit clean; pip check passes |
| Medium: static sensitive answers lost; language mistaken for age | Canonical underscores/hyphens and substring matching | Normalize keys, recognize work/location/start/notice queries, word boundaries. `api/app/applications/questions.py` | Five canonical-answer cases, language case, eight unknown-sensitive review cases |
| Medium: draft falsely said application already sent | Unconditional template claim | Truthful invitation instead of submitted claim. `api/app/ai/application_writing.py` | `test_recruiter_drafts_do_not_claim_an_application_was_submitted` |
| Medium: repeated recruiter contact across jobs | Dedup keyed by job too | Per-user normalized recruiter dedup; blank recipients denied. `api/app/ai/application_writing.py` | `test_same_recruiter_is_not_contacted_again_for_another_job` |
| Medium: interview transition rejected valid submission date; invalid patches committed | Date allowed only at submitted; partial updates not merged/validated | Validate full proposed state before commit, support post-submission outcomes, reject null status. `api/app/applications/router.py`, `schemas.py` | Interview regression; `test_inconsistent_status_updates_are_rejected_before_commit` |
| Medium: privilege-bearing extra fields silently ignored | Non-strict shared schema | `extra=forbid`. `api/app/config/schemas.py` | `test_invalid_or_privilege_bearing_signup_bodies` |
| Medium: generic JSON bodies unbounded | Only upload route capped | Streaming 1MiB non-upload cap, preserve 5MiB file envelope. `api/app/main.py`, `api/app/security/request_limits.py` | `test_json_body_limit_rejects_oversized_input`; existing upload/proxy bounds |
| Medium: limiter memory unbounded | Idle unique-client buckets retained | Expire buckets, cap cardinality, safe429. `api/app/security/http.py` | `test_rate_limiter_cannot_grow_without_bound_for_new_clients`; normal/over-limit API test |
| Medium: null required fields corrupted response state | Patch optional types allowed explicit null | Null validators and safe response-validation errors. `api/app/jobs/schemas_v2.py`, `api/app/security/errors.py`, `api/app/main.py` | Required-match/null-status/job-skills matrix |
| Medium: filesystem failure leaked raw upload failure | OSError uncaught | Safe503 and no created record. `api/app/resumes/router.py` | `test_storage_failure_is_safe_and_creates_no_record` |
| Medium: punctuation/empty-term duplicates survived | Identity punctuation and similarity-only comparison | Canonical terms, exact fingerprint short circuit, retain source URLs. `api/app/jobs/discovery.py` | Both duplicate tests in `test_adapter_matrix.py` |
| Medium: worker did not register scheduled tasks | Missing Celery include | Explicit task-module include. `api/app/scheduler/celery_app.py` | Registered-beat test and actual Redis/worker dispatch |
| Medium: daily in-process lock race/invalid schedule settings | Non-atomic set operations and missing bounds | Mutex and timezone/time/range validation. `api/app/scheduler/daily.py` | Concurrent-lock, settings and failure-release tests |
| Medium: onboarding accepted invalid/missing values | No per-step validation | Role/mode/duration/compensation/date/limit/file checks, accessible errors, stale filename reset; layout retained. `frontend/app/onboarding/page-content.tsx` | Eleven component tests including role/default-review/oversize/range cases |

## QA infrastructure fixes

- Tests inherited developer dotenv/direct DB configuration: bootstrap now sets
  test-only config before app imports, disables dotenv, enforces SQLite FKs,
  isolates storage and resets limiter state. `api/tests/conftest.py` and new
  local-only PostgreSQL fixtures ensure cloud data is not modified.
- Undisposed SQLite test engines caused resource warnings: explicit cleanup in
  `api/tests/conftest.py`, `test_resume_encryption_backfill.py`. Final warning
  count is one transport deprecation, not suppressed warnings.
- Next build/typecheck ran concurrently once, removing `.next/types` while tsc
  read it. Sequential runbook commands resolve the runner race; no type errors
  were disabled or ignored.
- Added component/Playwright/coverage tooling, safe secret scanner and opt-in
  live Clerk runner. Test keys/local targets required; no retained auth traces,
  passwords or storage states. `.env.qa`/generated artifacts remain ignored.
- New test configurations exclude browser specs from Vitest, not failing tests.
  All four release failures remain active in the complete default pytest run.

## Release-path fixes completed after the original QA

| Issue / severity | Root cause | Fix / files | Tests |
| --- | --- | --- | --- |
| High: dashboard/settings/saved jobs not persistent | Missing APIs and mock screen data | Owner-scoped dashboard, settings schemas/service/router, job state API; frontend screens connected | Original four release contracts retained; persistent API/UI tests; real HTTP restart |
| High: daily task placeholder | No persisted orchestration | scheduler/pipeline.py and run_models.py; real catalogue adapter; migration0007; tasks wired to services | Populated pipeline and approval/PDF journey; audit/limit/retry tests |
| High: concurrent/restarted preparation could duplicate work | Process-local lock/results | PostgreSQL user-row transaction lock, unique daily run, user/job uniqueness, persisted preparation counters | Four concurrent SQL connections create one package; new-session retry creates none |
| High: production limiter multiplied quota across processes | Local-only counters | Atomic Redis INCR/expiry and fail-closed503; bounded local fallback only for development | Actual shared Redis across two middleware instances; Redis failure test |
| High: desired technologies counted as verified skills | Matching unioned preference skills into qualifications | Only confident master/project/experience facts; shared skill evidence helper for writing | DesiredAWS remains missing; C/C++, Java/JavaScript, SQL/NoSQL distinction tests |
| Medium: package approval could use stale client references/preferences | Two independent client writes | Atomic server approval verifies stored resume and current score/hard filters; compare-and-set resume approval in same transaction | Foreign404 and changed-preference rejection; verified package/export journey |
| Medium: private downloads unavailable | No export route | Authenticated no-store attachment downloads, approval gate, fixed filenames, owner namespace validation | PDF/header/export gate and foreign-access tests |
| Medium: failed pipeline had no durable safe status | Partial transactional work/unsanitized errors | Rollback partial work, safe failure audit, persistent four-attempt bound and Celery late ack/retry settings | Failure-count/rollback/secret-message regression |
| Medium: scheduling ignored individual timezones | Global daily stub | Minute due dispatch uses persisted timezone/search time and disabled/completed suppression | DueIndia/not-dueUS/disabled/completed dispatch test |
| Medium: onboarding did not save/upload | Local React selections and navigation only | Profile/preferences persisted, cadence stored when supplied, upload completed before navigation, API errors retained | Component request/payload test and actual HTTP persistence journey |
| Medium: namespace traversal could escape an ownership prefix | Prefix-only object validation | Exact UUID namespace/file shape and resolved-parent check | Tampered owner/../other namespace rejected |

The migration-head expectation changed from0006 to0007 because a real new
migration was added; existing legacy-account preservation and schema-parity
assertions remain. The concurrency fixture was corrected to satisfy existing
file-metadata and unlocked-source triggers, not by relaxing those protections.

## Open high findings / release prerequisites

- Seven high frontend development-tree advisories remain (unpatched braces and
  propagated Tailwind/lint dependencies). Runtime npm audit and backend audit
  are clean. No forced framework downgrade/migration was used to fake a clean audit.
- Live Clerk lifecycle/cookie verification requires dedicated test keys/users.
  .env.qa is still blank; no real login success is claimed.
- Managed secret delivery/key rotation and future OAuth envelope encryption
  require deployment/integration work; no OAuth/password store exists.
- Successful external submission, atomic submission quotas and durable provider
  idempotency are not implemented or verified. Daily **preparation** safety is
  now persistent; that is not proof of an external submission receipt.
- Normal Neon data was not migrated. Migration0007 must be reviewed/applied to
  the intended deployment before these schema-dependent endpoints can run there.
- Docker daemon/image/deployment verification and broker/outbox/multi-host
  recovery remain open operational requirements.

No known failing test remains in the executed suites. This does not certify
the unexecuted provider/deployment requirements or close all production risks.

## Open medium/low findings and unverified behavior

- Medium: two moderate frontend development advisories remain.
- Medium: object storage/private signed downloads, data export, audit retention
  and production deletion workflow absent. File unlink and DB commit are not
  atomic; a late failure can leave a DB reference whose file has been removed.
  Durable deletion/outbox workflow is required before stronger guarantees.
- Medium: full live authenticated browser journeys and comprehensive account,
  tracking-status, source integration and PDF layout/Unicode/long-text coverage
  remain incomplete. Current screens use real APIs rather than mock datasets.
- Medium: future sending dedup/external executor results remain in-memory; no
  sending or external submission integration is enabled.
- Medium: real model timeout/invalid JSON, source/database/Redis outage recovery,
  successful submission retries, complete audit/notifications not verified.
  Deterministic injection tests do not certify future model/tool integration.
- Low: Starlette httpx TestClient deprecation; native Python3.13 QA does not
  establish Python3.12 Docker compatibility. Docker daemon unavailable.
- Low: authenticated responsive/account-menu/empty/loading/error UI coverage
  incomplete. Login375/768/1440px checks are not all-screen responsive coverage.

## Required continuation

Configure a dedicated Clerk test app and two verified +clerk_test users per
QA_RUNBOOK.md. Run the opt-in session suite; test signup/password/cookie/domain
flows separately. Review/apply migration0007 to the intended deployment, finish
remaining operational safeguards and verify Docker/live authenticated browser
journeys. Do not enable external submissions without a reviewed integration.

**All executed tests pass; full production release review remains incomplete.**
