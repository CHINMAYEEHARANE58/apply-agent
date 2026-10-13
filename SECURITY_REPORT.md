# InternAgent Security Report

Latest verification: 2026-10-12 (Clerk + Neon integration)

## Fixed in this review

- Production HTTP requests are rejected before authentication or data access; successful production responses carry HSTS.
- Strict CORS uses an explicit `ALLOWED_ORIGINS` list, disallows credentialed cross-origin requests, and limits methods/headers.
- Added `nosniff`, frame-denial, referrer, and restrictive CSP headers.
- Added an in-process privacy-preserving request-rate limiter and retained the streaming 5 MB upload guard.
- Existing controls verified: parameterized SQLAlchemy queries, owner-scoped resource lookups, encrypted private resume storage, encrypted parsed resume/facts, no public storage URLs, strict PDF/DOCX checks, immutable master resume versions, deterministic submission policy, and fact verification.

## Findings

| Severity | Finding | Status |
| --- | --- | --- |
| Critical | Direct application submission, arbitrary tool/URL execution, or job-site automation | Not present. All current executors stop at review/manual boundaries. |
| Critical | Resume fabrication | Mitigated by evidence-bound facts and fail-closed verification tests. |
| High | Clerk production identity configuration and live verification are incomplete | Implementation added; issuer/keys still missing. Signed-token tests pass, but provider signup/signin and production domain configuration must be verified before release. |
| High | Managed secret manager and envelope-encrypted OAuth refresh-token store are not implemented because no OAuth integration exists | Open deployment blocker; do not enable OAuth until implemented. |
| High | Rate limiting is process-local; a multi-worker production deployment needs Redis-backed shared limits | Open deployment blocker. |
| High | Full frontend dependency audit reports 7 high development-tool advisories | Open; runtime-only audit is clean. Upgrade remaining Tailwind/glob/lint tool dependencies without an unreviewed major-version migration. |
| Medium | Two moderate development-tool dependency advisories | Open; no critical dependency advisories remain after updating the test runner and PostCSS. |
| Medium | Browser uses Clerk cookies while FastAPI is bearer-only | Proxy mutations now require exact same-origin `Origin`; tests cover missing/foreign origins. Browser cookies and UUID headers are never forwarded as identity. |
| Medium | Signed short-lived resume download URLs are not implemented; no resume-download endpoint exists, so filesystem paths remain private | Add only with an object-storage download flow. |
| Low | Starlette test client emits a dependency deprecation warning | Upgrade test transport dependencies before release. |

## Release decision

**Not production-ready.** Provider configuration/live testing, mocked-screen API
wiring, outstanding development dependencies, managed secrets, distributed rate
limits, and privacy deletion/retention workflows remain release work.

## Clerk + Neon hardening

- Clerk credentials stay with Clerk; the application stores a unique Clerk subject
  mapped to its own UUID. Email is fetched from the provider and must be verified.
  Existing email accounts are not silently linked.
- The backend pins the issuer and trusted authorized parties, accepts only signed
  RS256 session JWTs, and ignores JWT-supplied URLs and browser identity headers.
- Every protected page has a resource-level sign-in check; the proxy and backend
  enforce their own independent checks. Middleware is not the authorization boundary.
- Neon requests use TLS and pooling; migrations use the direct endpoint. SQL bind
  parameters are hidden, and database failures return generic errors without PII.
- Local secrets are gitignored and owner-readable only. Docker build contexts exclude
  environment files and private resumes; only the Clerk publishable key is a build argument.
- Public source authorization registration is disabled in Clerk mode. Permissions
  cannot be self-declared by application users.

## Operational requirements

- Keep `.env` uncommitted; `.env.example` contains placeholders only.
- Terminate TLS at a trusted proxy/load balancer and forward only HTTPS traffic to the API.
- Configure explicit `ALLOWED_ORIGINS`; never use `*` with credentials.
- Use a managed secret manager and per-record envelope encryption for future OAuth refresh tokens.
- Do not log resume text, application answers, tokens, phone numbers, or email bodies.
