# S.A.G.A. v2 Phase 1 — Closed-Demo Main Site, Accounts & Invitations

**Status:** ACTIVE — 1A COMPLETE; 1B COMPLETE; 1C COMPLETE; 1D COMPLETE; 1E DETERMINISTIC ADMIN COMPLETE; DEDICATED HOSTED SUPABASE + ACTIVE V2 SCHEMA COMPLETE; AUTH/EMAIL/LIVE INVITATION PROOF PENDING

**Tracking:** #151

## Goal

Turn the Phase-0 web foundation into the first real S.A.G.A. v2 application: a closed invite-only demo with account/session boundaries, email invitations, admin access management, and a production-quality narrative workspace shell.

Phase 1 establishes the product/app/auth/UI contracts that the future AI system will operate behind.

## User Value

An invited demo user should be able to:

1. receive a S.A.G.A. invitation email;
2. confirm it through the supported Auth flow;
3. establish credentials;
4. sign in later;
5. reach the private S.A.G.A. workspace;
6. browse the first application information architecture without seeing internal provider/pipeline complexity.

An active S.A.G.A. admin should be able to invite users, revoke pending invitations, inspect S.A.G.A.-owned account state, suspend/reactivate accounts, and manage roles without relying on browser metadata.

## Merged Evidence

Phase 0 web foundation:

- PR #149
- merge `261b75ff2a60dfcada681af6b6c918c1ff5e3366`

Phase 1 contract/governance:

- PR #152
- merge `55beaccab011a4c5337db86dd88b52f6d48734c4`

Phase 1B account/access foundation:

- PR #153
- exact head `e81915942ba9e859c79898ec60fdda38a56235d3`
- merge `5d5b59d17d2bd2f9a5769d2e5c4f9a2b43d1bad9`
- validation: `docs/validation/PHASE_V2_1B_ACCOUNT_ACCESS_2026-09-11.md`

Phase 1C auth/access surfaces:

- PR #156
- exact head `7bc81877a55af9b47b6bbc96abd7a17e9100fda3`
- merge `319b785e43a169b4ffd7b57cd5be32ad3ef5da67`
- validation: `docs/validation/PHASE_V2_1C_AUTH_ACCESS_2026-09-11.md`

Phase 1D Narrative Desk:

- approved concept PR #158, merge `418e1d5d446c931bfba83170147307727378b664`
- implementation PR #160
- exact head `8ad0a7eb3bffa3aed394ea86eff562f837239b14`
- merge `f558a282b4743a15d440eada1c6a7ccefe44215c`
- validation: `docs/validation/PHASE_V2_1D_NARRATIVE_DESK_2026-09-11.md`

Phase 1E deterministic Admin operations:

- PR #162
- exact head `79929e2c90750c8832025bc57768917edae16f54`
- merge `39dceaf1254ed7616ed1bd9eb640d9d622a73812`
- validation: `docs/validation/PHASE_V2_1E_ADMIN_OPERATIONS_2026-09-11.md`

Phase 1E hosted Supabase foundation:

- dedicated hosted project created with explicit owner/cost approval
- validation: `docs/validation/PHASE_V2_1E_HOSTED_SUPABASE_2026-09-11.md`

## Owner Constraint — Closed Demo

S.A.G.A. v2 is not open signup.

- Public self-signup is disabled.
- Account admission begins with an admin invitation email.
- Supabase Auth is identity/session authority.
- S.A.G.A. owns product role/status/invitation state.
- Private product routes require a fresh verified identity plus active S.A.G.A. account access.
- Admin operations require a fresh active S.A.G.A. admin.
- Service-role/Auth Admin credentials never enter browser code.

## RenderLab Boundary

RenderLab is read-only reference material for process/setup/UI patterns only. Do not modify it and do not copy its product code, routes, schema/table names, branding, credentials, data, storage, deployments, or resources.

Authoritative S.A.G.A.-owned translations:

- `docs/v2/FRONTEND_ARCHITECTURE.md`
- `docs/v2/UI_SYSTEM.md`
- `docs/v2/ACCESS_AND_INVITATIONS.md`
- `docs/v2/PHASE_1D_UI_CONCEPT.md`

