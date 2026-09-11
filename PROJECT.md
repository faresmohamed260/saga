# S.A.G.A. Project

S.A.G.A. is being rebuilt as a web-first storytelling intelligence platform. The product goals remain: ingest books/stories, reconstruct evidence-backed canon, model characters/worlds/timelines, support narrative generation, and eventually produce grounded visual/audio/story outputs. The architecture is intentionally new.

This file is the short source-of-truth handoff for the active rebuild.

## Active Product Direction — S.A.G.A. v2

The owner authorized a fresh rebuild on 2026-09-11.

**Same goals and feature set; different architecture.**

The old contract-driven Python/nine-stage production architecture is **S.A.G.A. v1 historical/reference material**. v2 may reuse requirements, algorithms, evaluations, schemas, prompts, and lessons, but it does not preserve the old runtime architecture for compatibility.

The rebuild order remains:

1. main web product frontend/backend;
2. account/auth/data/storage/job/deployment contracts;
3. new agentic AI subsystem behind those product contracts;
4. progressive restoration of S.A.G.A. intelligence/generation capabilities.

## Merged Baselines

Phase 0 web foundation:

- PR **#149**
- merge commit `261b75ff2a60dfcada681af6b6c918c1ff5e3366`

Phase 1 closed-demo contract/governance:

- PR **#152**
- merge commit `55beaccab011a4c5337db86dd88b52f6d48734c4`

Phase 1B account/access foundation:

- PR **#153**
- exact PR head `e81915942ba9e859c79898ec60fdda38a56235d3`
- merge commit `5d5b59d17d2bd2f9a5769d2e5c4f9a2b43d1bad9`
- exact-head Web CI, compatibility, and backend architecture checks succeeded

Phase 1C auth/access surfaces:

- PR **#156**
- exact PR head `7bc81877a55af9b47b6bbc96abd7a17e9100fda3`
- merge commit `319b785e43a169b4ffd7b57cd5be32ad3ef5da67`
- exact-head Web CI, compatibility, and backend architecture checks succeeded

Phase 1D Narrative Desk shell / first product surfaces:

- approved concept PR **#158**, merge `418e1d5d446c931bfba83170147307727378b664`
- implementation PR **#160**
- exact PR head `8ad0a7eb3bffa3aed394ea86eff562f837239b14`
- merge commit `f558a282b4743a15d440eada1c6a7ccefe44215c`
- exact-head Web CI, compatibility, backend architecture, and production visual review succeeded

Phase 1E deterministic Admin operations:

- PR **#162**
- exact PR head `79929e2c90750c8832025bc57768917edae16f54`
- merge commit `39dceaf1254ed7616ed1bd9eb640d9d622a73812`
- exact-head `SAGA v2 Web CI`, `Required Check Compatibility`, `Backend Architecture CI`, and `SAGA v2 Visual Review` all succeeded before merge

Phase 1E deterministic handoff:

- PR **#163**
- merge commit `c274f1d26914edf62e30cfd2ef23222df6a8503f`

Phase 0 issue **#148** is closed. Phase 1 is tracked by **#151**.

Durable validation evidence:

- Phase 1B: `docs/validation/PHASE_V2_1B_ACCOUNT_ACCESS_2026-09-11.md`
- Phase 1C: `docs/validation/PHASE_V2_1C_AUTH_ACCESS_2026-09-11.md`
- Phase 1D: `docs/validation/PHASE_V2_1D_NARRATIVE_DESK_2026-09-11.md`
- Phase 1E Admin: `docs/validation/PHASE_V2_1E_ADMIN_OPERATIONS_2026-09-11.md`
- Phase 1E hosted Supabase foundation: `docs/validation/PHASE_V2_1E_HOSTED_SUPABASE_2026-09-11.md`
- Phase 1 hosted end-to-end completion: `docs/validation/PHASE_V2_1_HOSTED_E2E_2026-09-11.md`

## Active Phase

**S.A.G.A. v2 Phase 1 — Closed-Demo Main Site, Accounts & Invitations**

Contract: `docs/phases/PHASE_V2_1_CLOSED_DEMO_APP.md`

Status: **COMPLETE — deterministic repository slices, hosted Supabase/Auth/email, real invitation lifecycle, later sign-in, suspension/reactivation, and invitation revocation are validated.**

