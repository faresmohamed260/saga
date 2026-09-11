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

The documentation handoff/validation refresh followed through PR **#154**.

Phase 0 issue **#148** is closed. Phase 1 is tracked by **#151**.

Durable Phase 1B evidence: `docs/validation/PHASE_V2_1B_ACCOUNT_ACCESS_2026-09-11.md`.

## Active Phase

**S.A.G.A. v2 Phase 1 — Closed-Demo Main Site, Accounts & Invitations**

Contract: `docs/phases/PHASE_V2_1_CLOSED_DEMO_APP.md`

Status: **ACTIVE — 1A COMPLETE; 1B COMPLETE; 1C NEXT**

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

Earlier branch run **34593420479** also passed both the web-quality and database-contract jobs.

### Phase 1C — next

Start from the repository's actual current `main` after verifying its exact SHA. Use a fresh branch.

Implement the user-facing auth/access slice without weakening the merged Phase 1B guarantees:

- sign-in;
- server invitation confirmation;
- password setup/change for confirmed invited users;
- sign-out;
- SSR session refresh/cookie plumbing;
- protected route/layout boundary using fresh verified identity + S.A.G.A. access status;
- bounded unauthenticated/not-admitted/suspended/active/unavailable states;
- safe same-origin redirect handling;
- deterministic auth/access tests.

Do **not** add public self-signup.

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

These are required before Phase 1 can be called end-to-end complete, but they are **not blockers for deterministic Phase 1C repository work**:

1. a new **S.A.G.A.-owned Supabase project**; project creation through the connected tool requires explicit organization selection and cost confirmation;
2. hosted Supabase Auth Site URL/redirect allowlist and invite-confirm template configuration;
3. production-capable custom SMTP or equivalent email hook/sender setup;
4. a bucket-scoped non-master B2 application key for runtime S3-compatible access.

Do not reuse the connected RenderLab/Studio Supabase project or shared R2 state for S.A.G.A.

## Immediate Work

1. verify the exact current remote `main` and repository checks;
2. create a fresh Phase 1C branch;
3. implement sign-in, invite confirmation, password setup, SSR session refresh, sign-out, and private route boundaries using the merged Phase 1B access services;
4. keep hosted email delivery separate from deterministic CI until a dedicated S.A.G.A. Supabase project/email path is explicitly configured;
5. run exact-head `SAGA v2 Web CI` plus relevant repository checks before merge;
6. use a S.A.G.A.-specific concept/review pass before Phase 1D application-shell implementation; RenderLab remains read-only reference only;
7. implement the private application shell and first Home/Library/Projects surfaces after visual direction is approved;
8. implement narrow Admin invitation/account management APIs/UI;
9. configure hosted Supabase/email and scoped B2 runtime credentials when they become blocking;
10. prove at least one real bounded email invitation acceptance before closing Phase 1;
11. only after application/data/job contracts stabilize, plan the agentic AI phase.

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

The v2 web workflow also executes active `apps/web/supabase/migrations/*.sql` against disposable PostgreSQL with a minimal Supabase-compatible Auth/role bootstrap and runs database contract tests. Phase 1C should add deterministic auth/route-boundary coverage. Phase 1D later adds rendered/responsive application-shell evidence. Green v1 Python CI is not evidence that v2 works.

## Working Convention

A new session begins from `AGENTS.md`, this file, `docs/README.md`, `docs/DECISIONS.md`, and the active phase contract, then reads the relevant v2 subsystem docs.

Durable decisions and verified results go back into the repository. Do not reconstruct current project state from chat history when GitHub can establish it.