# S.A.G.A. Project

S.A.G.A. is being rebuilt as a web-first storytelling intelligence platform. The product goals remain: ingest books/stories, reconstruct evidence-backed canon, model characters/worlds/timelines, support narrative generation, and eventually produce grounded visual/audio/story outputs. The architecture is intentionally new.

This file is the short source-of-truth handoff for the active rebuild.

## Active Product Direction — S.A.G.A. v2

The owner authorized a fresh rebuild on 2026-09-11.

**Same goals and feature set; different architecture.**

The old contract-driven Python/nine-stage production architecture is **S.A.G.A. v1 historical/reference material**. v2 selectively reuses requirements, algorithms, evaluations, schemas, prompts, and lessons; it does not preserve the old runtime architecture for compatibility.

The rebuild order is deliberate:

1. main web product frontend/backend;
2. account/auth/data/storage/job/deployment contracts;
3. new agentic AI subsystem behind those product contracts;
4. progressive restoration of S.A.G.A. intelligence/generation capabilities.

## Current Baseline

Phase 0 merged through PR **#149**:

- `main`: `261b75ff2a60dfcada681af6b6c918c1ff5e3366`
- tree: `50f34409fb52540ce48c506f9446a3b75e608b08`
- merge: `Establish S.A.G.A. v2 web foundation (#149)`

Post-merge `Required Check Compatibility`, `SAGA v2 Web CI`, and `Backend Architecture CI` all completed successfully.

Phase 0 tracking issue **#148** is closed complete.

## Active Phase

**S.A.G.A. v2 Phase 1 — Closed-Demo Main Site, Accounts & Invitations**

Tracking issue: **#151**

Contract: `docs/phases/PHASE_V2_1_CLOSED_DEMO_APP.md`

Working branch for the contract/planning pass:

- `v2/phase-1-closed-demo-app`

Status: **ACTIVE — CONTRACT/ARCHITECTURE FIRST**

The Phase 1 contract and subsystem rules are merged before feature implementation begins. This follows the repository-first progressive-phase discipline proven useful in RenderLab while keeping S.A.G.A. ownership separate.

## Closed-Demo Product Constraint

S.A.G.A. v2 is a **closed demo**.

- There is no public self-signup path.
- Supabase Auth owns identity/session mechanics.
- S.A.G.A. owns product admission/authorization state.
- Access is granted through admin-created email invitations.
- A public landing/brand route may exist, but private application routes require an active S.A.G.A. account.
- Invitation/account administration is server-only and admin-authorized.
- Service-role/Auth Admin credentials never enter browser code.
- Email delivery is not considered complete until the hosted Supabase email/SMTP configuration and invite templates are verified.

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

S.A.G.A. may study its current repository documentation for proven process/architecture/UI conventions such as:

- repository-first continuity and progressive phase contracts;
- Server Components by default with small client islands;
- maintained UI primitives and semantic tokens;
- responsive/accessibility/reduced-motion discipline;
- explicit feature/server/infrastructure ownership;
- closed-beta invitation/access patterns above Supabase Auth;
- remote-first CI and rendered UI validation.

Do **not** modify RenderLab during S.A.G.A. work. Do not copy its product code, visual identity, routes, schema/table names, credentials, storage, deployments, product data, or assumptions. S.A.G.A. must express every adopted principle through S.A.G.A.-owned contracts and implementation.

Current S.A.G.A. translations of those reference principles live in:

- `docs/v2/FRONTEND_ARCHITECTURE.md`
- `docs/v2/UI_SYSTEM.md`
- `docs/v2/ACCESS_AND_INVITATIONS.md`

## Storage Foundation — VALIDATED

Backblaze B2 is the v2 object store. GitHub Actions run `34537566675` authorized B2, created/reused the dedicated private bucket, passed upload/download byte comparison, and deleted the smoke object.

Validated safe metadata in `config/v2-storage.json`:

- provider: `backblaze-b2`
- bucket: `saga-v2-faresmohamed260-1207062480`
- region: `us-east-005`
- S3 endpoint: `https://s3.us-east-005.backblazeb2.com`
- visibility: private

Bootstrap secrets:

- `SAGA_B2_KEY_ID`
- `SAGA_B2_MASTER_APPLICATION_KEY`

The master key remains bootstrap/admin-only. Normal web storage will use a later bucket-scoped application key through the provider-neutral storage boundary.

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

The future AI runtime is a consumer/producer of application-owned contracts rather than the top-level architecture.

## Phase 1 Product Areas

The information architecture is user-concept-first, not pipeline-stage-first. Current target areas:

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

Phase 1 can proceed substantially in the repository before cloud setup, but these items are required before full end-to-end completion:

1. a new **S.A.G.A.-owned Supabase project**; the connected account currently exposes the `Fares Home Lab` organization, but project creation requires explicit organization selection and cost confirmation before mutation;
2. hosted Supabase Auth Site URL/redirect allowlist and invite-confirm template configuration;
3. production-capable custom SMTP or equivalent email hook/sender setup for invitation and recovery mail;
4. a bucket-scoped non-master B2 application key for normal runtime S3-compatible access.

Do not reuse the connected RenderLab/Studio Supabase project or shared R2 state for S.A.G.A.

## Immediate Work

1. merge the Phase 1 contract/governance/reference translation;
2. create the S.A.G.A. Supabase schema/migration for account access and invitations;
3. implement server-side identity/account/admin boundaries plus invite confirmation/password setup/sign-in;
4. implement the private application shell and first Home/Library/Projects surfaces using the S.A.G.A. UI system;
5. implement narrow Admin invitation/account management APIs/UI;
6. add deterministic auth/access/UI tests and exact-head v2 CI;
7. configure the new Supabase project/email delivery and scoped B2 runtime key when those external dependencies become blocking;
8. only after the application/data/job contracts stabilize, plan the agentic AI phase.

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

Phase 1 will expand this with access/security and rendered/responsive UI gates. Green v1 Python CI is not evidence that v2 works.

## Working Convention

A new session begins from `AGENTS.md`, this file, `docs/README.md`, `docs/DECISIONS.md`, and the active phase contract, then reads the relevant v2 subsystem docs.

Durable decisions and verified results go back into the repository. Do not reconstruct current project state from chat history when GitHub can establish it.