### Phase 1A — complete

Closed-demo account/frontend/UI contract merged through PR #152.

### Phase 1B — complete

Implemented and validated:

- isolated active v2 database lineage under `apps/web/supabase/migrations/`;
- `saga_account_access` and `saga_invitations` product-owned authorization/admission state;
- forced RLS and revoked browser privileges on privileged tables;
- service-role-only transactional invitation claim using verified Auth identity/email;
- fresh server identity verification;
- bounded account resolver states;
- active-admin authorization helper;
- disposable-Postgres migration/database-contract CI.

Exact PR #153 validation:

- Web CI `34593615395` — success
- compatibility `34593615380` — success
- backend architecture `34593615394` — success

### Phase 1C — complete

Implemented and validated:

- invitation-only sign-in with no public signup;
- server invitation confirmation through supported Supabase invite verification;
- invitation claim after fresh Auth verification;
- session-bound password setup/change and sign-out;
- Next.js 16 SSR Supabase cookie/session refresh via `proxy.ts`;
- protected private route-group layout backed by S.A.G.A. account resolution;
- bounded unauthenticated/not-admitted/suspended/active/unavailable routing;
- safe same-origin redirect normalization;
- provider/config failure fail-closed behavior.

Exact PR #156 validation:

- Web CI `34601422907` — success
- compatibility `34601422970` — success
- backend architecture `34601422837` — success

### Phase 1D — complete

The approved S.A.G.A.-specific **Narrative Desk** concept is implemented.

Validated behavior includes:

- authenticated Narrative Desk shell;
- persistent desktop global rail;
- accessible narrow/mobile top bar and modal navigation sheet;
- Home, Library, Projects, and bounded Settings surfaces;
- honest empty states with no fabricated domain data;
- private-workspace semantic tokens;
- active-route semantics;
- keyboard/Escape/focus restoration;
- portal-safe Radix theming;
- reduced-motion handling;
- production Chromium desktop/narrow evidence.

Exact PR #160 validation:

- Web CI `34609975376` — success
- compatibility `34609975375` — success
- backend architecture `34609975398` — success
- visual review `34609975429` — success

### Phase 1E deterministic Admin slice — complete

Merged through PR #162.

Implemented and validated:

- active-admin-only invitation/account reads and mutations;
- server-only transactional admin database routines;
- normalized-email retry-safe invitation intent creation;
- provider delivery attempted only after durable S.A.G.A. invitation intent exists;
- bounded delivery-failure state preserving safe retry/revoke behavior;
- pending invitation revoke and expiry settlement;
- settled invitations remain non-mutating under revoke attempts;
- S.A.G.A.-known account listing without Auth-directory enumeration;
- role/status mutation with actor audit metadata;
- self-demotion/self-suspension rejection;
- serialized last-active-admin defense;
- canonical UUID-shape validation at Admin API path boundaries;
- bounded REST Admin APIs and server actions;
- role-aware Admin navigation;
- responsive Narrative Desk `/admin` surface;
- current-admin self-destructive controls omitted in UI while database protection remains authoritative;
- approximately 44 px narrow touch targets;
- deterministic SQL/structural tests and production rendered Admin evidence.

Exact PR #162 validation:

- `SAGA v2 Web CI` run **34612667218** — success
- `Required Check Compatibility` run **34612667253** — success
- `Backend Architecture CI` run **34612667248** — success
- `SAGA v2 Visual Review` run **34612667245** — success

Rendered evidence artifact **10268954015**, digest `faaa0bf2bcaef691e24a33df8488c79c00cdaa6bf6b1ff91b418deb4c3f9df50`.

### Phase 1E hosted Supabase foundation — complete

The owner explicitly authorized a new dedicated hosted Supabase project in the existing **Fares Home Lab** organization after Supabase reported the project cost as **$0/month**.

Created hosted project:

- name: `S.A.G.A.`
- project ref/id: `scmeqnpmhomzcwecjdtu`
- organization id: `imbicfntoeaqubhdcnpe`
- region: `eu-central-1` (Frankfurt)
- API URL: `https://scmeqnpmhomzcwecjdtu.supabase.co`
- project status after creation: `ACTIVE_HEALTHY`

The existing `AI Studio` Supabase project was **not reused or modified**.

