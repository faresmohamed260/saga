# S.A.G.A. Durable Decisions

This file records cross-cutting decisions that future sessions must not silently reinterpret. Detailed subsystem decisions should remain in their owning runtime/architecture documents when appropriate.

## D-001 — Repository Is the Persistent Source of Truth

**Status:** Accepted

S.A.G.A. repository code and current authoritative documentation define project state. ChatGPT Project context and conversations are supplementary continuity only.

**Consequence:** A durable decision, completed phase, blocker, validation result, or architecture change must be recorded in the repository rather than existing only in chat history.

## D-002 — Active Architecture Is Contract-Driven; Historical Backup Is Inert

**Status:** Accepted

The active rebuilt architecture uses reusable packages/integrations/application surfaces. `backup/reference/` is discovery/history material and active code must not import it.

**Consequence:** Legacy behavior may inform requirements, but legacy implementation does not become an active dependency by convenience.

## D-003 — Runtime Ownership Boundaries Must Be Preserved

**Status:** Accepted

Provider access, persistence, execution, identity, retrieval, reasoning, generation, observability, and other cross-cutting capabilities should flow through their owning active runtimes/contracts rather than ad hoc direct integrations.

**Consequence:** New agent or application code should not bypass an existing owning runtime merely to ship a local fix faster.

## D-004 — Analysis Produces Canon Memory; Generation Consumes It

**Status:** Accepted

The analysis side owns durable canon construction. Story, visual, and audiobook generation should ground against persisted canon/retrieval/state artifacts when available rather than independently reconstructing canon from raw books.

**Consequence:** Downstream fixes should not mask upstream canon/identity contamination when the upstream subsystem owns the defect.

## D-005 — Research Is Evidence, Not Implementation State

**Status:** Accepted

Papers, model cards, external repositories, deep-research reports, benchmarks, and proposed algorithms are candidates for controlled evaluation. They do not change S.A.G.A. architecture until implemented, evaluated, and explicitly adopted.

**Consequence:** Future sessions must label research-backed alternatives as candidates until repository evidence supports adoption.

## D-006 — Qualification Claims Must Be Bound to Reproducible Source

**Status:** Accepted

A successful real-book/local/provider run is useful evidence, but production/promotable qualification requires traceable committed source and the required repository validation gates.

**Consequence:** The 2026-08-09 accepted real-book qualification remains evidence, but its own dirty-worktree warning prevents it from proving that current `main` is a promotable release.

## D-007 — Progressive Phase Planning

**Status:** Accepted

For substantial recovery/development cycles, keep later work at roadmap level and fully specify the immediate phase from verified current state. Completing a phase requires evidence and documentation updates before the next phase is expanded.

**Consequence:** AI sessions should not create speculative detailed plans for many future phases while current-state evidence is still changing.

## D-008 — Cross-Surface Cleanup Requires Explicit Ownership Evidence

**Status:** Accepted

S.A.G.A. previously contained both its core product surfaces and the `apps/studio/` prototype. The prototype was not removed during initial recovery because ownership had to be established first.

**Consequence:** Destructive cross-surface cleanup requires an explicit ownership decision and focused change. That requirement was satisfied for Studio by D-009 and D-010; the same discipline applies to future ambiguous surfaces.

## D-009 — Generic Image/Video Studio Product Belongs In RenderLab

**Status:** Accepted

The generic image/video generation platform previously developed under the S.A.G.A. `apps/studio/` surface evolved into and is now owned by the separate `faresmohamed260/renderlab` repository.

**Consequence:** Generic image/video product UI, gallery, media-library, product persistence, and product-specific feature work must not continue in S.A.G.A. by default. RenderLab is a separate project and its product state is not S.A.G.A. implementation state.

## D-010 — Retire `apps/studio/`; Retain Reusable S.A.G.A. Visual Infrastructure

**Status:** Accepted

The owner explicitly authorized removal of the retired S.A.G.A. Studio prototype after confirming that its standalone successor is RenderLab. The focused cleanup removes `apps/studio/`, Studio-only workflows, UI/product documentation, patch helpers, and Studio-owned Supabase migration definitions from S.A.G.A.

Reusable provider infrastructure that is also part of S.A.G.A.'s stage-7 visual-generation runtime remains in S.A.G.A., including `packages/visual_generation`, `packages/modal_runtime`, `integrations/comfyui`, `integrations/qwen`, the Modal ecosystem configuration, and operational worker tooling. Public worker routing metadata formerly stored in the Studio app is rehomed to `config/modal-worker-registry.json`.

Existing remote resources are not destroyed merely because their Studio source definitions are removed. In particular, this repository cleanup does not drop already-created `studio_*` database objects, delete R2 objects/buckets, stop Modal workers, or mutate RenderLab resources.

**Consequence:** Future S.A.G.A. work may reuse the retained model/provider fleet only through S.A.G.A.'s own runtime contracts. Do not restore Studio UI/product code as a shortcut. Any live cleanup or transfer of legacy Studio cloud resources requires its own explicit operation.

## Open Decisions Requiring Evidence

These are not accepted decisions yet.

### O-002 — Current promotable S.A.G.A. release baseline

The repository has strong prior qualification evidence, and deterministic recovery CI is green, but clean-source protected-book qualification is still blocked by the documented Cloudflare R2 `403 Forbidden` asset-read prerequisite.

Phase 0 must identify the exact commit/configuration that satisfies the current build/test/qualification gates before this decision can be closed.
