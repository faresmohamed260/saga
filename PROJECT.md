# S.A.G.A. Project

S.A.G.A. is being rebuilt as a web-first storytelling intelligence platform. The product goals remain: ingest books/stories, reconstruct evidence-backed canon, model characters/worlds/timelines, support narrative generation, and eventually produce grounded visual/audio/story outputs. The architecture is intentionally new.

This file is the short source-of-truth handoff for the active rebuild.

## Active Product Direction — S.A.G.A. v2

The owner authorized a fresh rebuild on 2026-09-11.

**Same goals and feature set; different architecture.**

The old contract-driven Python/nine-stage production architecture is **S.A.G.A. v1 historical/reference material**. v2 may reuse requirements, algorithms, evaluations, schemas, prompts, and lessons, but it does not preserve the old runtime architecture for compatibility.

The rebuild order is deliberate:

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

Phase 1B closed-demo account/access foundation:

- PR **#153**
- code merge commit `5d5b59d17d2bd2f9a5769d2e5c4f9a2b43d1bad9`
- merged tree `6a2814f97114e6d731235b933f3a75c8fa9fdc76`
- exact PR head `e81915942ba9e859c79898ec60fdda38a56235d3`
- exact-head `SAGA v2 Web CI`, `Required Check Compatibility`, and `Backend Architecture CI` all succeeded before merge

The Phase 1B documentation handoff/validation refresh followed through PR **#154**.

Phase 1C closed-demo auth/access surfaces:

- PR **#156**
- exact PR head `7bc81877a55af9b47b6bbc96abd7a17e9100fda3`
- merged tree `3bb5388d2004fc09124fddbc59b7978414be6d4f`
- merge commit `319b785e43a169b4ffd7b57cd5be32ad3ef5da67`
- exact-head `SAGA v2 Web CI`, `Required Check Compatibility`, and `Backend Architecture CI` all succeeded before merge

Phase 1D Narrative Desk shell / first product surfaces:

- approved UI concept merged through PR **#158** at `418e1d5d446c931bfba83170147307727378b664`
- implementation PR **#160**
- exact PR head `8ad0a7eb3bffa3aed394ea86eff562f837239b14`
- merge commit `f558a282b4743a15d440eada1c6a7ccefe44215c`
- exact-head `SAGA v2 Web CI`, `Required Check Compatibility`, `Backend Architecture CI`, and `SAGA v2 Visual Review` all succeeded before merge

Phase 0 issue **#148** is closed. Phase 1 is tracked by **#151**.

Durable validation evidence:

- Phase 1B: `docs/validation/PHASE_V2_1B_ACCOUNT_ACCESS_2026-09-11.md`
- Phase 1C: `docs/validation/PHASE_V2_1C_AUTH_ACCESS_2026-09-11.md`
- Phase 1D: `docs/validation/PHASE_V2_1D_NARRATIVE_DESK_2026-09-11.md`

## Active Phase

**S.A.G.A. v2 Phase 1 — Closed-Demo Main Site, Accounts & Invitations**

Contract: `docs/phases/PHASE_V2_1_CLOSED_DEMO_APP.md`

Status: **ACTIVE — 1A COMPLETE; 1B COMPLETE; 1C COMPLETE; 1D COMPLETE; 1E NEXT**

### Phase 1A — complete

The closed-demo account/frontend/UI contract is merged through PR #152.

### Phase 1B — complete

Merged through PR #153.

Implemented and validated:

- isolated active v2 database lineage under `apps/web/supabase/migrations/`;
- explicit guardrail preventing the historical root `supabase/migrations/` lineage from bootstrapping v2;
- `saga_account_access` role/status persistence keyed by verified Supabase Auth UUID;
- `saga_invitations` normalized-email lifecycle state with no raw reusable token/secret fields;
- forced RLS on privileged account/invitation tables with browser-role grants revoked;
- service-role-only transactional invitation claim using verified `auth.users.email`;
- fresh server `auth.getUser()` identity boundary;
- server-only privileged Supabase client boundary;
- account resolver for unauthenticated/not-admitted/suspended/active/unavailable states;
- active-admin authorization helper;
- structural closed-demo/security tests;
- disposable-Postgres CI that executes the active v2 migration and database contract tests.