Hosted database work completed:

- project began with no application migrations;
- exact active repository migration lineage was read from `apps/web/supabase/migrations/` and applied in order;
- `closed_demo_account_access` — success;
- `admin_operations` — success;
- `admin_operation_hardening` — success;
- hosted migration history was re-read and confirmed in that order;
- Supabase security advisors reported only expected informational `rls_enabled_no_policy` notices on the two deliberately server-only privileged tables;
- performance advisors reported only informational FK-index suggestions and an unused-index notice on the new empty project.

No publishable or privileged API key value is stored in repository documentation. The connected Supabase integration exposes a modern publishable key, but does not expose a service-role secret or hosted Auth configuration mutation surface.

Detailed evidence: `docs/validation/PHASE_V2_1E_HOSTED_SUPABASE_2026-09-11.md`.

### Phase 1E hosted Auth/email/end-to-end gate — complete

Hosted Phase 1 behavior is now validated against the dedicated S.A.G.A. providers and public production origin:

- Supabase Auth Site URL restored to `https://saga-pi-two.vercel.app`;
- redirect allowlist restricted to the stable production alias plus future `https://saga.faresuniform.uk/**`;
- public self-signup remains disabled;
- verified Resend SMTP sender/domain is active;
- the first trusted owner/admin is bootstrapped and active;
- a clean disposable-user proof exercised the real admin invitation API, real Resend delivery, `/auth/confirm`, transactional S.A.G.A. claim, actual Set Password form, private `/home`, and later sign-in from a new browser session;
- a separate hosted proof verified active `/home` access, suspended-account denial, and reactivation;
- a separate hosted proof verified authenticated pending-invitation revocation and persisted `revoked_at`;
- all disposable users/access rows/invitations were independently verified cleaned up;
- temporary privileged proof workflows were removed from their ops branches and never merged to `main`.

Live proof runs:

- hosted password session + suspension/reactivation: `34647243289` on exact head `2b230f77e9ff6c0a582bc46f55d456c5a8690eb1`;
- normal invitation delivery/acceptance/later sign-in: `34647592382` on exact head `ee7fa83320dfcc0e152f1334c84f957cf55f0e7e`;
- hosted pending-invitation revocation: `34647880892` on exact head `62f184dcb763059382e9c6907bed6d398542cd3d`.

Detailed evidence: `docs/validation/PHASE_V2_1_HOSTED_E2E_2026-09-11.md`.

A scoped non-master B2 runtime key remains intentionally deferred until a product object-upload flow actually activates; it is not a Phase 1 blocker.

## Closed-Demo Product Constraint

S.A.G.A. v2 is a **closed demo**.

- No public self-signup.
- Supabase Auth owns identity/session mechanics.
- S.A.G.A. owns product admission, role, status, and invitation lifecycle.
- Access begins with an admin-created invitation.
- Private routes require a fresh verified identity plus active S.A.G.A. access.
- Admin operations are server-only and fresh-active-admin authorized.
- Service-role/Auth Admin credentials never enter browser code.
- Hosted invitation email delivery and acceptance are end-to-end validated; future provider/domain changes require revalidation.

Detailed contract: `docs/v2/ACCESS_AND_INVITATIONS.md`.

## Adopted v2 Stack

- **GitHub** — source of truth, review, CI, durable continuity
- **Vercel** — primary web deployment target
- **Next.js 16 + React 19 + TypeScript** — frontend and request-bounded backend/API
- **Tailwind CSS + maintained accessible primitives + Motion** — UI system
- **Supabase** — Postgres, Auth, Realtime, structured application records
- **Cloudflare** — DNS/CDN/security where useful, not S.A.G.A. object storage
- **Backblaze B2** — dedicated private object storage
- **future agentic runtime** — next-phase candidate behind application-owned job/runtime contracts; not yet implemented

The active v2 application lives under `apps/web/`.

## RenderLab Reference Boundary

`faresmohamed260/renderlab` is a separate product and read-only reference for process/architecture/UI conventions only.

Do not modify RenderLab during S.A.G.A. work. Do not copy its product code, visual identity, routes, schema/table names, credentials, storage, deployments, product data, or assumptions.

Authoritative S.A.G.A. translations:

