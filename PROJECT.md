# S.A.G.A. Project

S.A.G.A. (Story Analysis, Generation, and Archives) analyzes source books into evidence-backed canon, generates grounded narrative and multimedia outputs, and packages auditable release artifacts.

This file is the short current-state handoff for humans and AI sessions. Detailed subsystem behavior belongs in the existing documents indexed by `docs/README.md`.

## Product / System Direction

The active S.A.G.A. architecture is contract-driven and modular rather than a monolithic book-processing application.

Primary active surfaces are:

- `packages/` — reusable runtimes for agents, reasoning, retrieval, persistence, execution, identity, generation, observability, lineage, qualification, and deployment;
- `integrations/` — provider implementations, including ComfyUI, Qwen, XCore/Modal, and audio integrations;
- `apps/dashboard_api/` — stateless FastAPI control/query surface;
- `apps/dashboard_pro/` — operator dashboard;
- `deploy/production/` — production process/container topology;
- `migrations/` and `supabase/` — active persistence/schema assets;
- `tests/` and `scripts/` — automated validation and bounded operational entrypoints.

`backup/reference/` is inert historical reference material and must not become an active dependency.

The former `apps/studio/` generic image/video prototype has been retired from S.A.G.A. Its standalone successor is `faresmohamed260/renderlab`. S.A.G.A. keeps reusable visual-generation provider infrastructure only where it serves S.A.G.A.'s narrative-to-media pipeline. Public Modal worker routing metadata is owned by `config/modal-worker-registry.json`, not by an application UI.

## Core Pipeline

The repository documents a nine-stage production path:

1. source ingestion and analysis foundation;
2. identity resolution;
3. canon extraction;
4. character/world modeling;
5. generation planning;
6. narrative generation and semantic support;
7. visual generation and image QA;
8. audiobook synthesis and transcription QA;
9. EPUB, manifest, lineage, and qualification reporting.

Generation-side systems are expected to consume persisted canon/retrieval artifacts rather than repeatedly reconstructing canon from raw source text.

## Stack

### Python/runtime

- Python `>=3.10`
- package version currently declared as `0.2.0rc20`
- `uv`-locked Python dependency workflow
- FastAPI
- LangGraph
- PostgreSQL/Supabase + pgvector/object storage through persistence contracts
- Alembic migrations
- provider integrations for reasoning, identity, visual generation, audio, and external compute

### Operator UI

- React/Vite dashboard under `apps/dashboard_pro/`

## Verified Recovery Baseline — 2026-09-10

The local-to-GitHub handoff/recovery work is complete through the following merged pull requests:

- PR #134 — repository governance, recovery manifests, reproducibility, secrets/assets/model documentation;
- PR #135 — commit-by-commit triage of the 43 divergent local-side commits;
- PR #137 — protected asset verification workflow/manifest and explicit RenderLab ownership for future generic image/video product work;
- PR #138 — recorded the first real GitHub protected-asset verification result.

Verified `main` immediately before the Studio retirement cleanup:

- commit: `1944ea3a1c7d6733236869cec2e030dad4fdd470`;
- tree: `fcba8e1e175b3bc9c657f6c31a4e60e32c9af9a2`;
- commit message: `docs: record protected asset verification result (#138)`.

Recovery validation already recorded on GitHub includes successful backend tests, migration checks, container builds, Dashboard Pro compatibility, and the then-attached Vercel status. Local recovery validation also recorded a frozen `uv` install, one Alembic head, source-secret scan, complete backend test gate, Dashboard Pro tests/build, production dependency audit, and production Compose validation.

The repository is no longer dependent on undocumented state from the former local Codex checkout. Historical recovery evidence is indexed under `docs/recovery/`.

## Studio Retirement Boundary

The retired Studio product surface is not part of S.A.G.A.'s active architecture.

The focused cleanup removes:

- `apps/studio/`;
- Studio-only UI/product documentation;
- Studio-only GitHub Actions and patch helpers;
- Studio-owned Supabase migration definitions that are not part of the S.A.G.A. core schema.

The cleanup preserves and rehomes reusable S.A.G.A. infrastructure:

- `packages/visual_generation` and the stage-7 visual contract;
- `packages/modal_runtime`;
- `integrations/comfyui`;
- `integrations/qwen`;
- `config/modal-worker-ecosystems.json`;
- `config/modal-worker-registry.json` for non-secret worker routing metadata;
- Modal worker inventory/maintenance/provisioning and bounded live-smoke tooling after removal of Studio branch/path dependencies.

This repository cleanup does **not** delete live cloud resources or data. Existing Studio-era Supabase tables, R2 objects/buckets, Modal deployments, and RenderLab resources require separate explicit operations if they are ever migrated or decommissioned.

## Last Recorded End-to-End S.A.G.A. Qualification

`docs/production_qualification.md` records an accepted real-book run from 2026-08-09 using `Once Upon a Broken Heart.epub` through all nine pipeline stages.

The same record explicitly states that the run was **not promotable** because its source worktree was not a clean committed CI revision and reported 574 pending worktree paths at qualification time.

Therefore the run remains valuable behavioral evidence, but it is not proof that current `main` is a clean, reproducible, promotable S.A.G.A. release.

## Current External Blocker

The protected-asset verification workflow is present and has run from GitHub. The first real remote run (`34432226628`) reached Cloudflare R2 but failed with `403 Forbidden` while reading the documented protected-book object key.

This means:

- GitHub-side protected-asset workflow wiring exists;
- the remaining prerequisite is R2 object placement/read permission for the configured repository credentials;
- protected-book clean-source qualification must not be claimed until that prerequisite is fixed and the workflow succeeds.

## Active Phase

**Phase 0 — Repository Baseline Recovery & Requalification**

Contract: `docs/phases/PHASE_0_REPOSITORY_BASELINE_RECOVERY.md`

Status: **ACTIVE — REPOSITORY CONTINUITY RECOVERED; STUDIO SPLIT RESOLVED; PROTECTED-ASSET REQUALIFICATION BLOCKED BY R2 ACCESS**

Phase 0 is no longer about reconstructing undocumented local state. The remaining work is to finish exact-head requalification from the clean repository and address only evidence-backed blockers.

## Immediate Next Step

1. validate and merge the focused Studio retirement cleanup with S.A.G.A. core CI green;
2. verify no active code/workflow path depends on `apps/studio/` and that reusable worker-fleet resources are owned by S.A.G.A. config/runtime paths;
3. fix the documented Cloudflare R2 protected-asset read/object-placement issue;
4. rerun `Protected Asset Verification` from GitHub;
5. run the bounded clean-source S.A.G.A. qualification required by the current production contracts;
6. bind the resulting evidence to the exact commit/configuration and update this file plus the Phase 0 contract before declaring Phase 0 complete.

## Development Commands

Python:

```powershell
uv sync --frozen --extra dev
uv run pytest -q
```

Operator dashboard:

```powershell
cd apps\dashboard_pro
npm ci
npm test -- --run
npm run build
```

API after configuring the required persistence environment:

```powershell
uv run saga-runtime-api
```

Production topology configuration is documented in `docs/deployment_operations.md`. Do not deploy merely because local/CI validation passes.

## Working Convention

The repository must remain sufficient for a new session with no conversation history to determine:

- what S.A.G.A. currently is;
- what is active vs historical/experimental;
- what has actually been validated;
- what phase is active;
- what remains blocked or unresolved;
- what exact work should happen next.

Durable project state belongs in the repository, not only in chat history.
