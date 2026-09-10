# S.A.G.A. Durable Decisions

This file records cross-cutting decisions future sessions must not silently reinterpret.

## Active v2 Decisions

### D-001 — Repository Is the Persistent Source of Truth

**Status:** Accepted

Current repository code and authoritative documentation define S.A.G.A. state. Chat/project memory is supplementary continuity.

**Consequence:** Durable architecture, phase state, validation evidence, and blockers must be recorded in GitHub.

### D-011 — S.A.G.A. v2 Is a Fresh Rebuild

**Status:** Accepted — owner decision 2026-09-11

S.A.G.A. keeps its product goals and intended capabilities but abandons the previous implementation architecture as the active system.

The pre-v2 Python/nine-stage system becomes historical/reference material. v2 is not required to preserve its runtime package boundaries, deployment topology, persistence abstractions, qualification control plane, provider routing, or orchestration design.

**Consequence:** Reuse requirements, algorithms, evaluations, schemas, prompts, and lessons selectively; do not bulk-port v1 code or treat v1 compatibility as a default requirement.

### D-012 — v2 Is Web-First

**Status:** Accepted

The main application is built first as a web product. The initial architecture is:

- Next.js + React + TypeScript;
- Vercel deployment;
- Supabase Postgres/Auth/Realtime;
- Cloudflare DNS/CDN/security where useful;
- dedicated object storage behind a S.A.G.A.-owned interface.

The first active product surface is `apps/web/`.

**Consequence:** User-facing domain workflows, application state, auth, jobs, and storage contracts are designed before the new agentic AI runtime.

### D-013 — Agentic AI Follows the Web/Application Foundation

**Status:** Accepted

The new agentic AI subsystem is intentionally deferred until the web frontend/backend, application data model, storage, authentication, job lifecycle, and deployment contracts are stable enough to consume.

**Consequence:** Phase 0/1 must not recreate the old pipeline as the top-level product architecture. Future agents operate behind application-owned contracts and write structured application state/artifacts.

### D-014 — Backblaze B2 Is the v2 Object Store

**Status:** Accepted

S.A.G.A. v2 will not use the existing shared Cloudflare R2 allocation. Backblaze B2 is selected for S.A.G.A.-dedicated object storage for the hobby/demo deployment.

Supabase owns structured relational application state. B2 owns source files, generated media, exports, and other large binary/object payloads.

**Consequence:** Do not make new S.A.G.A. storage depend on the RenderLab/Fares Uniform R2 allocation. Keep the object-store boundary replaceable.

### D-015 — Object Storage Is Provider-Neutral at the Domain Boundary

**Status:** Accepted

Feature/domain code depends on a S.A.G.A.-owned storage interface rather than directly on B2/AWS SDK clients. The B2 runtime implementation may use Backblaze's S3-compatible API once a scoped application key exists.

**Consequence:** Vendor details remain in `apps/web/src/server/storage/` (or a later dedicated infrastructure package). Switching to another S3-compatible store should not require rewriting domain features.

### D-016 — B2 Master Key Is Bootstrap-Only

**Status:** Accepted

Repository secrets `SAGA_B2_KEY_ID` and `SAGA_B2_MASTER_APPLICATION_KEY` are available for bounded Backblaze account/bootstrap operations. Their values must never be printed or committed.

Backblaze master application keys are not S3-compatible, so they are not the normal web runtime credential.

**Consequence:** GitHub Actions may use the master key to create/inspect/smoke-test the dedicated bucket through the B2 Native/CLI path. Normal web storage will later use a bucket-scoped application key and explicit S3 endpoint configuration.

### D-017 — RenderLab Is an Engineering Reference, Not a Shared Product

**Status:** Accepted

S.A.G.A. v2 deliberately uses the same technology family and may reuse proven workflow conventions from the former Studio/RenderLab lineage. RenderLab remains a separate project.

**Consequence:** Do not share database schema ownership, R2 credentials, routes, generated-media state, deployments, or product assumptions between the projects merely because the stacks are similar.

### D-018 — Progressive v2 Phases

**Status:** Accepted

Fully specify the immediate v2 phase and keep later phases at roadmap level until current implementation evidence is stable.

Current order:

1. Phase 0 — web foundation + storage bootstrap;
2. Phase 1 — main site frontend/backend product;
3. later — agentic AI foundation and progressive restoration of S.A.G.A. intelligence/generation capabilities.

## Still-Applicable General Principles From v1

These principles remain useful across the rebuild even though their old implementation context is historical:

- research is evidence, not implementation state;
- analysis-derived canon should become durable application state before generation relies on it;
- qualification/evaluation claims must be tied to reproducible source/configuration;
- cross-project cleanup/reuse requires explicit ownership evidence;
- deterministic code should own schemas, validation, identifiers, state transitions, authorization, and orchestration invariants.

## Historical v1 Decisions

The earlier D-002 through D-010 decisions described the pre-v2 contract-driven Python architecture, nine-stage runtime, Studio retirement, and v1 qualification/recovery boundaries. They remain valid **historical evidence about v1**, but they do not constrain v2 architecture except where an active decision above explicitly preserves the principle.

The clean v1 boundary immediately before the rebuild is commit:

`b689e17bf2b70ea6c2ade0c3795bb85bb048d57b`

Do not reactivate the v1 Phase-0 qualification/R2 repair path unless the owner explicitly reverses the v2 rebuild decision.

## Open v2 Decisions

Do not decide these prematurely; resolve them in the phase that needs them:

- exact new Supabase project and schema rollout strategy;
- final runtime hosting/queue architecture for long-running agent jobs that exceed Vercel request limits;
- agent framework/model-provider architecture;
- GPU/provider strategy for future visual/audio generation;
- whether B2 runtime access should be direct-to-browser presigned S3 uploads, server-mediated operations, or a hybrid per object type.