- `docs/v2/FRONTEND_ARCHITECTURE.md`
- `docs/v2/UI_SYSTEM.md`
- `docs/v2/ACCESS_AND_INVITATIONS.md`

## Storage Foundation — VALIDATED

Backblaze B2 is the v2 object store. GitHub Actions run `34537566675` authorized B2, created/reused the dedicated private bucket, passed upload/download byte comparison, and deleted the smoke object.

Safe metadata: `config/v2-storage.json`

- provider: `backblaze-b2`
- bucket: `saga-v2-faresmohamed260-1207062480`
- region: `us-east-005`
- S3 endpoint: `https://s3.us-east-005.backblazeb2.com`
- visibility: private

Bootstrap secrets remain admin-only:

- `SAGA_B2_KEY_ID`
- `SAGA_B2_MASTER_APPLICATION_KEY`

Normal web storage must use a bucket-scoped non-master application key through the provider-neutral storage boundary when that flow becomes active.

## v2 Architectural Boundary

```text
Public browser
  -> landing / sign-in / invite-confirm surfaces

Verified invited user
  -> Next.js application on Vercel
       -> server-verified Supabase Auth identity
       -> S.A.G.A. account/access resolver
       -> dedicated S.A.G.A. Supabase Postgres / Realtime
       -> ObjectStorage -> Backblaze B2
       -> application API / durable job-control layer
            -> future agentic AI runtime
```

The future AI runtime consumes and produces application-owned contracts rather than defining the top-level architecture.

## Phase 1 Product Areas

The information architecture is user-concept-first, not pipeline-stage-first:

- Home
- Library / Sources
- Projects / Stories
- Characters / Relationships
- World / Locations
- Timeline / Events
- Canon / Evidence
- Story / Planning
- Media
- Activity
- Settings
- Admin

Routes/schema are defined only where the active phase needs them.

## External Setup Dependencies

Phase 1 has no remaining hosted blocker.

Completed hosted dependencies include:

- dedicated S.A.G.A. Supabase project and active v2 schema;
- closed-signup Auth configuration and production redirect boundary;
- verified Resend SMTP sender/domain;
- privileged runtime secret wiring through server/GitHub/Vercel secret boundaries;
- trusted initial admin bootstrap;
- real hosted invitation delivery, confirmation, claim, credential setup and later sign-in;
- hosted suspension/reactivation and pending-invitation revocation;
- obsolete Vercel `studio` Git integration disconnected;
- Git-triggered Vercel deployments disabled under the owner-authorized manual deployment policy.

Deferred operational work that is **not** a Phase 1 blocker:

- final custom public domain `saga.faresuniform.uk`, tracked separately;
- scoped B2 runtime credentials when a product object-upload flow becomes active.

Do not reuse the RenderLab/Studio Supabase project or shared R2 state for S.A.G.A.

## Immediate Work

1. merge the Phase 1 hosted completion evidence after exact-head repository validation;
2. close Phase 1 tracking issue #151 from the merged evidence;
3. on a fresh branch, author the immediate **Phase 2 contract** for the application job-control / agentic-runtime foundation using the contract-first rules in D-018;
4. merge that Phase 2 contract/governance update before any Phase 2 production implementation;
5. only then implement the bounded Phase 2 slice defined by that contract.

**No Phase 2 agent/LLM/runtime implementation is authorized until its immediate phase contract is written, reviewed, validated, and merged.**

## Validation

For `apps/web`:

```text
npm install --no-audit --no-fund
npm run lint
npm run typecheck
npm run test:unit
npm run build
```

The v2 Web CI also applies active `apps/web/supabase/migrations/*.sql` to disposable PostgreSQL and runs database contracts, including Phase 1E Admin hardening semantics. The visual workflow builds production Next.js and captures exact-head desktop/narrow evidence using runner-only fixtures.

Hosted Supabase validation is recorded separately from CI because successful repository tests do not prove hosted provider configuration or email delivery.

Green v1 Python CI or stale historical Vercel previews are not evidence that v2 works.

## Working Convention

A new session begins from `AGENTS.md`, this file, `docs/README.md`, `docs/DECISIONS.md`, and the active phase contract, then reads the relevant v2 subsystem docs.

Durable decisions and verified results go back into the repository. Do not reconstruct current project state from chat history when GitHub can establish it.
