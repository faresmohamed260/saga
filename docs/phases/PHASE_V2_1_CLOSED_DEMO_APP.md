# S.A.G.A. v2 Phase 1 — Closed-Demo Main Site, Accounts & Invitations

**Status:** ACTIVE — 1A COMPLETE; 1B COMPLETE; 1C COMPLETE; 1D COMPLETE; 1E NEXT

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
- durable validation: `docs/validation/PHASE_V2_1B_ACCOUNT_ACCESS_2026-09-11.md`

Phase 1C auth/access surfaces:

- PR #156
- exact PR head `7bc81877a55af9b47b6bbc96abd7a17e9100fda3`
- merge commit `319b785e43a169b4ffd7b57cd5be32ad3ef5da67`
- exact-head `SAGA v2 Web CI`, `Required Check Compatibility`, and `Backend Architecture CI` all succeeded before merge
- durable validation: `docs/validation/PHASE_V2_1C_AUTH_ACCESS_2026-09-11.md`

Phase 1D Narrative Desk shell / first product surfaces:

- approved UI concept: PR #158
- concept merge commit `418e1d5d446c931bfba83170147307727378b664`
- implementation PR #160
- exact PR head `8ad0a7eb3bffa3aed394ea86eff562f837239b14`
- implementation merge commit `f558a282b4743a15d440eada1c6a7ccefe44215c`
- exact-head `SAGA v2 Web CI`, `Required Check Compatibility`, `Backend Architecture CI`, and `SAGA v2 Visual Review` all succeeded before merge
- durable validation: `docs/validation/PHASE_V2_1D_NARRATIVE_DESK_2026-09-11.md`

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

RenderLab is read-only reference material for process/setup/UI patterns only. Do not modify it and do not copy its product code, routes, schema/table names, branding, visual composition, credentials, data, storage, deployments, or resources.

S.A.G.A.-owned translations are authoritative:

- `docs/v2/FRONTEND_ARCHITECTURE.md`
- `docs/v2/UI_SYSTEM.md`
- `docs/v2/ACCESS_AND_INVITATIONS.md`
- `docs/v2/PHASE_1D_UI_CONCEPT.md`

## Phase 1B — Complete Foundation

The active v2 Supabase migration lineage is `apps/web/supabase/migrations/`; the historical root `supabase/migrations/` tree is not the v2 bootstrap source.

Merged account/access behavior includes:

- `saga_account_access` keyed by verified Supabase Auth user ID;
- role `member | admin` and status `active | suspended`;
- `saga_invitations` keyed by normalized email intent with `pending | accepted | revoked | expired` lifecycle;
- no reusable raw Auth invite token, OTP, password, or equivalent credential material;
- forced RLS on privileged tables with browser-role table privileges revoked;
- service-role-only privileged persistence access;
- transactional invitation claim that reloads verified identity/email server-side;
- fresh `auth.getUser()` verification;
- server-only privileged Supabase client;
- bounded account resolver states;
- active-admin authorization helper.

Exact PR #153 validation:

- `SAGA v2 Web CI` run `34593615395` — success
- `Required Check Compatibility` run `34593615380` — success
- `Backend Architecture CI` run `34593615394` — success

## Phase 1C — Complete Auth / Access Slice

Merged through PR #156.

Implemented:

- invitation-only sign-in with no public signup path;
- server invitation confirmation using supported Supabase invite token-hash verification;
- transactional invitation claim after fresh Auth verification;
- session-bound password setup/change;
- sign-out;
- Next.js 16 `proxy.ts` SSR cookie/session refresh;
- protected route-group layout using fresh identity plus S.A.G.A. account resolution;
- safe same-origin redirects;
- deterministic auth/access tests;
- bounded unauthenticated, not-admitted, suspended, active, and unavailable states;
- provider/config failures that fail closed.

Exact PR #156 validation:

- `SAGA v2 Web CI` run `34601422907` — success
- `Required Check Compatibility` run `34601422970` — success
- `Backend Architecture CI` run `34601422837` — success

Hosted email delivery remains outside deterministic proof until Phase 1E hosted integration is explicitly configured and tested.

## Phase 1D — Complete Application Shell / First Product Surfaces

The approved **Narrative Desk** concept is implemented through PR #160.

Implemented:

- authenticated application shell behind the existing Phase 1C access boundary;
- persistent desktop global rail;
- narrow/mobile top bar and Radix-backed modal navigation sheet;
- Home;
- Library with honest empty state;
- Projects with honest empty state;
- bounded Settings/session surface;
- graphite/warm-neutral/iris private-workspace tokens;
- active-route `aria-current` semantics;
- keyboard/Escape/focus-restoration behavior;
- touch-sized narrow controls;
- portal-safe theme inheritance for Radix content;
- reduced-motion behavior;
- exact-head production Chromium desktop/narrow rendered validation;
- no fabricated domain state or generic admin-dashboard/card-grid fallback.

Exact PR #160 validation:

- `SAGA v2 Web CI` run `34609975376` — success
- `Required Check Compatibility` run `34609975375` — success
- `Backend Architecture CI` run `34609975398` — success
- `SAGA v2 Visual Review` run `34609975429` — success

Rendered evidence artifact `10267703757` and its digest are recorded in the Phase 1D validation document.

