# Phase V2.1C Auth / Access Validation — 2026-09-11

## Result

**Phase 1C deterministic repository work is complete and merged.**

Implementation PR: **#156**

- exact PR head: `7bc81877a55af9b47b6bbc96abd7a17e9100fda3`
- exact PR tree: `3bb5388d2004fc09124fddbc59b7978414be6d4f`
- merge commit on `main`: `319b785e43a169b4ffd7b57cd5be32ad3ef5da67`

This validation proves the repository-owned closed-demo auth/access behavior implemented in Phase 1C. It does **not** claim that hosted Supabase invitation email delivery is configured or validated.

## Implemented Scope

Phase 1C added:

- invitation-only `/sign-in` with no public self-signup path;
- server-owned `/auth/confirm` handling for Supabase invite token hashes;
- reuse of the Phase 1B transactional S.A.G.A. invitation claim after fresh Auth verification;
- session-bound `/set-password` password setup/change;
- sign-out;
- Next.js 16 `proxy.ts` SSR Supabase cookie/session refresh plumbing;
- private route-group layout authorization using the merged S.A.G.A. account resolver;
- bounded routing for unauthenticated, not-admitted, suspended, active, and unavailable states;
- safe same-origin post-auth redirect normalization;
- a minimal `/home` private-access checkpoint only, with the real application shell intentionally deferred to Phase 1D;
- deterministic structural/auth-routing tests;
- bounded `unavailable` handling when server Auth/config/access dependencies cannot be trusted.

## Security Properties Preserved

The merged implementation preserves the closed-demo model:

- there is no `auth.signUp()` path;
- browser/user metadata is not an authorization source;
- private application access still requires fresh server-verified Supabase identity plus active S.A.G.A. account access;
- suspended and not-admitted identities fail closed for private routes;
- invitation confirmation does not persist reusable raw invite tokens in S.A.G.A. tables;
- the existing server-owned transactional claim remains the account-admission authority;
- `SUPABASE_SERVICE_ROLE_KEY` remains server-only;
- SSR cookie refresh is plumbing, not the final authorization decision;
- safe redirect handling rejects cross-origin/protocol-relative confirmation destinations.

## Exact-Head CI Evidence

The following pull-request workflows all ran against exact PR head `7bc81877a55af9b47b6bbc96abd7a17e9100fda3` and completed successfully before merge:

| Workflow | Run | Result |
|---|---:|---|
| SAGA v2 Web CI | `34601422907` | success |
| Required Check Compatibility | `34601422970` | success |
| Backend Architecture CI | `34601422837` | success |

### SAGA v2 Web CI

Run `34601422907` proved:

- dependency install — success;
- lint — success;
- TypeScript typecheck — success;
- unit and structural tests — success;
- production Next.js build — success;
- disposable PostgreSQL database-contract job — success.

The database-contract job reapplied only the active v2 migration lineage under `apps/web/supabase/migrations/` and revalidated the closed-demo account/invitation contract.

### Backend Architecture CI

Run `34601422837` completed successfully, including active backend tests, architecture/credential-boundary checks, migration validation, and container-image build checks. These broader checks are compatibility evidence only; they do not change the v2 web ownership model.

## Known Deferred / Non-Blocking Signals

The historical Vercel `studio` deployment status still reports failure. Repository governance already classifies that legacy Studio/Vercel signal as deferred and not an active S.A.G.A. v2 validation gate.

No hosted email-delivery claim is made here. Phase 1E still owns the operational proof for:

- a dedicated S.A.G.A. Supabase project;
- Site URL and redirect allowlist;
- invite/recovery templates;
- custom SMTP or equivalent email hook;
- actual bounded inbox delivery and invitation acceptance;
- scoped non-master B2 runtime credentials when product upload flow needs them.

## Phase Handoff

Phase 1C is complete.

Before Phase 1D implementation, perform the required S.A.G.A.-specific UI concept/review pass using `docs/v2/UI_SYSTEM.md`.

Phase 1D then owns:

- authenticated application shell;
- Home;
- Library;
- Projects;
- responsive navigation/composition system;
- rendered responsive/accessibility review.

The product principle remains **“Narrative first, complexity on demand.”** Do not turn the storytelling workspace into a generic admin-dashboard/card-grid shell, and do not visually copy RenderLab.

Agent/LLM runtime work remains out of scope until the application/data/storage/job contracts are ready for that later phase.
