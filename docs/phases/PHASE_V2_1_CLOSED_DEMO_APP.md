# S.A.G.A. v2 Phase 1 — Closed-Demo Main Site, Accounts & Invitations

**Status:** ACTIVE — 1A COMPLETE; 1B COMPLETE; 1C NEXT

**Tracking:** #151

## Goal

Turn the Phase-0 web foundation into the first real S.A.G.A. v2 application: a closed invite-only demo with account/session boundaries, email invitations, admin access management, and a production-quality narrative workspace shell.

Phase 1 establishes the product/app/auth/UI contracts that the future AI system will operate behind.

## User Value

An invited demo user should be able to:

1. receive a S.A.G.A. invitation email;
2. confirm the invitation through the supported Auth flow;
3. establish credentials;
4. sign in later;
5. reach the private S.A.G.A. workspace;
6. browse the first application information architecture without seeing internal provider/pipeline complexity.

An active S.A.G.A. admin should be able to invite users, revoke pending invitations, inspect S.A.G.A.-owned account state, suspend/reactivate accounts, and manage roles without relying on browser metadata.

## Merged Evidence

Phase 0 web foundation:

- PR #149
- merge commit `261b75ff2a60dfcada681af6b6c918c1ff5e3366`

Phase 1 contract/governance:

- PR #152
- merge commit `55beaccab011a4c5337db86dd88b52f6d48734c4`

Phase 1B account/access foundation:

- PR #153
- code merge commit `5d5b59d17d2bd2f9a5769d2e5c4f9a2b43d1bad9`
- exact PR head `e81915942ba9e859c79898ec60fdda38a56235d3`
- exact-head `SAGA v2 Web CI`, `Required Check Compatibility`, and `Backend Architecture CI` all succeeded before merge

Durable validation record:

`docs/validation/PHASE_V2_1B_ACCOUNT_ACCESS_2026-09-11.md`

The documentation handoff refresh followed through PR #154.

## Owner Constraint — Closed Demo

S.A.G.A. v2 is not open signup.

- Public self-signup is disabled.
- Account admission begins with an admin invitation email.
- Supabase Auth is identity/session authority.
- S.A.G.A. owns product access, role, status, and invitation state.
- Public landing/brand routes may exist.
- Private product routes require a fresh verified identity plus active S.A.G.A. account access.
- Invitation/account administration is server-only and admin-authorized.
- Service-role/Auth Admin credentials never enter browser code.

## RenderLab Reference Boundary

RenderLab is read-only reference material for process/setup/UI patterns only.

Permitted reference categories include:

- repository-first continuity;
- contract-first progressive phases;
- Server Components by default with small client islands;
- maintained accessible primitives and semantic tokens;
- responsive/accessibility/reduced-motion discipline;
- identity vs product-access separation;
- closed-beta invitation/access patterns;
- remote CI and rendered UI validation.

Do not modify RenderLab. Do not copy its product code, routes, schema/table names, branding, visual composition, credentials, data, storage, deployments, or resources.

S.A.G.A.-owned translations are authoritative:

- `docs/v2/FRONTEND_ARCHITECTURE.md`
- `docs/v2/UI_SYSTEM.md`
- `docs/v2/ACCESS_AND_INVITATIONS.md`

## Phase 1B — Complete Foundation

### Active v2 database lineage

The active v2 Supabase migration lineage is:

`apps/web/supabase/migrations/`

The historical root `supabase/migrations/` tree is not the v2 bootstrap source.

### Account access

Merged account state:

- `saga_account_access` keyed by verified Supabase Auth user ID;
- role: `member | admin`;
- status: `active | suspended`;
- inviter/acceptance/audit metadata required by the closed-demo contract.

### Invitations

Merged invitation state:

- `saga_invitations` keyed by normalized email intent;
- intended role;
- `pending | accepted | revoked | expired` lifecycle;
- inviter/acceptance/revocation/expiry metadata;
- no reusable raw Auth invite token, OTP, password, or equivalent credential material.

### Database security

Merged protections:

- forced RLS on privileged account/invitation tables;
- browser-role table privileges revoked;
- service-role-only privileged persistence access.

### Transactional invitation claim

The merged server-owned claim routine:

- derives effective identity server-side;
- reloads verified email from `auth.users`;
- never trusts browser-supplied effective user ID/email/role;
- serializes the eligible invitation row;
- expires stale pending invitations;
- rejects missing, mismatched, revoked, expired, or consumed state;
- prevents double claim;
- atomically establishes S.A.G.A. account access.

### Server authorization

Merged server boundaries include:

