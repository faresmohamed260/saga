# S.A.G.A. v2 Phase 1 — Closed-Demo Main Site, Accounts & Invitations

**Status:** COMPLETE — deterministic implementation, hosted Supabase/Auth/email, real invitation acceptance/later sign-in, suspension/reactivation, and invitation revocation are validated.

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

## Phase 1E Hosted Auth / Email / Live-Proof Gate — Complete

The hosted gate is validated against the dedicated S.A.G.A. providers and public production origin.

Verified:

- Auth Site URL is `https://saga-pi-two.vercel.app`;
- redirect allowlist contains only the stable production alias plus future `https://saga.faresuniform.uk/**`;
- public self-signup remains disabled;
- custom Resend SMTP is active on the verified `mail.saga.faresuniform.uk` sending domain;
- first trusted admin bootstrap exists;
- real admin API invitation delivery reached mail infrastructure;
- the delivered token-hash confirmation link passed through production `/auth/confirm`;
- matching S.A.G.A. invitation claim established an active member;
- the actual Set Password surface established credentials and entered `/home`;
- a fresh later browser session signed in successfully using those credentials;
- a valid Auth session lost private access immediately when product status changed to suspended and regained access after reactivation;
- authenticated pending-invitation revocation returned and persisted `revoked` with `revoked_at`;
- all disposable proof identities and product rows were cleaned up and independently verified absent.

Live evidence:

- access/suspension/reactivation run `34647243289` — exact head `2b230f77e9ff6c0a582bc46f55d456c5a8690eb1`;
- invitation delivery/acceptance/later sign-in run `34647592382` — exact head `ee7fa83320dfcc0e152f1334c84f957cf55f0e7e`;
- invitation revocation run `34647880892` — exact head `62f184dcb763059382e9c6907bed6d398542cd3d`.

Detailed evidence: `docs/validation/PHASE_V2_1_HOSTED_E2E_2026-09-11.md`.

The scoped B2 runtime key remains deferred until an object-upload product flow activates. The final custom domain remains separately tracked and is not required for the working closed-demo production alias.

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
- **1E hosted Auth/email/live proof — COMPLETE:** runtime secrets, closed Auth config, verified email, real invite acceptance/later sign-in, suspension/reactivation, and revocation

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
| Hosted invitation delivery | real inbox/provider delivery test | **validated — run `34647592382`** |
| Hosted invite acceptance/sign-in | live end-to-end test | **validated — run `34647592382`** |
| Hosted suspension/revocation | live hosted behavior | **validated — runs `34647243289` and `34647880892`** |

## External Dependencies / Blockers

There is no remaining Phase 1 hosted blocker.

Completed during Phase 1:

- dedicated S.A.G.A.-owned Supabase project and active v2 schema;
- Auth Site URL / redirect configuration and closed public signup;
- verified custom Resend SMTP sender/domain;
- privileged runtime secret wiring;
- trusted initial admin bootstrap;
- real invitation delivery, acceptance, password setup, private access, and later sign-in;
- hosted suspension/reactivation and pending-invitation revocation;
- obsolete Vercel `studio` Git integration disconnected;
- owner-authorized manual-only Vercel deployment policy.

Deferred beyond Phase 1:

- final custom domain `saga.faresuniform.uk`;
- scoped B2 runtime key when source/object upload becomes active;
- application job-control and agentic AI runtime work, which requires a new phase contract.

Do not reuse RenderLab/Studio Supabase or shared R2 state for S.A.G.A.

## Explicitly Out of Scope for Phase 1

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

## Exit Criteria — Satisfied

Phase 1 closes with all contract exit criteria satisfied:

1. Phase-1 contracts are authoritative — **satisfied**;
2. S.A.G.A.-owned schema is applied to a dedicated hosted S.A.G.A. Supabase project — **satisfied**;
3. public self-signup remains absent — **satisfied**;
4. invite confirmation + credential setup + later sign-in work end-to-end — **satisfied**, run `34647592382`;
5. private routes require a fresh verified identity + active S.A.G.A. account — **satisfied**;
6. suspended/unknown identities fail closed — **satisfied**, including hosted suspension run `34647243289`;
7. active admins can create/revoke invitations and manage bounded role/status — **satisfied**, including hosted revoke run `34647880892`;
8. at least one real invitation email is delivered and accepted — **satisfied**, run `34647592382`;
9. private application shell and initial narrative IA are responsive — **satisfied** by Phase 1D/1E rendered evidence;
10. no privileged credentials/tokens leak to browser, repository, or logs — **satisfied** by structural boundaries and secret-bound hosted proof;
11. exact-head CI and rendered/accessibility review pass — **satisfied** for implementation heads; completion reconciliation receives its own exact-head CI before merge;
12. `PROJECT.md` records the hosted proof and next phase from verified reality — **satisfied by the Phase 1 completion reconciliation**.

## Next-Phase Direction

Phase 1 is complete. Do not begin broad Phase 2 implementation directly from this document.

The next repository step is contract-first:

1. create a fresh Phase 2 contract/governance branch from current `main`;
2. define the immediate application job-control / agentic-runtime foundation only to the detail justified by Phase 1 evidence;
3. specify ownership, persistence/job lifecycle, authorization, failure/retry semantics, observability/UI state, provider/runtime boundaries, validation, and deployment implications;
4. validate and merge that Phase 2 contract;
5. only then begin Phase 2 production implementation on a fresh implementation branch.

The contract should preserve the web-first rule: future agents operate behind S.A.G.A.-owned application/job contracts rather than becoming the top-level product architecture.
