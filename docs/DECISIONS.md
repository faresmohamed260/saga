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

## D-008 — No Silent Cross-Surface Cleanup

**Status:** Accepted

The repository currently contains S.A.G.A. core surfaces plus `apps/studio/` and Studio-specific workflows/issues/PR history. Their coexistence is real repository state even where documentation is inconsistent.

**Consequence:** Do not delete, merge, migrate, or redefine those surfaces merely to make the repository look cleaner. Phase 0 must classify ownership and coupling from code/history first, and any destructive separation requires an explicit decision.

## D-009 — Generic Image/Video Studio Product Belongs In RenderLab

**Status:** Accepted

The generic image/video generation platform previously developed under the S.A.G.A. `apps/studio/` surface is now owned by the separate `faresmohamed260/renderlab` repository.

The existing S.A.G.A. `apps/studio/` files and Studio-specific workflow history remain real repository state and may be needed as historical or migration reference, but they are not the default place for new generic image/video product development.

**Consequence:** Do not continue RenderLab feature work in S.A.G.A. by default. Do not delete the S.A.G.A. Studio files as part of recovery without a separate explicit removal/migration PR. Treat active RenderLab work as external product work and S.A.G.A. Studio as transitional/historical until cleanup is separately authorized.

## Open Decisions Requiring Evidence

These are not accepted decisions yet.

### O-001 — Cleanup path for `apps/studio/` inside the S.A.G.A. repository

Decision D-009 assigns future generic image/video product ownership to RenderLab. Remaining evidence needed: whether S.A.G.A. should delete `apps/studio/`, move it under a historical/reference path, or keep it temporarily until RenderLab reaches feature parity and deployment parity.

Do not perform destructive cleanup without a focused PR that verifies RenderLab already owns the required deployment and history.

### O-002 — Current promotable S.A.G.A. release baseline

The repository has strong prior qualification evidence but no current clean-source qualification is established by the 2026-09-10 audit.

Phase 0 must identify the exact commit/configuration that can satisfy the current build/test/qualification gates before this decision can be closed.
