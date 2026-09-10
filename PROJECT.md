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

Generation-side systems consume persisted canon/retrieval artifacts rather than repeatedly reconstructing canon from raw source text.

## Stack

- Python `>=3.10`; package version currently declared as `0.2.0rc20`
- `uv`-locked Python dependency workflow
- FastAPI and LangGraph
- PostgreSQL/Supabase + pgvector/object storage through persistence contracts
- Alembic migrations
- provider integrations for reasoning, identity, visual generation, audio, and external compute
- React/Vite operator dashboard under `apps/dashboard_pro/`

## Verified Recovery Baseline — 2026-09-10

Repository continuity, surface ownership, protected-storage diagnostics, and the clean-source qualification control plane are complete through:

- PR #134 — repository governance, recovery manifests, reproducibility, secrets/assets/model documentation;
- PR #135 — commit-by-commit triage of the 43 divergent local-side commits;
- PR #137 — protected asset verification workflow/manifest and explicit RenderLab ownership for generic image/video product work;
- PR #138 — recorded the first real protected-asset verification result;
- PR #139 — retired `apps/studio/` and rehomed reusable S.A.G.A. worker metadata;
- PR #140 — made retained live FLUX runtime/gateway deployments manual-only;
- PR #141 — added bounded protected-R2 access/object/download diagnostics and jurisdiction-aware acquisition;
- PR #145 — added the manual, `main`-only, exact-SHA clean-source production qualification workflow and fail-fast source/provider/pricing readiness gate.

Verified current clean `main` baseline:

- commit: `67e852116af2efea9484daa6ddb343397c5322a9`;
- tree: `f5cf499f280fbc2fb12c7e1a1bcafeb8577833b9`;
- commit message: `Add clean-source production qualification workflow (#145)`.

PR #145 final head `8b00e732bfeda213b77dc77a44ebc60fabc46a8e` passed Backend Architecture CI and Required Check Compatibility. After merge, `main` push runs `34509072301` (Required Check Compatibility) and `34509072302` (Backend Architecture CI) also passed. The paid/live **Clean-Source Production Qualification** did not auto-run.

Detailed external-readiness evidence is recorded in `docs/validation/PHASE_0_EXTERNAL_READINESS_2026-09-10.md`.

## Studio / RenderLab Boundary

The retired Studio product surface is not part of active S.A.G.A. architecture. `apps/studio/`, Studio-only workflows/docs/helpers, and Studio-owned product persistence definitions were removed. The separate successor is `faresmohamed260/renderlab`.

S.A.G.A. retains only provider/runtime resources it owns and consumes for the narrative-to-media path, including `packages/visual_generation`, `packages/modal_runtime`, `integrations/comfyui`, `integrations/qwen`, and S.A.G.A.-owned worker configuration.

Existing Studio-era remote database/storage/compute resources were not destructively removed during repository cleanup.

## Last Recorded End-to-End Qualification

`docs/production_qualification.md` records an accepted 2026-08-09 real-book run through all nine stages. It remains strong behavioral evidence but **not promotable release proof** because its source worktree contained 574 pending paths.

The current production qualifier also enforces source freshness by filename/SHA. That historical input must not be assumed eligible for a new clean qualification against the same production library.

## Current Phase-0 External Blockers

Issue #142 remains open. The repository control plane is ready, but the external production environment is not.

Read-only GitHub Actions diagnostics on 2026-09-10 established:

- no `SAGA_SUPABASE_DB_URL` or explicit S.A.G.A. DB host/component configuration is currently available to Actions;
- legacy `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are present, but the only connected Supabase project inspected is RenderLab/retired-Studio infrastructure and is **not** S.A.G.A. production;
- source freshness and persisted S.A.G.A. provider readiness therefore cannot currently be proven;
- `SAGA_PROVIDER_COST_RATES_JSON` is absent;
- explicit `OLLAMA_API_KEY` and `MISTRAL_API_KEY` fallbacks are absent; persisted alternatives remain unknown until the real S.A.G.A. DB is connected;
- the R2 credential-name set is present, but bounded bucket listing returns `access_failed` for `default`, `eu`, `us`, and `fedramp`, so no supported jurisdiction is currently accessible;
- because bucket listing fails, there is **no evidence yet that an individual protected object is missing**;
- historical pre-retirement `apps/studio/api/_r2.js` used the exact same `R2_*` environment-variable namespace and defaulted to bucket `saga-studio-media`. This proves namespace reuse from Studio-era infrastructure, not that current secret values are identical.

The diagnostic runs were `34514215596` and `34514460132`. They made no paid provider calls, uploaded no protected artifacts, and the temporary diagnostic workflow was removed after use.

## Active Phase

**Phase 0 — Repository Baseline Recovery & Requalification**

Contract: `docs/phases/PHASE_0_REPOSITORY_BASELINE_RECOVERY.md`

Status: **ACTIVE — REPOSITORY/CONTROL-PLANE RECOVERY COMPLETE; EXTERNAL PRODUCTION CONFIGURATION + FRESH PROTECTED SOURCE BLOCK QUALIFICATION**

Phase 0 is no longer about reconstructing repository state. The remaining work is external qualification readiness and one exact-head clean-source qualification.

## Immediate Next Step

1. configure the actual S.A.G.A. production Postgres/Supabase DB path in GitHub Actions, not the connected RenderLab/Studio project;
2. configure legitimate versioned provider-wide `SAGA_PROVIDER_COST_RATES_JSON` fallbacks for `ollama`, `mistral`, and `modal`; do not invent prices;
3. verify the real persisted Modal/reasoning configuration, including a usable Ollama credential and Mistral access;
4. reconfigure/rotate the repository R2 credentials so they explicitly target a S.A.G.A.-owned private protected-assets bucket/prefix with List/Get access;
5. rerun `Protected Asset Verification` and require bucket access before classifying object presence;
6. choose a manifest asset that passes production source-freshness checks; add metadata for another authorized unseen source if necessary, never the protected bytes;
7. require private download plus committed SHA-256 verification;
8. only after those prerequisites are green, manually dispatch **Clean-Source Production Qualification** from exact `main` and separately set `confirm_live_cost=true`;
9. bind the persisted qualification report to the exact source/configuration and update the Phase-0 evidence before declaring Phase 0 complete.

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

The repository must remain sufficient for a new session with no conversation history to determine what S.A.G.A. is, what is active/historical, what has actually been validated, what phase is active, what remains blocked, and what exact work happens next.

Durable project state belongs in the repository, not only in chat history.