## Phase 1B — Complete Foundation

Implemented and validated:

- active v2 migration lineage under `apps/web/supabase/migrations/`;
- product-owned `saga_account_access` and `saga_invitations` state;
- forced RLS and revoked browser privileges;
- service-role-only invitation claim using verified Auth identity/email;
- fresh server `auth.getUser()` boundary;
- bounded account resolver states;
- active-admin authorization helper;
- disposable-Postgres migration/database-contract CI.

Exact PR #153 checks:

- Web CI `34593615395` — success
- compatibility `34593615380` — success
- backend architecture `34593615394` — success

## Phase 1C — Complete Auth / Access

Implemented and validated:

- invitation-only sign-in; no public signup;
- supported server invite-confirm flow;
- transactional S.A.G.A. invitation claim after fresh Auth verification;
- session-bound password setup/change;
- sign-out;
- SSR Supabase cookie/session refresh through Next.js 16 `proxy.ts`;
- protected private route-group boundary;
- safe same-origin redirects;
- bounded unauthenticated/not-admitted/suspended/active/unavailable states;
- fail-closed provider/config handling.

Exact PR #156 checks:

- Web CI `34601422907` — success
- compatibility `34601422970` — success
- backend architecture `34601422837` — success

## Phase 1D — Complete Narrative Desk

Implemented and validated:

- authenticated Narrative Desk shell;
- desktop global rail;
- narrow/mobile top bar and modal navigation sheet;
- Home, Library, Projects, bounded Settings;
- honest empty states;
- keyboard/focus/touch semantics;
- portal-safe Radix theming;
- reduced motion;
- production Chromium desktop/narrow evidence.

Exact PR #160 checks:

- Web CI `34609975376` — success
- compatibility `34609975375` — success
- backend architecture `34609975398` — success
- visual review `34609975429` — success

## Phase 1E — Deterministic Admin Slice Complete

Merged through PR #162.

### Admin authorization and data scope

- every Admin read/mutation requires fresh active-admin authorization;
- account listings begin from S.A.G.A.-owned access rows;
- Auth email lookup occurs only for already-known S.A.G.A. user IDs;
- the whole shared Auth directory is never exposed as product data;
- privileged Supabase capability remains server-only.

### Invitation semantics

- normalized-email invitation intent creation is transactional;
- same-role pending retries reuse the existing intent;
- conflicting-role retries are rejected;
- already-admitted identities conflict with new invitation intent;
- provider email delivery is attempted only after durable S.A.G.A. intent exists;
- delivery failure is bounded and leaves retry/revoke-safe product state;
- pending invitations can be revoked transactionally;
- expired pending invitations settle to `expired`;
- accepted/revoked/otherwise settled invitations are non-mutating under revoke attempts;
- no raw reusable invite token is persisted or returned.

### Account mutation safety

- role/status mutation requires active-admin authorization;
- actor audit metadata is preserved;
- self-demotion/self-suspension is rejected;
- active-admin transitions are serialized;
- last-active-admin removal is rejected defensively.

### API/UI

- bounded invitation/account REST APIs;
- canonical UUID-shape validation at Admin path boundaries;
- server actions for the Admin product surface;
- Admin navigation derived from server-resolved role;
- responsive Narrative Desk `/admin` UI;
- current-admin destructive controls omitted in UI;
- sanitized operational feedback;
- approximately 44 px narrow control targets.

### Exact-head evidence

All succeeded on exact PR #162 head `79929e2c90750c8832025bc57768917edae16f54`:

- `SAGA v2 Web CI` run `34612667218`
- `Required Check Compatibility` run `34612667253`
- `Backend Architecture CI` run `34612667248`
- `SAGA v2 Visual Review` run `34612667245`

Visual artifact:

- ID `10268954015`
- digest `faaa0bf2bcaef691e24a33df8488c79c00cdaa6bf6b1ff91b418deb4c3f9df50`

## Phase 1E — Hosted Supabase Foundation Complete

