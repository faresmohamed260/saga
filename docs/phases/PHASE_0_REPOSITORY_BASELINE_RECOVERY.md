# Phase 0 — Repository Baseline Recovery & Requalification

**Status:** ACTIVE — REPOSITORY BASELINE RECOVERED; CLEAN-SOURCE QUALIFICATION CONTROL PLANE IN PROGRESS; PRIVATE R2 SOURCE STILL BLOCKED

## Goal

Establish a trustworthy, clean, reproducible current S.A.G.A. baseline before broad feature work resumes.

The phase succeeds when a new session can identify exactly what current committed S.A.G.A. builds, tests, runs, and qualifies; stale status documents no longer control work; unrelated repository surfaces are explicitly classified; and remaining defects can be planned from evidence rather than conversation history.

## Verified Recovery Baseline — 2026-09-10

### Repository

- Repository: `faresmohamed260/saga`
- Default branch: `main`
- Verified clean baseline through PR #141: `b416eaf0f0b2431845e8b26a4a51d315881bcfa0`
- Verified tree: `4b909b2718419a2d0f41e86d069bfabbd1e09e1d`
- Recovery/cleanup PRs #134, #135, #137, #138, #139, #140, and #141 are merged evidence.

### Local-to-GitHub recovery

- The former local Codex branch `codex/transaction-pool-rc36` and its 43 local-side divergent commits were audited and triaged.
- The old branch was closed and must not be merged wholesale because doing so would remove substantial newer GitHub work.
- Recovery inventory: `docs/recovery/LOCAL_TO_GITHUB_HANDOFF_INVENTORY.md`
- Commit triage: `docs/recovery/LOCAL_COMMIT_TRIAGE.md`
- Final handoff report: `docs/recovery/HANDOFF_REPORT_2026-09-10.md`
- Reproducibility manifest: `docs/validation/REPRODUCIBILITY.md`
- Secrets manifest: `docs/operations/GITHUB_ACTIONS_SECRETS.md`
- Protected asset manifest: `docs/operations/PROTECTED_TEST_ASSETS.md`
- Protected asset verification workflow: `.github/workflows/protected-asset-verification.yml`
- Model/provider manifest: `docs/operations/MODEL_PROVIDER_MANIFEST.md`

The project is no longer dependent on undocumented local state.

### Active architecture

The active S.A.G.A. product/runtime surfaces are:

- modular runtime packages under `packages/`;
- provider integrations under `integrations/`;
- `apps/dashboard_api/`;
- `apps/dashboard_pro/`;
- production deployment topology;
- nine-stage end-to-end orchestration;
- historical implementation isolated under `backup/reference/`.

The former `apps/studio/` generic image/video prototype is retired. Its successor is the separate `faresmohamed260/renderlab` repository. S.A.G.A. retains only visual/provider resources that serve its own narrative-to-media contracts.

### CI / deterministic recovery evidence

PR #141 at head `2bc87f62deb3e7a17d02ee41f30083ca6db292a3` passed:

- frozen dependency install;
- one Alembic migration head;
- source-secret scan;
- architecture-boundary checks;
- active backend tests;
- migration upgrade, rollback, re-upgrade, and isolated restore;
- production Compose validation;
- runtime container build;
- frontend container build;
- Required Check Compatibility / Dashboard Pro gate.

It merged as `b416eaf0f0b2431845e8b26a4a51d315881bcfa0`. A green unrelated workflow does not prove end-to-end S.A.G.A. qualification.

### Last recorded full qualification

`docs/production_qualification.md` records a 2026-08-09 accepted run of `Once Upon a Broken Heart.epub` through all nine stages with noncritical warnings.

It also explicitly records:

- backend `243 passed, 3 skipped`;
- dashboard `13 passed` and Vite build success;
- security-sensitive suite `60 passed`;
- real pipeline/provider evidence;
- **non-promotable source provenance because 574 worktree paths were pending**.

Treat this as strong behavioral evidence, not current clean-release proof.

### Protected-asset prerequisite — issue #142

Protected commercial book bytes are intentionally absent from the public repository. Recovery recorded their filenames, hashes, purposes, and intended private object keys, but did not migrate the bytes.