## Target Route Boundary

Route groups may separate public/auth/app layouts without leaking those group names into URLs.

```text
/                         public landing/brand
/sign-in                  public sign-in
/auth/confirm             server invitation confirmation
/set-password             confirmed/session-bound credential setup/change

/home                     private application home
/library                  private source/library workspace
/projects                 private project list
/projects/[projectId]     private project workspace later
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
- verified identity with no S.A.G.A. account -> denied / invitation-completion state, not auto-admitted;
- suspended account -> private product denied except bounded security/recovery/sign-out behavior;
- active member -> private product;
- active admin -> private product + admin operations;
- browser/user metadata never supplies authorization role.

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

## Active Next Slice — Phase 1E

### 1E — Admin invitation/account operations

Implement the narrow private admin surface over S.A.G.A.-owned state only:

- pending invitations;
- S.A.G.A.-known accounts only;
- create/revoke/retry-safe invitation state handling;
- account role/status mutation;
- self-lockout and last-admin protections where applicable;
- sanitized operational feedback;
- active-admin-only server authorization for every mutation/read;
- deterministic database/service/API/UI tests;
- responsive/accessibility/rendered evidence using the existing Narrative Desk system.

Do not expose the whole shared `auth.users` directory as product data.

The deterministic repository implementation can proceed without hosted provider setup.

### 1E hosted operational gate

After the deterministic admin slice is stable, configure and verify only with explicit external-resource authorization:

- dedicated S.A.G.A. Supabase project and schema application;
- Site URL and redirect allowlist;
- invite/recovery templates using supported confirmation variables;
- custom SMTP or equivalent Auth email hook;
- sender-domain authentication and acceptable rate limits;
- at least one real bounded invitation delivered to an inbox and accepted;
- scoped non-master B2 runtime credentials when product object-storage flow actually needs them.

Supabase project creation through the connected tool requires explicit organization selection and cost confirmation. A generic “keep going” does not authorize that external resource creation.

## UI/UX Contract

Primary principle: **Narrative first, complexity on demand.**

Core rules:

- maintained accessible controls before custom mechanics;
- story/source/evidence/entity/timeline content dominates chrome;
- progressive disclosure for advanced controls;
- no generic card-grid solution for every page;
- desktop productivity is primary, while narrow access remains coherent and touch-friendly;
- keyboard/focus semantics are required;
- no hover-only essential behavior;
- meaningful motion only, with reduced-motion/static equivalents;
- rendered fidelity review is separate from functional CI.

Phase 1D established the approved Narrative Desk shell and visual language. Phase 1E Admin should extend that system rather than inventing a second application style.

## Phase Slices

### 1A — Contract / architecture / UI governance — COMPLETE

Merged through PR #152.

### 1B — Account/invitation persistence + server authorization — COMPLETE

Merged through PR #153.

### 1C — Auth/invite/password surfaces — COMPLETE

Merged through PR #156.

### 1D — Application shell / first product surfaces — COMPLETE

Concept approved through PR #158 and implementation merged through PR #160 with functional and rendered exact-head evidence.

### 1E — Admin invitation/account operations + hosted integration — NEXT

Implement deterministic admin APIs/UI first, then complete hosted Supabase/email proof under the explicit external-resource gate.

Later slices do not silently change earlier contracts without updating authoritative docs.

## Validation Matrix

| Claim | Required evidence | Current state |
|---|---|---|
| Phase contract current | docs/PROJECT/DECISIONS review | current through Phase 1D; 1E next |
| No public signup | structural/API/UI tests | validated through 1D; continue every slice |
| Private route denial | deterministic auth/access tests | validated in Phase 1C |
| Suspended/unknown denial | deterministic account/route tests | validated in Phase 1C |
| Admin-only invitation mutation | fresh-auth + active-admin tests | server auth boundary exists; 1E APIs/UI next |
| Invite claim matches verified email | transactional integration test | validated in disposable Postgres |
| No raw invite token persistence | schema/structural test | validated |
| No privileged secret in browser | source/bundle structural checks | validated structural boundary; continue every slice |
| UI shell responsive | desktop + narrow production rendered evidence | validated in Phase 1D |
| Shell keyboard/focus/touch behavior | Chromium interaction review | validated in Phase 1D |
| Reduced motion | rendered/computed-style validation | validated in Phase 1D |
| Admin UI accessible | keyboard/focus/touch/rendered review | pending 1E |
| Hosted invitation delivery | explicit live inbox test | pending 1E hosted gate |
| Merge safety | exact-head v2 CI + relevant rendered checks | Phase 1D passed |

## External Dependencies / Blockers

Not blockers for deterministic Phase 1E repository work:

- new S.A.G.A.-owned Supabase project;
- custom SMTP/email hook;
- scoped B2 runtime application key.

They become blockers only for hosted/end-to-end or object-storage slices that actually need them.

The connected historical Vercel project still points at retired `apps/studio`; do not treat its failed previews as current v2 evidence or silently repurpose it.

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

Do not design or implement the agentic AI phase yet.

The immediate next work is **Phase 1E deterministic Admin invitation/account operations**, followed by the explicitly authorized hosted Supabase/email acceptance proof needed to close Phase 1.