PR #153 validation:

- `SAGA v2 Web CI` run **34593615395** — success;
- `Required Check Compatibility` run **34593615380** — success;
- `Backend Architecture CI` run **34593615394** — success.

### Phase 1C — complete

Merged through PR #156.

Implemented and validated:

- invitation-only public sign-in with no public signup path;
- server invitation confirmation using supported Supabase invite token-hash verification;
- reuse of the Phase 1B transactional invitation claim after fresh Auth verification;
- session-bound password setup/change;
- sign-out;
- Next.js 16 SSR Supabase cookie/session refresh through `proxy.ts`;
- protected private route-group layout backed by fresh S.A.G.A. account resolution;
- bounded unauthenticated, not-admitted, suspended, active, and unavailable routing;
- safe same-origin post-auth redirect normalization;
- provider/config failures bounded to the `unavailable` account state rather than untrusted partial access;
- deterministic auth/access structural tests;
- a minimal `/home` private-access checkpoint only, deliberately leaving the real application shell to Phase 1D.

PR #156 exact-head validation:

- `SAGA v2 Web CI` run **34601422907** — success;
- `Required Check Compatibility` run **34601422970** — success;
- `Backend Architecture CI` run **34601422837** — success.

Hosted invitation email delivery remains unproven and is still owned by the later Phase 1E operational gate.

### Phase 1D — complete

The S.A.G.A.-specific **Narrative Desk** concept was approved and merged through PR #158, then implemented through PR #160.

Implemented and validated:

- authenticated Narrative Desk application shell;
- one persistent desktop global rail with Home, Library, Projects, Settings, account context and sign-out;
- narrow/mobile top bar with accessible Radix-backed navigation sheet;
- real Home composition;
- real Library surface with honest empty state;
- real Projects surface with honest empty state;
- bounded Settings/session surface;
- private-workspace graphite/warm-neutral/iris semantic tokens;
- active-route `aria-current` semantics;
- keyboard/Escape/focus-restoration behavior for mobile navigation;
- portal-safe private theme inheritance for Radix content;
- reduced-motion behavior;
- production Chromium rendered validation at desktop and narrow widths;
- no fabricated domain data or generic admin-dashboard/card-grid fallback.

PR #160 exact-head validation:

- `SAGA v2 Web CI` run **34609975376** — success;
- `Required Check Compatibility` run **34609975375** — success;
- `Backend Architecture CI` run **34609975398** — success;
- `SAGA v2 Visual Review` run **34609975429** — success.

Rendered evidence artifact `10267703757` is recorded in the Phase 1D validation document.

### Phase 1E — next

The next deterministic repository slice is narrow **Admin invitation/account management** using the server authorization and account/invitation contracts already established in 1B/1C.

Implement only the bounded S.A.G.A.-owned admin surface needed for:

- pending invitations;
- S.A.G.A.-known accounts;
- role/status mutation;
- revoke/retry-safe invitation state handling;
- self-lockout/last-admin protections where applicable;
- sanitized operational feedback.

Then complete the hosted integration gate only with the required explicit authorization for external resources: dedicated S.A.G.A. Supabase project selection/cost confirmation, hosted Auth redirect/template/email setup, a real bounded invitation acceptance test, and scoped B2 runtime credentials when product object storage needs them.

Do not expose the shared `auth.users` directory as product data.

## Closed-Demo Product Constraint

S.A.G.A. v2 is a **closed demo**.

- There is no public self-signup path.
- Supabase Auth owns identity/session mechanics.
- S.A.G.A. owns product admission/authorization state.
- Access is granted through admin-created email invitations.
- A public landing/brand route may exist, but private application routes require an active S.A.G.A. account.
- Invitation/account administration is server-only and admin-authorized.
- Service-role/Auth Admin credentials never enter browser code.
- Email delivery is not complete until hosted Supabase email/SMTP configuration and invite templates are verified.

Detailed contract: `docs/v2/ACCESS_AND_INVITATIONS.md`.

## Adopted v2 Stack