The first manual protected-asset verification run (`34432226628`) reached Cloudflare R2 with the required repository secrets present and failed with `403 Forbidden` on `HeadObject` for `once-upon-a-broken-heart`.

PR #141 replaced that ambiguous acquisition path with a bounded helper/workflow that:

- supports `default`, `eu`, `us`, and `fedramp` R2 endpoints;
- attempts a bounded exact-prefix listing without printing the listing;
- classifies `access_failed` separately from `object_missing`;
- distinguishes a visible object that still cannot be downloaded as `download_failed`;
- verifies the downloaded file against the committed SHA-256 and deletes temporary bytes.

Issue #142 is the active external protected-source blocker. Close it only after the selected object downloads in GitHub Actions and matches the committed hash.

### Qualification control-plane gap — issue #143

Repository audit after PR #141 found that S.A.G.A. already had `scripts/run_production_qualification.py` but did not have a GitHub Actions entrypoint capable of running the nine-stage qualification from exact committed source.

Focused work under `phase-0/clean-source-qualification-workflow` addresses that gap with:

- `.github/workflows/production-qualification.yml` — manual-only workflow with explicit live-cost confirmation;
- `scripts/check_production_qualification_readiness.py` — non-destructive fail-fast production schema/provider/pricing readiness check;
- deterministic unit coverage for readiness behavior;
- exact `GITHUB_SHA` release provenance;
- private protected-source acquisition/hash verification and unconditional cleanup;
- bounded global/stage deadlines and retries;
- no automatic deployment or release promotion.

Current nine-stage metering collapses to provider names `ollama`, `mistral`, and `modal`. Because qualification rejects unpriced charges, readiness requires valid versioned provider-wide fallback `CostRate` entries for all three. More-specific model/account rates may override those fallbacks.

## Phase Work

### 0A — Governance and handoff baseline — COMPLETE

- `AGENTS.md` established;
- `PROJECT.md` established;
- `docs/README.md` established;
- `docs/DECISIONS.md` established;
- this phase contract established;
- repository state, research state, validation state, and conversation context made explicitly distinct.

### 0B — Exact-head repository and local-divergence audit — COMPLETE

Audited:

- package/runtime inventory;
- application surfaces;
- provider integrations;
- migrations/schema ownership;
- production compose/process definitions;
- dependency locks;
- tests;
- GitHub Actions gates;
- release/qualification scripts;
- the 43 local-side commits and dirty/untracked local workspace state.

Future focused PRs may port selected local-side code/evidence only when current repository evidence justifies doing so.

### 0C — CI and reproducibility recovery — COMPLETE FOR NON-LIVE BASELINE

The deterministic local and hosted gates recorded by recovery passed. Live/provider qualification remains separate and cost/secret/asset gated.

### 0D — Documentation reconciliation — IN PROGRESS

Current handoff/governance docs supersede stale immediate-next-step text in older snapshots. Historical audits remain useful evidence but do not control current work.

The authoritative handoff is reconciled through Studio retirement, protected-storage diagnostics, and the current clean-source qualification workflow effort. Older subsystem snapshots may still contain dated historical next-step text and should be corrected only when their owning subsystem is touched.

### 0E — Surface ownership audit — COMPLETE

Ownership is resolved:

- the generic image/video product previously under `apps/studio/` evolved into the standalone `faresmohamed260/renderlab` project;
- S.A.G.A. must not continue generic RenderLab product UI/features internally;
- `apps/studio/`, Studio-only workflows/docs/helpers, and Studio-owned product schema definitions were removed in PR #139;
- reusable S.A.G.A. visual provider infrastructure remains because it serves stage 7 of the S.A.G.A. pipeline;
- public Modal worker routing metadata is owned by `config/modal-worker-registry.json`;
- retained live FLUX deployments are manual-only after PR #140;
- no destructive operation was performed against Studio-era remote database/storage/compute resources as part of repository cleanup.

### 0F — Clean-source requalification — IN PROGRESS

Repository readiness work:

1. protected-R2 diagnostic acquisition path — **COMPLETE through PR #141**;
2. clean-source GitHub qualification workflow + readiness gate — **IN PROGRESS under issue #143**;
3. protected source availability/hash verification — **BLOCKED externally under issue #142**;
4. actual exact-head nine-stage qualification — **NOT YET RUN**.

