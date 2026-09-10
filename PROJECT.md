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

Repository continuity, surface ownership, and protected-storage diagnostics are complete through these merged pull requests:

- PR #134 — repository governance, recovery manifests, reproducibility, secrets/assets/model documentation;
- PR #135 — commit-by-commit triage of the 43 divergent local-side commits;
- PR #137 — protected asset verification workflow/manifest and explicit RenderLab ownership for future generic image/video product work;
- PR #138 — recorded the first real GitHub protected-asset verification result;
- PR #139 — retired `apps/studio/` and rehomed reusable worker metadata under S.A.G.A.-owned configuration;
- PR #140 — made retained live FLUX runtime/gateway deployments manual-only;
- PR #141 — added bounded protected-R2 access/object/download diagnostics and jurisdiction-aware acquisition.

Verified current clean `main` baseline through PR #141:

- commit: `b416eaf0f0b2431845e8b26a4a51d315881bcfa0`;
- tree: `4b909b2718419a2d0f41e86d069bfabbd1e09e1d`;
- commit message: `Diagnose protected R2 asset availability before qualification (#141)`.

PR #141 passed Backend Architecture CI (active backend tests, migration upgrade/rollback/re-upgrade and isolated restore, production Compose validation, runtime image build, frontend image build) plus Required Check Compatibility before merge.

The repository is no longer dependent on undocumented state from the former local Codex checkout. Historical recovery evidence is indexed under `docs/recovery/`.

## Studio Retirement Boundary

The retired Studio product surface is not part of S.A.G.A.'s active architecture.

Removed from S.A.G.A.:

- `apps/studio/`;
- Studio-only UI/product documentation;
- Studio-only GitHub Actions and patch helpers;
- Studio-owned Supabase migration definitions that were not part of the S.A.G.A. core schema.

Preserved/reowned by S.A.G.A. where used by the narrative-to-media pipeline:

- `packages/visual_generation` and the stage-7 visual contract;
- `packages/modal_runtime`;
- `integrations/comfyui`;
- `integrations/qwen`;
- `config/modal-worker-ecosystems.json`;
- `config/modal-worker-registry.json`;
- Modal worker inventory/maintenance/provisioning and bounded live-smoke tooling.

Existing Studio-era remote database/storage/compute resources were not destructively removed as part of the repository cleanup.

## Last Recorded End-to-End S.A.G.A. Qualification

`docs/production_qualification.md` records an accepted real-book run from 2026-08-09 using `Once Upon a Broken Heart.epub` through all nine pipeline stages.

The same record explicitly states that the run was **not promotable** because its source worktree was not a clean committed CI revision and reported 574 pending worktree paths at qualification time.

Therefore the run remains valuable behavioral evidence, but it is not proof that current `main` is a clean, reproducible, promotable S.A.G.A. release. Because the production qualifier enforces a freshness guard by source filename/SHA, that historical input must not be assumed to be eligible for the next clean qualification against the same production persistence.

## Current Qualification Blockers / Readiness

Protected-book qualification remains externally blocked until at least one authorized manifest asset is both reachable/hash-valid in private storage **and fresh in the production library**. Issue #142 tracks that prerequisite.

The first GitHub protected-asset verification run (`34432226628`) reached R2 with all required secrets present and received `403 Forbidden` from the old `HeadObject` path. PR #141 replaced that ambiguous path with diagnostics that can distinguish:

- `access_failed` — account/bucket/jurisdiction/token scope/Object Read problem;
- `object_missing` — exact manifest key absent after successful prefix listing;
- `download_failed` — object visible but GetObject/download fails;
- success — bytes download and still must pass the committed SHA-256 check.

Repository audit also found that clean-source qualification lacked a GitHub Actions control plane. Issue #143 is being implemented by PR #145 on `phase-0/clean-source-qualification-workflow`.

The intended manual qualification gate now requires, before protected-book processing or live reasoning/provider requests:

- explicit authorization for live provider cost;
- exact `GITHUB_SHA` / clean tracked checkout provenance;
- a single explicitly selected protected manifest asset;
- proof that the selected filename/SHA does not already exist in production persistence;
- production Supabase schema/API/service-role readiness;
- persisted provider credentials for `modal_xcore_litbank`, `modal_comfyui`, and `modal_kokoro_tts`;
- an actual usable Ollama API key for the current default gpt-oss stages, not merely an Ollama provider-config row;
- Mistral configured through persistence or `MISTRAL_API_KEY` for current Mistral reasoning/vision/transcription stages;
- versioned provider-wide pricing fallbacks for metered `ollama`, `mistral`, and `modal` usage;
- the selected protected EPUB downloaded from private R2 and hash-verified.

If every currently listed protected asset is already present in production persistence, add metadata for another authorized unseen source to the manifest and private storage. Never commit the protected bytes.

## Active Phase

**Phase 0 — Repository Baseline Recovery & Requalification**

Contract: `docs/phases/PHASE_0_REPOSITORY_BASELINE_RECOVERY.md`

Status: **ACTIVE — REPOSITORY BASELINE RECOVERED; CLEAN-SOURCE QUALIFICATION CONTROL PLANE IN PR #145; FRESH PRIVATE SOURCE / LIVE CONFIGURATION REMAINS**

Phase 0 is no longer about reconstructing undocumented local state. The remaining work is to validate/merge the manual clean-source qualification workflow, resolve its private-source and provider/pricing prerequisites, run exact-head qualification, and bind the result to committed source/configuration.

## Immediate Next Step

1. validate and merge PR #145 / issue #143 with core CI green;
2. configure the actual S.A.G.A. production Supabase database/API/service-role path used by qualification;
3. configure real, versioned provider-wide `SAGA_PROVIDER_COST_RATES_JSON` fallbacks for `ollama`, `mistral`, and `modal` plus any desired specific overrides; do not invent prices;
4. ensure persisted Modal provider rows and a usable Ollama credential plus Mistral access are qualification-ready;
5. choose a protected manifest asset that passes the production freshness preflight; do not assume the historical `once-upon-a-broken-heart` asset is fresh;
6. resolve issue #142 for that fresh asset by running `Protected Asset Verification` with the correct R2 jurisdiction and fixing the exact reported category;
7. make the selected object download successfully and match its committed SHA-256;
8. manually dispatch **Clean-Source Production Qualification** on the exact `main` commit intended for evidence and explicitly authorize live cost;
9. bind the resulting persisted report to the exact commit/configuration and update this file plus Phase 0 / qualification evidence before declaring Phase 0 complete.

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
