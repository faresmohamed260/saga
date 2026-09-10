# S.A.G.A. Project

S.A.G.A. is being rebuilt as a web-first storytelling intelligence platform. The product goals remain: ingest books/stories, reconstruct evidence-backed canon, model characters/worlds/timelines, support narrative generation, and eventually produce grounded visual/audio/story outputs. The architecture is intentionally new.

This file is the short source-of-truth handoff for the active rebuild.

## Active Product Direction — S.A.G.A. v2

The owner authorized a fresh rebuild on 2026-09-11.

**Same goals and feature set; different architecture.**

The old contract-driven Python/nine-stage production architecture is now **S.A.G.A. v1 historical/reference material**. Its code, tests, qualification machinery, recovery documents, and provider integrations may be consulted for requirements, proven behavior, schemas, algorithms, evaluation ideas, and lessons learned, but v2 must not depend on them by default.

The rebuild order is deliberate:

1. build the main web product frontend and backend;
2. establish application data, auth, storage, jobs, and deployment contracts;
3. only then design and implement the new agentic AI subsystem against those stable product contracts;
4. progressively restore the original S.A.G.A. intelligence/generation capabilities through the new architecture.

## Adopted v2 Stack

The web stack follows the successful Studio/RenderLab family of technologies without importing RenderLab product state or ownership:

- **GitHub** — repository source of truth, CI, review, durable project continuity;
- **Vercel** — primary web deployment;
- **Next.js 16 + React 19 + TypeScript** — frontend and initial backend/API layer;
- **Tailwind CSS + reusable maintained component primitives + Motion** — design system and interaction layer;
- **Supabase** — Postgres, Auth, Realtime, and authoritative application records;
- **Cloudflare** — DNS/CDN/security boundary where useful, but not S.A.G.A. object storage;
- **Backblaze B2** — dedicated S.A.G.A. object storage;
- **Agentic AI runtime** — deferred until the web application/backend foundation is stable.

The current v2 web application lives under `apps/web/`.

## Storage Foundation — VALIDATED

S.A.G.A. v2 does **not** use the existing Cloudflare R2 allocation. Backblaze B2 is the selected v2 object store.

GitHub Actions run `34537566675` successfully:

- authorized the B2 account using the configured bootstrap secrets;
- created/reused a dedicated private S.A.G.A. bucket;
- uploaded a small `_system/bootstrap/` object;
- downloaded it and passed byte-for-byte comparison;
- deleted the smoke object;
- exposed only safe bucket/endpoint metadata.

Validated non-secret storage configuration is committed in `config/v2-storage.json`:

- provider: `backblaze-b2`
- bucket: `saga-v2-faresmohamed260-1207062480`
- region: `us-east-005`
- S3 endpoint: `https://s3.us-east-005.backblazeb2.com`
- visibility: private

Bootstrap repository secrets:

- `SAGA_B2_KEY_ID`
- `SAGA_B2_MASTER_APPLICATION_KEY`

Never print or commit their values.

The master application key is **bootstrap/admin only**. Normal S.A.G.A. web runtime storage must use a later bucket-scoped application key through the B2 S3-compatible endpoint and the provider-neutral storage interface under `apps/web/src/server/storage/`.

Planned object namespaces:

- `sources/`
- `artifacts/analysis/`
- `generated/images/`
- `generated/audio/`
- `exports/`
- `temporary/`
- `_system/`

Supabase owns structured application/domain state; B2 owns large binary/object payloads.

## v2 Architectural Boundary

```text
Browser
  -> Next.js web application on Vercel
       -> Supabase Auth / Postgres / Realtime
       -> ObjectStorage -> Backblaze B2
       -> application API / job-control layer
            -> future agentic AI runtime
```

The AI runtime becomes a consumer/producer of stable application contracts rather than the top-level architecture of the product.

## Implemented v2 Foundation

Current active implementation includes:

- `apps/web/` Next.js/React/TypeScript application;
- initial S.A.G.A. landing/product shell;
- `/api/health` configuration-status endpoint;
- Supabase SSR server/configuration boundary;
- provider-neutral `ObjectStorage` contract;
- Backblaze B2 S3 runtime adapter using **scoped runtime credential names only**;
- structural tests preventing master B2 credentials from entering the web runtime;
- `.github/workflows/v2-web-ci.yml` deterministic web gate;
- `.github/workflows/v2-b2-bootstrap.yml` manual-only B2 administration/smoke workflow;
- `config/v2-storage.json` validated safe storage metadata.

The first v2 Web CI run `34537327565` passed install, lint, typecheck, tests, and production build before the final workflow-boundary tests were added. Final-head CI must be rerun before merge.

## Legacy v1 Boundary

The pre-v2 `packages/`, `integrations/`, `apps/dashboard_api/`, `apps/dashboard_pro/`, `deploy/production/`, Python migrations/runtime scripts, qualification workflows, and related tests/docs remain temporarily as **historical/reference surfaces**.

Rules:

- do not add new v2 behavior to those surfaces;
- do not import them from `apps/web`;
- do not preserve their architecture merely for compatibility;
- reuse ideas or algorithms only through an explicit v2 implementation decision;
- remove/archive obsolete v1 surfaces progressively after useful knowledge has been preserved.

The separate `faresmohamed260/renderlab` project remains separate. S.A.G.A. may reuse engineering conventions/technology choices but not RenderLab product state, routes, schema ownership, storage credentials, or deployment assumptions.

## Active Phase

**S.A.G.A. v2 Phase 0 — Web Foundation & Storage Bootstrap**

Tracking issue: **#148**

Contract: `docs/phases/PHASE_V2_0_WEB_FOUNDATION.md`

Status: **ACTIVE — FOUNDATION IMPLEMENTED; FINAL CI/PR MERGE REMAINS**

The old v1 Phase-0 recovery/qualification issues #142 and #147 are closed `not_planned` because the owner replaced that architecture with the v2 rebuild.

## Current Branch

- branch: `v2/phase-0-web-foundation`
- pre-v2 boundary: `b689e17bf2b70ea6c2ade0c3795bb85bb048d57b`

## Immediate Work

1. run final-head v2 web CI including the storage/workflow boundary tests;
2. inspect the complete branch diff for v1/v2 boundary mistakes or secret leakage;
3. open and merge the focused Phase-0 v2 PR only after exact-head checks pass;
4. update the merged baseline/evidence;
5. start **Phase 1 — Main Site Frontend & Backend**;
6. provision a new S.A.G.A.-owned Supabase project/schema as Phase 1 needs it;
7. create a bucket-scoped B2 runtime application key and add its runtime secrets before implementing real source upload/read paths.

**Agent/LLM pipeline implementation remains out of scope until the web/backend product foundation is stable.**

## v2 Validation

From `apps/web`:

```text
npm install --no-audit --no-fund
npm run lint
npm run typecheck
npm run test:unit
npm run build
```

A green v1 Python workflow is not proof that v2 works. v2 changes require v2-specific exact-head CI evidence.

## Working Convention

A new session begins from this file and `AGENTS.md`, then reads `docs/README.md`, `docs/DECISIONS.md`, and the active v2 phase contract.

Durable decisions and verified results go back into the repository. Do not reconstruct current project state from chat history when GitHub can establish it.