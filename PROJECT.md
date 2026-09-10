# S.A.G.A. Project

S.A.G.A. is being rebuilt as a web-first storytelling-intelligence platform. The product goals remain: ingest narrative sources, reconstruct evidence-backed canon, model characters/worlds/timelines, support grounded story generation, and eventually produce canon-aware visual/audio/story outputs. The architecture is intentionally new.

This file is the short source-of-truth handoff for the active rebuild.

## Active Product Direction — S.A.G.A. v2

The owner authorized a fresh rebuild on 2026-09-11.

**Same product goals; different architecture.**

The pre-v2 Python/nine-stage runtime is **S.A.G.A. v1 historical/reference material**. Its algorithms, evaluations, schemas, prompts, provider experiments, and lessons may inform v2, but v2 does not inherit its runtime architecture by default.

Development order:

1. main web frontend/backend product;
2. auth, application data, storage, jobs, deployment, and UX contracts;
3. new agentic AI runtime against those stable product contracts;
4. progressive restoration of analysis/canon/generation/media capabilities.

## Closed-Demo Product Model

S.A.G.A. v2 is a **closed demo**.

- private application access requires an account;
- there is **no public self-service signup**;
- access is invitation-only;
- invitations are created by an authorized S.A.G.A. admin and delivered by email;
- Supabase Auth owns identity/session state;
- S.A.G.A. owns product admission separately from Auth identity;
- only active admitted accounts may enter private application routes;
- pending/unknown/suspended identities fail closed;
- invitation/admin capability remains server-only;
- production email delivery requires correctly configured hosted Auth redirect/template/SMTP behavior before it can be called production-ready.

The durable Phase-1 contract is `docs/phases/PHASE_V2_1_CLOSED_DEMO_WEB.md`.

## Adopted v2 Stack

- **GitHub** — repository source of truth, CI, review, durable continuity;
- **Vercel** — primary web deployment target;
- **Next.js 16 + React 19 + TypeScript** — frontend and request-bounded backend/API layer;
- **Tailwind CSS + maintained accessible primitives + Motion** — design/interaction system;
- **Supabase** — Postgres, Auth, Realtime, authoritative structured application records;
- **Cloudflare** — DNS/CDN/security boundary where useful, not object storage;
- **Backblaze B2** — dedicated S.A.G.A. object storage;
- **future agentic runtime** — deferred until the web/application foundation is stable.

The active v2 web application lives under `apps/web/`.

## RenderLab Reference Boundary

`faresmohamed260/renderlab` is a **separate project** and must remain unchanged.

S.A.G.A. may read RenderLab documentation/code for reference on:

- repository-first continuity;
- Next.js/Supabase project setup conventions;
- server/client ownership boundaries;
- account identity vs product admission separation;
- invite/admin security patterns;
- maintained component primitives;
- semantic design tokens;
- responsive/rendered UI verification;
- progressive phase planning and design-governance process.

S.A.G.A. must **not** copy RenderLab product state, routes, schema/table names, brand/visual identity, media/generation state, R2 resources, credentials, deployments, or implementation wholesale.

S.A.G.A.-owned UI rules live in:

- `docs/v2/UI_SYSTEM.md`
- `docs/v2/DESIGN_WORKFLOW.md`

## Phase-0 Foundation — MERGED / VALIDATED

PR #149 merged as:

`261b75ff2a60dfcada681af6b6c918c1ff5e3366`

Validated foundation:

- `apps/web/` Next.js/React/TypeScript application;
- `/api/health` configuration-status route;
- Supabase SSR server/configuration boundary;
- provider-neutral `ObjectStorage` contract;
- Backblaze B2 S3 runtime adapter using scoped runtime credential names only;
- structural tests preventing B2 master bootstrap secrets from entering web runtime;
- `.github/workflows/v2-web-ci.yml` deterministic web gate;
- `.github/workflows/v2-b2-bootstrap.yml` manual-only B2 administration/smoke workflow;
- `config/v2-storage.json` validated storage metadata;
- post-merge SAGA v2 Web CI, Backend Architecture CI, and Required Check Compatibility all passed.