The owner explicitly selected the **Fares Home Lab** organization, approved a **new** S.A.G.A. project rather than reusing `AI Studio`, selected `eu-central-1` (Frankfurt), and approved the Supabase-reported **$0/month** project cost.

Created project:

- name: `S.A.G.A.`
- project ref/id: `scmeqnpmhomzcwecjdtu`
- organization id: `imbicfntoeaqubhdcnpe`
- region: `eu-central-1`
- API URL: `https://scmeqnpmhomzcwecjdtu.supabase.co`
- status after creation: `ACTIVE_HEALTHY`

The exact active repository migration lineage was applied to the new project in order and all three applications succeeded:

1. `closed_demo_account_access`
2. `admin_operations`
3. `admin_operation_hardening`

Hosted migration history was then re-read and matched that order.

Security advisors reported only two informational `rls_enabled_no_policy` findings on the deliberately server-only privileged tables. Those tables enable/force RLS and revoke browser-role access by design. Performance advisors reported only informational FK-index suggestions and one unused-index notice on the new empty project.

No API key or privileged secret is committed to repository documentation.

Detailed evidence: `docs/validation/PHASE_V2_1E_HOSTED_SUPABASE_2026-09-11.md`.

## Target Route Boundary

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

Routes beyond the implemented slice are information-architecture direction, not a promise that every route ships immediately.

## Authorization Model

```text
request/session
  -> SSR Auth cookie maintenance
  -> fresh server Supabase Auth identity verification
  -> S.A.G.A. account-access lookup
  -> role/status decision
  -> owner/admin-scoped product operation
```

Rules:

- anonymous -> sign-in boundary;
- verified Auth identity without S.A.G.A. access -> denied, not auto-admitted;
- suspended account -> private/admin denied except bounded security/recovery/sign-out behavior;
- active member -> private product, no Admin;
- active admin -> private product + Admin;
- browser/user metadata never supplies authorization role or actor ID.

## Invitation Flow

```text
active admin
  -> create invitation(email, role)
  -> normalize + validate email
  -> persist/reuse pending S.A.G.A. intent
  -> request Supabase Auth invite email server-side
  -> recipient opens supported confirmation link
  -> server verifies Auth invitation
  -> fresh verified identity/email
  -> transactional claim of matching eligible S.A.G.A. invitation
  -> active S.A.G.A. account established
  -> credential setup / private app
```

If outbound email fails, the product surfaces bounded delivery failure while preserving deterministic retry/revoke state.

## Remaining Phase 1E Hosted Auth / Email / Live-Proof Gate

The dedicated hosted project and database schema now exist. Phase 1 remains open because these hosted claims are still unproven:

- S.A.G.A. Site URL and redirect allowlist;
- invite/recovery templates using supported variables;
- production-capable custom SMTP or equivalent Auth email hook;
- authenticated sender domain and acceptable rate limits;
- deployed runtime wiring to the dedicated S.A.G.A. project, including privileged server credentials through a secret boundary;
- first trusted S.A.G.A. admin bootstrap;
- actual inbox delivery;
- invite click -> confirmation -> claim -> password setup -> later sign-in;
- hosted suspension/revocation behavior;
- scoped non-master B2 runtime credentials when object-storage flow becomes active.

The connected Supabase integration used for the hosted database foundation does not expose service-role secret retrieval or Auth Site URL/template/SMTP mutation controls. Do not invent those settings or claim they are configured.

## UI/UX Contract

Primary principle: **Narrative first, complexity on demand.**

- maintained accessible controls before custom mechanics;
- user/domain content dominates chrome;
- no generic card-grid solution for every page;
- desktop productivity primary, narrow access coherent/touch-friendly;
- keyboard/focus semantics required;
- no hover-only essential behavior;
- meaningful motion only, with reduced-motion equivalents;
- rendered fidelity review separate from functional CI.

Phase 1E Admin extends the approved Narrative Desk system rather than inventing a second application style.

## Phase Slices