- fresh `auth.getUser()` verification;
- server-only privileged Supabase client using `SUPABASE_SERVICE_ROLE_KEY`;
- account resolution for unauthenticated, not admitted, suspended, active, and unavailable states;
- active-admin authorization helper.

### Deterministic validation

Exact PR #153 head checks:

- `SAGA v2 Web CI` run `34593615395` — success;
- `Required Check Compatibility` run `34593615380` — success;
- `Backend Architecture CI` run `34593615394` — success.

The v2 database-contract CI:

1. starts PostgreSQL 16;
2. creates a minimal Supabase-compatible Auth/API-role bootstrap;
3. applies only `apps/web/supabase/migrations/*.sql`;
4. runs `apps/web/supabase/tests/closed_demo_account_access.sql`.

Proven behavior includes migration application, RLS/browser-role denial, successful verified-email invitation claim, double-claim denial, verified-email mismatch denial, expiry settlement, and duplicate pending invitation rejection.

The old external Studio/Vercel failure remains deferred and is not an active v2 validation signal.

## Phase 1C — Immediate Scope

Start from the repository's actual current `main` after verifying its exact SHA, then create a fresh Phase 1C branch.

Implement:

- public sign-in surface;
- server invitation confirmation route;
- password setup/change flow for confirmed invited users;
- sign-out;
- SSR cookie refresh/session plumbing;
- protected route/layout boundary using fresh identity + merged S.A.G.A. account resolver;
- safe same-origin redirect validation;
- deterministic auth/access tests;
- bounded states for unauthenticated, not admitted, suspended, active, and unavailable access.

Do **not** add public create-account/signup behavior.

Hosted email delivery is not required for deterministic Phase 1C CI. Keep hosted SMTP/template claims separate until a dedicated S.A.G.A. Supabase project is configured and tested.

## Target Route Boundary

Initial direction; route groups may separate public/auth/app layouts without leaking those group names into URLs.

```text
/                         public landing/brand
/sign-in                  public sign-in
/auth/confirm             server invitation/recovery confirmation
/set-password             confirmed/session-bound credential setup

/home                     private application home
/library                  private source/library workspace
/projects                 private project list
/projects/[projectId]     private project workspace
/projects/[projectId]/characters
/projects/[projectId]/world
/projects/[projectId]/timeline
/projects/[projectId]/canon
/projects/[projectId]/story
/projects/[projectId]/media
/activity                 private activity/jobs later
/settings                 account/settings
/admin                    active-admin only
```

Routes beyond the active implementation slice are information-architecture direction, not a promise that every route ships in one PR.

## Authorization Model

```text
request/session
  -> SSR Auth cookie maintenance
  -> fresh server Supabase Auth identity verification
  -> S.A.G.A. account-access lookup
  -> role/status decision
  -> owner/admin-scoped domain service
```

Rules:

- anonymous -> sign-in boundary;
- verified identity with no S.A.G.A. account -> access denied / invitation-completion state, not auto-admitted;
- suspended account -> private product denied, while bounded security/recovery/sign-out may remain available;
- active member -> private product;
- active admin -> private product + admin operations;
- role is never read from browser/user metadata for authorization.

## Invitation Flow

```text
active admin
  -> create invitation(email, role)
  -> normalize + validate email
  -> persist pending S.A.G.A. invitation
  -> request Supabase Auth invite email server-side
  -> recipient opens supported confirmation link
  -> server verifies Auth invitation
  -> fresh verified identity/email
  -> transactional claim of matching eligible S.A.G.A. invitation
  -> active S.A.G.A. account established
  -> credential setup / private app
```

If outbound email fails, the product must surface a bounded delivery failure and preserve enough product state to retry/revoke safely without leaking token material.

## Later Phase 1 Slices

### 1D — Application shell / first product surfaces

After a S.A.G.A.-specific concept/review pass, implement the responsive shell and initial Home/Library/Projects footholds.

Target information architecture:

- Home
- Library
- Projects
- Characters
- World
- Timeline
- Canon
- Story
- Media
- Activity
- Settings
- Admin

Do not present fake analysis results merely to fill UI.

### 1E — Admin operations + hosted integration

Implement narrow private admin APIs/UI for:

- pending invitations;
- S.A.G.A.-known accounts only;
- role/status mutation;
- self-lockout/last-admin protection where applicable;
- sanitized operational feedback.

Then configure/verify the dedicated S.A.G.A. Supabase project, email path, and at least one real bounded invite acceptance flow. Establish scoped B2 runtime credentials when source upload becomes part of the product flow.

Do not expose the whole shared `auth.users` directory as product data.

## Email Operational Gate

Before invitation delivery is called end-to-end validated, verify:

- S.A.G.A. Supabase Site URL;
- allowlisted same-origin redirects;
- invite/recovery templates using supported confirmation variables;
- custom SMTP or equivalent Auth email hook;
- sender-domain authentication;
- acceptable rate limits;
- actual inbox delivery for at least one bounded test invitation.

Application CI does not need to send real external email.

## UI/UX Contract

Primary principle: **Narrative first, complexity on demand.**

Core rules:

- maintained accessible controls before custom mechanics;
- story/source/evidence/entity/timeline content dominates chrome;
- progressive disclosure for advanced controls;
- no generic card-grid solution for every page;
- prefer rails, lists, split workspaces, canvases, editors, relationship/timeline views, and focused detail panels where they fit the task;
- desktop productivity is primary, but mobile/narrow access remains coherent and touch-friendly;
- keyboard/focus semantics are required;
- no hover-only essential behavior;
- meaningful motion only, with reduced-motion/static equivalents;
- concept/rendered fidelity review is separate from functional CI.

See `docs/v2/UI_SYSTEM.md`.

## Phase Slices

### 1A — Contract / architecture / UI governance — COMPLETE

Merged through PR #152.

### 1B — Account/invitation persistence + server authorization — COMPLETE

Merged through PR #153.

### 1C — Auth/invite/password surfaces — NEXT

Implement sign-in, confirmation, password setup, session/account boundaries, and protected layout behavior.

### 1D — Application shell / first product surfaces — PENDING

Implement the approved responsive shell and first Home/Library/Projects composition using S.A.G.A.-owned visual concepts.

### 1E — Admin invitation/account operations + hosted integration — PENDING

Implement admin APIs/UI and complete the hosted Supabase/email proof.

Later slices do not silently change earlier contracts without updating authoritative docs.

## Validation Matrix

| Claim | Required evidence | Current state |
|---|---|---|
| Phase contract current | docs/PROJECT/DECISIONS review | current through Phase 1B |
| No public signup | structural/API/UI tests + rendered auth review | structural contract validated; rendered auth pending 1C |
| Private route denial | deterministic auth/access tests | pending 1C |
| Suspended/unknown denial | deterministic account/route tests | server resolver exists; route proof pending 1C |
| Admin-only invitation mutation | fresh-auth + active-admin tests | server boundary exists; UI/API pending 1E |
| Invite claim matches verified email | transactional integration test | validated in disposable Postgres |
| No raw invite token persistence | schema/structural test | validated |
| No privileged secret in browser | source/bundle structural checks | structural boundary validated; continue every slice |
| UI shell responsive | desktop + narrow rendered evidence | pending 1D |
| Auth/admin accessible | keyboard/focus/touch review | pending 1C/1E |
| Reduced motion | motion-path audit | pending visual slices |
| Hosted invitation delivery | explicit live inbox test | pending 1E |
| Merge safety | exact-head v2 CI + relevant repo checks | Phase 1B passed |

## External Dependencies / Blockers

Not blockers for deterministic Phase 1C repository work:

- new S.A.G.A.-owned Supabase project;
- custom SMTP/email hook;
- scoped B2 runtime application key.

They become blockers only for hosted end-to-end slices that need them.

Supabase project creation through the connected tool requires explicit organization selection and cost confirmation. Do not infer that authorization from a generic “keep going.”

## Explicitly Out of Scope

- agentic AI/LLM orchestration;
- identity/coreference/canon extraction runtime;
- generation planning/narrative generation;
- live visual/audio model execution;
- public signup/request-access product;
- social login unless separately approved;
- billing/subscriptions;
- organization/team multi-tenancy;
- copying/modifying RenderLab;
- production deployment without separate owner authorization;
- claiming email deliverability before hosted configuration is verified.

## Exit Criteria

Phase 1 closes only when:

1. Phase-1 contracts are merged and authoritative;
2. S.A.G.A.-owned account/invitation schema is applied to the new S.A.G.A. Supabase project;
3. public self-signup remains absent;
4. invite confirmation + credential setup + later sign-in work end-to-end;
5. private routes require fresh verified identity + active S.A.G.A. account;
6. suspended/unknown identities fail closed;
7. active admins can create/revoke invitations and manage bounded account role/status;
8. at least one real invitation email is delivered and accepted through hosted configuration;
9. the private application shell and initial narrative information architecture are implemented and responsive;
10. no privileged credentials/tokens leak to browser, repository, or logs;
11. exact-head v2 CI and relevant rendered/accessibility review pass;
12. `PROJECT.md` records the merged baseline and next phase from verified reality.

## Next-Phase Direction

Do not fully design the agentic AI phase yet.

Once Phase 1 establishes real projects/sources/accounts/storage/jobs/UI ownership, plan the next immediate phase around the first durable story/source workflow and the job boundary the future agents will consume.