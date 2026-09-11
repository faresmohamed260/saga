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

An active S.A.G.A. admin should be able to:

- invite a person by email;
- revoke a still-pending invitation;
- inspect S.A.G.A.-owned account state;
- suspend/reactivate an account;
- promote/demote roles without relying on browser metadata.

## Verified Current State

Merged Phase-0 baseline:

- repository: `faresmohamed260/saga`
- merge: `261b75ff2a60dfcada681af6b6c918c1ff5e3366`
- PR: #149
- Phase-0 issue: #148 closed complete

Merged Phase-1 contract baseline:

- merge: `55beaccab011a4c5337db86dd88b52f6d48734c4`
- PR: #152

Merged Phase-1B account/access foundation:

- current `main`: `5d5b59d17d2bd2f9a5769d2e5c4f9a2b43d1bad9`
- tree: `6a2814f97114e6d731235b933f3a75c8fa9fdc76`
- PR: #153
- exact PR head: `e81915942ba9e859c79898ec60fdda38a56235d3`
- exact-head `SAGA v2 Web CI`, `Required Check Compatibility`, and `Backend Architecture CI` all succeeded before merge

Durable Phase-1B evidence: `docs/validation/PHASE_V2_1B_ACCOUNT_ACCESS_2026-09-11.md`.

Verified foundation now includes:

- Next.js/React/TypeScript app under `apps/web/`;
- Supabase SSR configuration boundary;
- provider-neutral object storage + B2 S3 adapter;
- dedicated private B2 bucket validated through GitHub Actions;
- v2 web CI for install/lint/typecheck/tests/build;
- active v2 Supabase migration lineage under `apps/web/supabase/migrations/`;
- closed-demo account/invitation persistence and transactional claim logic;
- fresh server Auth identity verification and S.A.G.A. account resolver;
- active-admin authorization boundary;
- disposable-Postgres database-contract CI;
- v1 runtime classified historical/reference.

External state still not complete:

- there is no S.A.G.A.-owned hosted Supabase project configured yet;
- creating one through the connected tool requires explicit organization selection/cost confirmation;
- B2 master/bootstrap credentials exist, but no scoped runtime B2 application key is configured yet;
- hosted invitation-email SMTP/template configuration is not yet verified.

## Owner Constraint — Closed Demo

S.A.G.A. v2 is not open signup.

- Public self-signup is disabled.
- Account creation/admission begins with an admin invitation email.
- Supabase Auth remains identity/session authority.
- S.A.G.A. owns product access/role/status/invitation state.
- A public brand/landing page may remain available.
- Private product routes require a fresh verified identity plus active S.A.G.A. account access.

## RenderLab Reference Boundary

RenderLab is read-only reference material for process/setup/UI patterns only.

Useful reference principles inspected for this phase include:

- repository-first continuity;
- execution-ready phase contracts merged before implementation;
- Server Components by default and small client interaction islands;
- maintained accessible primitive layer;
- responsive/accessibility/reduced-motion requirements;
- explicit account identity vs product access separation;
- normalized-email invitation records above Supabase Auth;
- fresh server-side Auth checks for privileged/private authorization;
- admin-only account/invitation services;
- clear distinction between application code and hosted email/SMTP operational readiness;
- rendered UI validation separate from build success.

Do not copy RenderLab code, table names, routes, branding, visual composition, data, credentials or resources. Do not modify its repository during S.A.G.A. work.

S.A.G.A.'s own contracts are:

- `docs/v2/FRONTEND_ARCHITECTURE.md`
- `docs/v2/UI_SYSTEM.md`
- `docs/v2/ACCESS_AND_INVITATIONS.md`

## Implemented Phase 1B Foundation

### Account / invitation persistence

Phase 1B merged:

- `saga_account_access` keyed by verified Supabase Auth user ID;
- S.A.G.A.-owned account role (`member|admin` initially);
- S.A.G.A.-owned account status (`active|suspended` initially);
- `saga_invitations` with normalized email and `pending|accepted|revoked|expired` lifecycle;
- inviter/claim/audit timestamps required for deterministic authorization/operations;
- no reusable raw Auth invitation tokens/secrets in application tables;
- forced RLS and revoked browser-role table access;
- service-role-only privileged access.

The active v2 migration lineage is `apps/web/supabase/migrations/`. The historical root `supabase/migrations/` tree is not the v2 database bootstrap source.

### Invitation claim

The merged transactional claim routine:

- derives identity server-side;
- reloads verified `auth.users.email` rather than trusting browser input;
- locks the eligible invitation row;
- settles stale invitations to expired;
- rejects missing, mismatched, revoked, expired, or consumed state;
- prevents double claim;
- atomically establishes S.A.G.A. account access.

