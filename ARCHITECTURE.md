# InternAgent Architecture

## Trust boundaries

```text
Browser -> Clerk sign-in + resource-level Next.js page guards
        -> same-origin allowlisted proxy (server-side Clerk session token)
        -> HTTPS/CORS/rate-limit middleware -> verified Clerk JWT boundary
        -> owner-scoped API routers -> SQLAlchemy parameterized persistence
        -> encrypted resume/fact storage

SQLAlchemy -> Neon pooled TLS connection (application queries)
Alembic -> Neon direct TLS connection (versioned migrations)

Untrusted job/email/site text -> normalization/matching only -> reviewable drafts
                                                    X no tool execution
                                                    X no secret access
                                                    X no application submission

Draft -> deterministic ApplicationPolicyService -> authorized executor OR assisted/manual handoff
```

## Security decisions

- Candidate facts are derived only from locked master-resume versions and explicitly supplied profile data.
- Resume artifacts use authenticated encryption and opaque internal storage references. API responses omit file references.
- All user-owned reads/writes are constrained by authenticated `user_id`; absent/foreign records return non-enumerating not-found responses.
- `SourceCapability` and `ApplicationPolicyService` are the mandatory authorization boundary before any future submitter.
- Job descriptions, company text, messages, questions, and email text are untrusted data. No AI module has direct database, shell, URL, or submission access.

## Deployment boundaries

The current repository is a foundation, not a production integration deployment.
Clerk sign-in/JWT validation is implemented; the provider keys/issuer and live
identity tests remain required. Neon development storage is provisioned and
migrated. The UI forms still use earlier mocks and must be connected to the
authenticated API. Before release, add managed secret delivery, Redis-shared
limits and locks, cloud private storage, audit retention/deletion workflows, and
reviewed source/API integrations. Employer OAuth token storage is a separate future
integration: there is currently no employer OAuth refresh-token store.