- **GitHub** — source of truth, review, CI, durable continuity;
- **Vercel** — primary web deployment target;
- **Next.js 16 + React 19 + TypeScript** — frontend and request-bounded backend/API;
- **Tailwind CSS + maintained accessible primitives + Motion** — UI system and intentional interaction;
- **Supabase** — Postgres, Auth, Realtime, structured application records;
- **Cloudflare** — DNS/CDN/security boundary where useful, not S.A.G.A. object storage;
- **Backblaze B2** — dedicated private S.A.G.A. object storage;
- **future agentic runtime** — deferred until the application foundation is stable.

The active v2 application lives under `apps/web/`.

## RenderLab Reference Boundary

`faresmohamed260/renderlab` is a **separate product and read-only reference** for S.A.G.A. work.

S.A.G.A. may inspect its current repository documentation for proven process/architecture/UI conventions such as repository-first continuity, progressive phase contracts, Server Components by default, maintained UI primitives, semantic tokens, responsive/accessibility/reduced-motion discipline, explicit server boundaries, closed-beta invitation/access patterns, and rendered validation.

Do **not** modify RenderLab during S.A.G.A. work. Do not copy its product code, visual identity, routes, schema/table names, credentials, storage, deployments, product data, or assumptions. Any adopted principle must be expressed through S.A.G.A.-owned contracts and implementation.

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

Bootstrap secrets:

- `SAGA_B2_KEY_ID`
- `SAGA_B2_MASTER_APPLICATION_KEY`

The master key remains bootstrap/admin-only. Normal web storage later uses a bucket-scoped application key through the provider-neutral storage boundary.

Supabase owns structured application/domain state; B2 owns large binary/object payloads.

## v2 Architectural Boundary

```text
Public browser
  -> landing / sign-in / invite-confirm surfaces

Verified invited user
  -> Next.js application on Vercel
       -> server-verified Supabase Auth identity
       -> S.A.G.A. account/access resolver
       -> Supabase Postgres / Realtime
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

These are required before Phase 1 can be called end-to-end complete, but they are **not blockers for deterministic Phase 1E admin API/UI repository work**:

1. a new **S.A.G.A.-owned Supabase project**; project creation through the connected tool requires explicit organization selection and cost confirmation;
2. hosted Supabase Auth Site URL/redirect allowlist and invite-confirm template configuration;
3. production-capable custom SMTP or equivalent email hook/sender setup;
4. a bucket-scoped non-master B2 application key for runtime S3-compatible access when product object-storage flow needs it.

Do not reuse the connected RenderLab/Studio Supabase project or shared R2 state for S.A.G.A.

The connected historical Vercel project also still points at retired `apps/studio`; do not treat those failed previews as v2 application evidence or silently repurpose that hosted project without the owning deployment decision.

## Immediate Work

1. verify the exact current remote `main` and repository checks;
2. implement Phase 1E narrow active-admin invitation/account server services and APIs using the existing fresh-auth/admin boundary;
3. implement the bounded `/admin` UI over S.A.G.A.-owned invitation/account state only;
4. add deterministic database/service/API/UI tests, including self-lockout/last-admin protections where applicable;
5. collect rendered desktop/narrow/accessibility evidence for the Admin surface;
6. configure hosted S.A.G.A. Supabase/email only after explicit organization selection and cost confirmation;
7. prove at least one real bounded email invitation acceptance before closing Phase 1;
8. establish scoped B2 runtime credentials when source upload becomes part of the product flow;
9. only after application/data/job contracts stabilize, plan the agentic AI phase.

**Agent/LLM pipeline implementation remains out of scope in Phase 1.**

## Validation

For `apps/web`:

```text
npm install --no-audit --no-fund
npm run lint
npm run typecheck
npm run test:unit
npm run build
```

The v2 web workflow also executes active `apps/web/supabase/migrations/*.sql` against disposable PostgreSQL with a minimal Supabase-compatible Auth/role bootstrap and runs database contract tests. Phase 1C added deterministic auth/route-boundary coverage. Phase 1D added structural shell coverage plus exact-head production Chromium desktop/narrow/accessibility evidence. Green v1 Python CI is not evidence that v2 works.

## Working Convention

A new session begins from `AGENTS.md`, this file, `docs/README.md`, `docs/DECISIONS.md`, and the active phase contract, then reads the relevant v2 subsystem docs.

Durable decisions and verified results go back into the repository. Do not reconstruct current project state from chat history when GitHub can establish it.