Issue #148 is closed completed.

## Storage Foundation — VALIDATED

GitHub Actions run `34537566675` successfully authorized Backblaze, created/reused the private S.A.G.A. bucket, uploaded/downloaded/byte-compared/deleted a smoke object, and exposed only safe metadata.

Committed non-secret configuration:

- provider: `backblaze-b2`
- bucket: `saga-v2-faresmohamed260-1207062480`
- region: `us-east-005`
- S3 endpoint: `https://s3.us-east-005.backblazeb2.com`
- visibility: private

Bootstrap-only repository secrets:

- `SAGA_B2_KEY_ID`
- `SAGA_B2_MASTER_APPLICATION_KEY`

Never print or commit their values.

The master key is bootstrap/admin only. Normal web runtime storage requires a later bucket-scoped application key through the existing provider-neutral storage interface.

## v2 Architectural Boundary

```text
Public browser
  -> public landing / sign-in / auth completion

Admitted browser session
  -> private Next.js application on Vercel
       -> fresh Supabase Auth identity verification
       -> S.A.G.A. account admission
       -> Supabase Postgres / Realtime
       -> ObjectStorage -> Backblaze B2
       -> application job/control plane
            -> future agentic AI runtime
```

Auth identity and S.A.G.A. product admission are separate security decisions.

## Active Phase

**S.A.G.A. v2 Phase 1 — Closed Demo Web Product, Accounts & Invitations**

Tracking issue: **#150**

Contract: `docs/phases/PHASE_V2_1_CLOSED_DEMO_WEB.md`

Branch:

`v2/phase-1-closed-demo-web`

Status: **ACTIVE**

## Phase-1 Immediate Work

1. make Phase-1/closed-demo direction authoritative across governance docs;
2. add S.A.G.A.-owned UI/design rules using RenderLab only as read-only process reference;
3. establish public vs private route groups and application shell;
4. add browser/server/session Supabase boundaries for account workflows;
5. define v2 account-access + invitation persistence/migration;
6. implement fresh server identity + active admission checks for private routes;
7. add sign-in/invitation completion/account surfaces without public signup;
8. add admin invitation/account operations with anti-enumeration behavior;
9. keep service-role/Auth Admin capability server-only;
10. document hosted email/SMTP/template requirements honestly;
11. run exact-head v2 CI and rendered desktop/narrow review.

## External Phase-1 Dependencies

Live end-to-end activation still requires:

- a S.A.G.A.-owned Supabase project selected/created by the owner;
- Supabase public/server credentials in the appropriate deployment/CI boundaries;
- Site URL + allowed redirect configuration;
- invitation/confirmation/recovery templates;
- production-capable custom SMTP or equivalent Auth email delivery;
- bucket-scoped B2 runtime credentials before real source upload is enabled.

Missing external configuration must fail honestly. Do not invent live readiness.

## Legacy v1 Boundary

The pre-v2 `packages/`, `integrations/`, `apps/dashboard_api/`, `apps/dashboard_pro/`, `deploy/production/`, Python runtime/migrations/qualification machinery, and related docs remain historical/reference surfaces during transition.

Rules:

- do not add new v2 behavior there;
- do not import them into `apps/web`;
- do not preserve v1 architecture merely for compatibility;
- reuse useful ideas only behind v2-owned contracts.

The clean pre-v2 boundary is:

`b689e17bf2b70ea6c2ade0c3795bb85bb048d57b`

## Validation

Minimum deterministic web gate:

```text
cd apps/web
npm install --no-audit --no-fund
npm run lint
npm run typecheck
npm run test:unit
npm run build
```

A green legacy Python workflow does not prove v2 works. Phase-1 claims require v2-specific exact-head evidence plus rendered UI verification when presentation changes.

## Working Convention

A new session begins from this file and `AGENTS.md`, then reads `docs/README.md`, `docs/DECISIONS.md`, the active phase contract, and relevant `docs/v2/` subsystem/UI rules.

Durable decisions and verified results go back into the repository. Do not reconstruct current state from chat history when GitHub can establish it.
