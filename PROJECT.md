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

## Storage Decision

S.A.G.A. v2 does **not** use the existing Cloudflare R2 allocation. R2 is already shared by other projects and should not become another hobby/demo cost/congestion dependency.

Backblaze B2 is the selected v2 object store. GitHub repository secrets have been manually provisioned for bootstrap operations under these names:

- `SAGA_B2_KEY_ID`
- `SAGA_B2_MASTER_APPLICATION_KEY`

Never print or commit their values.

The master application key is **bootstrap/admin only**. Backblaze does not support master keys through its S3-compatible API. Normal S.A.G.A. web runtime storage must use a later bucket-scoped application key and the B2 S3 endpoint behind a provider-neutral storage interface.

Planned object namespaces:

- `sources/` — uploaded EPUB/PDF/source material;
- `artifacts/analysis/` — durable non-database analysis artifacts where needed;
- `generated/images/`;
- `generated/audio/`;
- `exports/`;
- `temporary/` — explicitly disposable objects;
- `_system/` — bounded storage validation/bootstrap objects.

Supabase owns structured application/domain state; B2 owns large binary/object payloads. Do not use object storage as an ad-hoc replacement for relational application state.

## v2 Architectural Boundary

The initial application is web-native:

```text
Browser
  -> Next.js web application on Vercel
       -> Supabase Auth / Postgres / Realtime
       -> Storage interface -> Backblaze B2
       -> application API / job-control layer
            -> future agentic AI runtime
```

The AI runtime must become a consumer/producer of stable application contracts rather than the top-level architecture of the product.

## Legacy v1 Boundary

The pre-v2 `packages/`, `integrations/`, `apps/dashboard_api/`, `apps/dashboard_pro/`, `deploy/production/`, Python migrations/runtime scripts, qualification workflows, and related tests/docs remain in the repository temporarily as **historical/reference surfaces** while v2 is established.

Rules:

- do not add new v2 behavior to those surfaces;
- do not import them from `apps/web`;
- do not make new architecture decisions merely to preserve their contracts;
- reuse ideas or algorithms only through an explicit v2 implementation decision;
- remove/archive obsolete v1 surfaces progressively after equivalent knowledge has been preserved where useful.

The separate `faresmohamed260/renderlab` project remains separate. S.A.G.A. may reuse proven engineering conventions/technology choices but not RenderLab product state, routes, schema ownership, storage credentials, or deployment assumptions.

## Active Phase

**S.A.G.A. v2 Phase 0 — Web Foundation & Storage Bootstrap**

Tracking issue: **#148**

Contract: `docs/phases/PHASE_V2_0_WEB_FOUNDATION.md`

Status: **ACTIVE**

The old v1 Phase-0 recovery/qualification issues #142 and #147 were closed as `not_planned` because the owner replaced that architecture with the v2 rebuild. Their evidence remains historical.

## Current Starting Baseline

v2 branch:

- `v2/phase-0-web-foundation`

Branch base / last v1 `main` before the v2 reset work:

- `b689e17bf2b70ea6c2ade0c3795bb85bb048d57b`
- `Record Phase 0 external readiness blockers (#146)`

That SHA is a historical v1 boundary, not the target architecture for v2.

## Immediate Work

Phase 0 currently owns:

1. repository governance reset for v2;
2. `apps/web` Next.js/TypeScript scaffold;
3. initial S.A.G.A. product shell and health/backend boundary;
4. provider-neutral object-storage contract;
5. Supabase server/client boundary ready for a new S.A.G.A.-owned project;
6. v2-focused GitHub CI;
7. Backblaze B2 account bootstrap through GitHub Actions using the two configured bootstrap secrets;
8. creation and smoke validation of a dedicated private S.A.G.A. B2 bucket;
9. durable non-secret recording of bucket endpoint/identity metadata;
10. transition to Phase 1 for the main site frontend/backend product.

**Agent/LLM pipeline implementation is explicitly out of scope until the web/backend foundation is stable.**

## Validation Direction

For v2 web changes, the primary deterministic checks will be executed from `apps/web`:

```text
npm install --no-audit --no-fund
npm run lint
npm run typecheck
npm run test:unit
npm run build
```

The existing v1 Python CI may remain during transition, but a green v1 check is not evidence that v2 works and a v1 architecture constraint must not block an intentional v2 design decision unless it protects a repository-wide security/integrity rule.

## Working Convention

A new session must begin from this file and `AGENTS.md`, then read `docs/README.md`, `docs/DECISIONS.md`, and the active v2 phase contract.

Durable decisions and verified results go back into the repository. Do not reconstruct current project state from chat history when the repository can establish it.