Qualification workflow preconditions include:

- production Supabase DB/API/service-role configuration and current schema;
- persisted `modal_xcore_litbank`, `modal_comfyui`, and `modal_kokoro_tts` account credentials;
- active persisted Ollama/gpt-oss configuration for current default reasoning stages;
- Mistral persisted or available via `MISTRAL_API_KEY`;
- versioned provider-wide pricing fallbacks for `ollama`, `mistral`, and `modal`;
- one reachable/hash-valid protected source;
- explicit live-cost authorization.

If a live provider remains unavailable, record the exact external blocker and complete all unaffected validation rather than fabricating qualification.

## Explicitly Out of Scope

- broad architecture redesign;
- replacing LangGraph, Supabase, Modal, XCore, ComfyUI, Qwen, TTS, or other providers without evidence and explicit scope;
- implementing research proposals merely because they appear promising;
- broad identity-resolver redesign before baseline recovery is closed;
- deleting `backup/reference/` historical code;
- production deployment or promotion;
- destructive deletion of existing Studio-era remote database/storage/compute resources;
- unrelated new product features;
- generic RenderLab product development inside S.A.G.A.

## Validation Matrix

| Surface | Required evidence |
| --- | --- |
| Governance | New-session startup path is complete and internally consistent |
| Python dependency graph | Frozen install succeeds or blocker is documented |
| Backend | Full repository pytest gate passes or failures are classified/fixed |
| Architecture boundaries | Legacy/reference dependency guard passes |
| Migrations | Alembic/schema validation gate passes |
| Dashboard Pro | `npm ci`, tests, production build pass |
| CI | Relevant core workflows attach to exact head and succeed |
| Providers | Configuration requirements are documented; live checks only where authorized/available |
| Protected storage | R2 access/object presence/download/hash outcomes are distinguishable without exposing protected bytes or secrets |
| Qualification readiness | Production schema, provider config, pricing coverage, protected-source handling, explicit cost authorization, and exact-SHA provenance are checked before live work |
| Qualification | Exact committed source/configuration/release identity recorded; no dirty-worktree provenance; evaluator accepts persisted report |
| Documentation | README/project/phase/qualification state agree on what is current |
| Studio split | `apps/studio/` and Studio-only automation are absent; reusable stage-7 resources have S.A.G.A.-owned contracts/configuration |

## Exit Criteria

Phase 0 is complete only when:

1. repository-first governance remains consistent with current source;
2. current active/historical/experimental surfaces are classified;
3. exact clean committed source passes required non-live core gates, or every remaining failure is a specific accepted blocker;
4. current documentation no longer points future sessions to stale immediate-next-step instructions;
5. the retired Studio product surface remains removed without breaking the retained S.A.G.A. visual runtime;
6. the clean-source qualification workflow/readiness path is merged and validated;
7. protected-asset verification succeeds;
8. the required exact-head clean-source S.A.G.A. qualification runs and its persisted report is accepted, or a precise external prerequisite is explicitly accepted as deferred;
9. `PROJECT.md` records verified completion evidence and names the next phase from actual results.

## Current Next Step

1. validate and merge issue #143 / `phase-0/clean-source-qualification-workflow` with Backend Architecture CI and Required Check Compatibility green;
2. configure legitimate versioned provider-wide `SAGA_PROVIDER_COST_RATES_JSON` fallbacks for `ollama`, `mistral`, and `modal`; do not invent prices;
3. resolve issue #142 by manually running the revised protected-asset verification and repairing the exact reported storage category;
4. verify the protected source hash;
5. verify persisted provider/reasoning readiness;
6. manually dispatch the clean-source production qualification on the exact intended `main` SHA with explicit live-cost authorization;
7. record the resulting qualification evidence and only then close Phase 0 / choose the next implementation phase.

## Next Phase Rule

Do not fully specify the next implementation phase yet.

Phase 0 evidence determines whether the next priority is runtime/deployment repair, provider requalification, identity quality improvement, visual quality hardening, cost/usage telemetry, or another concrete blocker discovered by qualification.