- **1A — COMPLETE:** contract / architecture / UI governance
- **1B — COMPLETE:** account/invitation persistence + server authorization
- **1C — COMPLETE:** auth/invite/password surfaces
- **1D — COMPLETE:** Narrative Desk shell / first product surfaces
- **1E deterministic Admin — COMPLETE:** Admin APIs/UI/database safeguards/rendered evidence
- **1E hosted Supabase foundation — COMPLETE:** dedicated project + active v2 schema + advisor review
- **1E hosted Auth/email/live proof — PENDING:** runtime secrets, Auth config, email, real invite acceptance/sign-in

## Validation Matrix

| Claim | Required evidence | Current state |
|---|---|---|
| No public signup | structural/API/UI tests | validated; continue guarding |
| Private route denial | deterministic auth/access tests | validated in 1C |
| Suspended/unknown denial | deterministic account/route tests | validated in 1C |
| Admin-only reads/mutations | fresh-auth + active-admin tests | validated in 1E deterministic slice |
| Retry-safe invitation intent | disposable-Postgres contract | validated in 1E |
| Settled invitation revoke is non-mutating | disposable-Postgres hardening contract | validated in 1E |
| Self/last-admin protections | database/structural tests | validated in 1E |
| Dedicated hosted S.A.G.A. Supabase | explicit creation result | validated |
| Active v2 schema on hosted project | hosted migration history | validated |
| Hosted schema advisor review | Supabase security/performance advisors | validated; informational findings only |
| No raw invite token persistence | schema/structural tests | validated |
| No privileged secret in browser | architecture/source checks | validated structural boundary |
| Narrative Desk responsive | production desktop+narrow render | validated in 1D |
| Admin responsive/accessibility | production desktop+narrow interaction/render | validated in 1E |
| Reduced motion | computed-style render validation | validated |
| Hosted invitation delivery | real inbox test | **pending** |
| Hosted invite acceptance/sign-in | live end-to-end test | **pending** |
| Hosted suspension/revocation | live hosted behavior | **pending** |

## External Dependencies / Blockers

Completed:

- dedicated S.A.G.A.-owned Supabase project;
- active v2 schema application.

Remaining blockers to **Phase 1 end-to-end completion**:

- hosted Auth Site URL/redirect/template configuration;
- custom SMTP/email hook and sender configuration;
- runtime/deployment privileged secret wiring;
- trusted initial admin bootstrap;
- real hosted invite acceptance/sign-in proof;
- hosted suspension/revocation proof;
- scoped B2 runtime key when object upload becomes active;
- deployment ownership decision for the stale Vercel project still pointing at retired `apps/studio`.

Do not reuse RenderLab/Studio Supabase or shared R2 state for S.A.G.A.

## Explicitly Out of Scope While Phase 1 Is Open

- agentic AI/LLM orchestration;
- identity/coreference/canon extraction runtime;
- generation planning/narrative generation;
- live visual/audio model execution;
- public signup/request-access product;
- social login unless separately approved;
- billing/subscriptions;
- organization/team multi-tenancy;
- copying/modifying RenderLab;
- claiming production/email readiness before hosted proof.

## Exit Criteria

Phase 1 closes only when:

1. Phase-1 contracts are authoritative;
2. S.A.G.A.-owned schema is applied to a dedicated hosted S.A.G.A. Supabase project — **complete**;
3. public self-signup remains absent;
4. invite confirmation + credential setup + later sign-in work end-to-end;
5. private routes require fresh verified identity + active S.A.G.A. account;
6. suspended/unknown identities fail closed;
7. active admins can create/revoke invitations and manage bounded role/status;
8. at least one real invitation email is delivered and accepted;
9. private application shell and initial narrative IA are responsive;
10. no privileged credentials/tokens leak to browser, repository, or logs;
11. exact-head CI and rendered/accessibility review pass;
12. `PROJECT.md` records the hosted proof and next phase from verified reality.

## Next-Phase Direction

Do not design or implement the agentic AI phase yet.

The immediate remaining work is the **hosted Auth/email/runtime-secret/live invitation acceptance proof** required to close Phase 1.