### Server authorization

Merged server boundaries include:

- fresh `auth.getUser()` identity verification;
- server-only privileged Supabase client using `SUPABASE_SERVICE_ROLE_KEY`;
- account resolution for unauthenticated, not admitted, suspended, active, and unavailable states;
- active-admin authorization helper;
- invitation claim service that never accepts browser-supplied effective user ID/email/role.

### Phase 1B deterministic validation

PR #153 exact-head checks:

- `SAGA v2 Web CI` run `34593615395` — success;
- `Required Check Compatibility` run `34593615380` — success;
- `Backend Architecture CI` run `34593615394` — success.

The v2 web CI database-contract job applies `apps/web/supabase/migrations/*.sql` to disposable PostgreSQL with a minimal Supabase-compatible Auth/API-role bootstrap and proves:

- migration application;
- RLS/browser-role privilege denial;
- successful verified-email invitation claim;
- double-claim denial;
- verified-email mismatch denial;
- expiry settlement;
- duplicate pending invitation rejection.

The external legacy Studio/Vercel failure is deferred and is not an active v2 validation signal.

## Phase 1C — Immediate Scope

Phase 1C is the next implementation slice. Start from current `main` on a fresh branch.

Implement:

- public sign-in surface;
- server invitation confirmation route;
- password setup/change flow for confirmed invited users;
- sign-out;
- SSR cookie refresh/session plumbing;
- fresh current-user verification for private product/account/admin authorization;
- protected layout/route boundary using the merged S.A.G.A. account resolver;
- safe same-origin redirect validation;
- deterministic auth/access tests;
- clear bounded states for unauthenticated, not admitted, suspended, active, and unavailable access.

Do **not** add public create-account/signup behavior.

Hosted email delivery is not required for deterministic Phase 1C CI. Keep hosted SMTP/template claims separate until a dedicated S.A.G.A. Supabase project is configured and tested.

## Later Phase 1 Scope

### Phase 1D — Main application shell / information architecture

Implement the first real shell around S.A.G.A. user concepts after a S.A.G.A.-specific visual concept/review pass.

Target product areas:

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
- Admin (authorized only)

Phase 1D need not fully implement every domain surface. It must establish the shell, routing model, responsive navigation, page composition rules and initial Home/Library/Projects footholds without presenting fake analysis results.

### Phase 1E — Admin invitation/account operations + hosted integration

Implement private admin UI/API for:

- pending invitations;
- S.A.G.A.-known accounts only;
- role/status mutation;
- self-lockout/last-admin protection when applicable;
- sanitized operational feedback.

Then configure/verify the new S.A.G.A. Supabase project/email path and prove a real bounded invite acceptance flow. Scoped B2 runtime credentials may also be established when source upload becomes part of the first product workflow.

Do not expose the whole shared `auth.users` directory as product data.

## Explicitly Out of Scope

- agentic AI/LLM orchestration;
- identity/coreference/canon extraction runtime;
- generation planning/narrative generation;
- live visual/audio model execution;
- a public signup/request-access product;
- social login unless separately approved;
- billing/subscriptions;
- organization/team multi-tenancy;
- copying/modifying RenderLab;
- production deployment without separate owner authorization;
- claiming email deliverability before hosted configuration is verified.

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

Routes beyond the active implementation slice are information-architecture direction, not a promise that every route ships in the same PR.

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
- suspended account -> private product denied but bounded security/account recovery/sign-out may remain available;
- active member -> private product;
- active admin -> private product + admin operations;
- role is never read from browser/user metadata for authorization.

## Invitation Flow

```text
active admin
  -> POST invitation(email, role)
  -> normalize + validate email
  -> persist pending S.A.G.A. invitation
  -> request Supabase Auth invite email server-side
  -> recipient opens supported token-hash/confirmation link
  -> server verifies Auth invitation
  -> fresh verified identity/email
  -> transactional claim of matching eligible S.A.G.A. invitation
  -> active S.A.G.A. account established
  -> credential setup / private app
```

If outbound email fails, the product must surface a bounded invitation-delivery failure and preserve enough product state to retry/revoke safely without leaking token material.

## Email Operational Gate

Before the invite flow can be called end-to-end validated in a hosted demo, verify:

- S.A.G.A. Supabase project Site URL;
- allowlisted same-origin callback/redirect URLs;
- invite and recovery email templates using supported confirmation/token-hash variables;
- custom SMTP or equivalent Auth email hook;
- sender domain authentication;
- acceptable rate limits;
- actual inbox delivery for at least one bounded test invitation.

