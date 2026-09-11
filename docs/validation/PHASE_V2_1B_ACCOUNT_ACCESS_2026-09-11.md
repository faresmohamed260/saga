# Phase v2.1B Account / Access Foundation — Validation Record

Date: **2026-09-11**

Status: **MERGED AND VALIDATED**

## Scope

This record captures the deterministic evidence for S.A.G.A. v2 Phase 1B: closed-demo account/invitation persistence and server authorization.

It does **not** claim hosted Supabase readiness, outbound email delivery, production deployment, or complete user-facing authentication UX. Those remain later Phase 1 work.

## Merged Baseline

PR: **#153 — Add S.A.G.A. v2 closed-demo access foundation**

Exact PR head before merge:

`e81915942ba9e859c79898ec60fdda38a56235d3`

Merged `main` commit:

`5d5b59d17d2bd2f9a5769d2e5c4f9a2b43d1bad9`

Merged tree:

`6a2814f97114e6d731235b933f3a75c8fa9fdc76`

## Exact-Head CI Evidence

Before merge, the exact PR head completed:

- `SAGA v2 Web CI` run **34593615395** — **success**
- `Required Check Compatibility` run **34593615380** — **success**
- `Backend Architecture CI` run **34593615394** — **success**

The old external Vercel `studio` status remained failed/deferred. It is a legacy Studio integration and is not an active S.A.G.A. v2 validation signal.

Earlier branch validation run **34593420479** also passed both jobs of `SAGA v2 Web CI`.

## Implemented Foundation

### Active v2 database lineage

The active v2 database lineage is isolated under:

`apps/web/supabase/migrations/`

The historical root `supabase/migrations/` lineage is not the v2 bootstrap source.

### Account access

Implemented `saga_account_access` keyed by verified Supabase Auth user ID with S.A.G.A.-owned:

- role: `member | admin`
- status: `active | suspended`
- invitation/audit metadata required by the phase contract

### Invitations

Implemented `saga_invitations` with:

- normalized email identity
- intended role
- `pending | accepted | revoked | expired` lifecycle
- inviter/acceptance/revocation/expiry metadata
- no reusable raw Auth invite token, OTP, password, or equivalent credential material

### Authorization/security

Implemented and validated:

- forced RLS on privileged account/invitation tables
- browser-role table privileges revoked
- service-role-only privileged persistence access
- fresh server `auth.getUser()` identity verification
- isolated server-only privileged Supabase client
- S.A.G.A. account resolver for unauthenticated/not-admitted/suspended/active/unavailable states
- active-admin authorization helper
- no authorization from browser metadata/user metadata

### Transactional invitation claim

The server-owned claim path:

- reloads the Auth user's verified email from `auth.users`
- does not trust browser-supplied effective identity/email/role
- serializes the eligible invitation row
- rejects missing/mismatched/revoked/expired/consumed invitations
- settles stale pending invitations to expired
- prevents double claim
- atomically establishes S.A.G.A. account access

## Disposable PostgreSQL Proof

`SAGA v2 Web CI` runs a dedicated database-contract job that:

1. starts PostgreSQL 16;
2. creates a minimal Supabase-compatible Auth schema and API roles;
3. applies only `apps/web/supabase/migrations/*.sql`;
4. runs `apps/web/supabase/tests/closed_demo_account_access.sql`.

The successful proof covers:

- clean migration application
- RLS/browser-role privilege denial
- successful verified-email invitation claim
- double-claim denial
- verified-email mismatch denial
- expiry settlement
- duplicate pending invitation rejection

## Structural / Web Validation

The Phase 1B web-quality job passed:

- dependency install
- lint
- TypeScript typecheck
- unit/structural tests
- production Next.js build

Structural tests cover the closed-demo invariants, including:

- no public signup path/affordance in the implemented foundation
- no browser service-role usage
- no role trust from user/browser metadata
- no reusable invitation-token persistence
- expected RLS/security boundaries

## Explicitly Not Yet Proven

Phase 1B does not prove:

- a hosted S.A.G.A.-owned Supabase project exists
- the v2 migration has been applied to hosted Supabase
- hosted Auth Site URL/redirect configuration
- custom SMTP/Auth email-hook delivery
- invitation email inbox delivery
- sign-in UI
- invite confirmation UI/route behavior
- password setup UX
- SSR session refresh/private route UX
- admin invitation/account management UI/API
- responsive application shell
- scoped B2 runtime application key

Those remain Phase 1C–1E work.

## Next Slice

Phase 1C begins from merged `main` and implements:

- sign-in
- server invite confirmation
- password setup/change
- sign-out
- SSR session refresh/cookie plumbing
- protected route/layout enforcement
- bounded unauthenticated/not-admitted/suspended/active/unavailable states
- same-origin redirect safety
- deterministic auth/access tests

Public self-signup remains forbidden.

RenderLab remains a read-only reference for engineering/UI process and must not be modified or copied.