Application CI is not required to send real external email.

## UI/UX Contract

Primary product principle: **Narrative first, complexity on demand.**

The application should feel like a focused narrative intelligence workspace rather than a generic admin dashboard or an AI-provider console.

Core rules:

- maintained accessible controls before custom mechanics;
- story/source/evidence/entity/timeline content dominates chrome;
- progressive disclosure for advanced controls;
- no default card-grid solution for every page;
- prefer rails, lists, split workspaces, canvases, editors, relationship/timeline views and focused detail panels where they fit the user task;
- desktop productivity is primary, but mobile/narrow access remains coherent and touch-friendly;
- WCAG-oriented keyboard/focus semantics;
- no hover-only essential behavior;
- meaningful motion only, with reduced-motion/static equivalents;
- concept and rendered fidelity review are separate from functional CI.

See `docs/v2/UI_SYSTEM.md`.

## Phase Slices

### 1A — Contract / architecture / UI governance — COMPLETE

Merged through PR #152.

### 1B — Account/invitation persistence + server authorization — COMPLETE

Merged through PR #153 at `5d5b59d17d2bd2f9a5769d2e5c4f9a2b43d1bad9`.

### 1C — Auth/invite/password surfaces — NEXT

Implement sign-in, confirmation, password setup, session/account boundaries and protected layout behavior.

### 1D — Application shell / first product surfaces — PENDING

Implement approved responsive shell and first Home/Library/Projects composition using S.A.G.A.-owned visual concepts.

### 1E — Admin invitation/account operations + hosted integration — PENDING

Implement admin UI/APIs, configure/verify the new S.A.G.A. Supabase project/email path and prove a real bounded invite acceptance flow. Scoped B2 runtime credentials may also be established when source upload becomes part of the first product workflow.

Later slices do not silently change earlier contracts without updating the authoritative docs.

## Validation Matrix

| Claim | Required evidence | Current state |
|---|---|---|
| Phase contract current | docs/PROJECT/DECISIONS exact-head review | current through Phase 1B |
| No public signup | structural/API/UI tests + rendered auth review | structural contract validated; rendered auth pending 1C |
| Private route denial | deterministic auth/access tests | pending 1C |
| Suspended/unknown denial | deterministic server account resolver tests | server resolver implemented; route proof pending 1C |
| Admin-only invitation mutation | fresh-auth + active-admin tests | server boundary implemented; UI/API pending 1E |
| Invite claim matches verified email | transactional integration test | validated in disposable Postgres |
| No raw invite token persistence | schema/structural test | validated |
| No privileged secret in browser | bundle/source structural checks | structural boundary validated; continue every slice |
| UI shell responsive | desktop + narrow rendered evidence | pending 1D |
| Auth/admin accessible | keyboard/focus/touch review | pending 1C/1E |
| Reduced motion | implemented motion paths audited | pending visual slices |
| Hosted invitation delivery | explicit live inbox test after SMTP/templates configured | pending 1E |
| Merge safety | exact-head `SAGA v2 Web CI` + required repo checks | Phase 1B passed |

## External Dependencies / Blockers

Not blockers for Phase 1C deterministic implementation:

- new S.A.G.A. Supabase project;
- custom SMTP/email hook;
- scoped B2 runtime application key.

They become blockers only for hosted end-to-end slices that require them.

Supabase project creation through the connected tool requires the owner to explicitly choose an organization and confirm the reported cost before mutation. Do not assume this authorization from generic “keep going.”

## Exit Criteria

Phase 1 closes only when:

1. Phase-1 contracts are merged and authoritative;
2. S.A.G.A.-owned account/invitation schema is applied to the new S.A.G.A. Supabase project;
3. public self-signup is absent;
4. invite confirmation + credential setup + later sign-in work end-to-end;
5. private routes require fresh verified identity + active S.A.G.A. account;
6. suspended/unknown identities fail closed;
7. active admins can create/revoke invitations and manage bounded account role/status;
8. at least one real invitation email is delivered and accepted through the hosted configuration;
9. the private application shell and initial narrative information architecture are implemented and responsive;
10. no privileged credentials/tokens leak to browser, repository or logs;
11. exact-head v2 CI and relevant rendered/accessibility review pass;
12. `PROJECT.md` records the merged baseline and the next application/agent phase from verified reality.

## Next-Phase Direction

Do not fully design the agentic AI phase yet.

Once Phase 1 establishes real projects/sources/accounts/storage/jobs/UI ownership, plan the next immediate phase around the first durable story/source workflow and the job boundary the future agents will consume.