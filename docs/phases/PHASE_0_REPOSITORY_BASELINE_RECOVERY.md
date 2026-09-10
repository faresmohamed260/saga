# Phase 0 — Repository Baseline Recovery & Requalification

**Status:** ACTIVE — REPOSITORY CONTINUITY RECOVERED; STUDIO SPLIT RESOLVED; PROTECTED-ASSET REQUALIFICATION BLOCKED BY R2 ACCESS

## Goal

Establish a trustworthy, clean, reproducible current S.A.G.A. baseline before broad feature work resumes.

The phase succeeds when a new session can identify exactly what current committed S.A.G.A. builds, tests, runs, and qualifies; stale status documents no longer control work; unrelated repository surfaces are explicitly classified; and remaining defects can be planned from evidence rather than conversation history.

## Verified Recovery Baseline — 2026-09-10

### Repository

- Repository: `faresmohamed260/saga`
- Default branch: `main`
- Verified pre-Studio-cleanup HEAD: `1944ea3a1c7d6733236869cec2e030dad4fdd470`
- Verified pre-Studio-cleanup tree: `fcba8e1e175b3bc9c657f6c31a4e60e32c9af9a2`
- PRs #134, #135, #137, and #138 are merged recovery evidence.

### Local-to-GitHub recovery

- The former local Codex branch `codex/transaction-pool-rc36` and its 43 local-side divergent commits were audited and triaged.
- The old branch must not be merged wholesale because doing so would remove substantial newer GitHub work.
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

The former `apps/studio/` generic image/video prototype is not a S.A.G.A. product surface. Its successor is the separate `faresmohamed260/renderlab` repository.

### CI / deterministic recovery evidence

Recovery validation recorded:

- clean frozen `uv` dependency install;
- one Alembic head `202608090400`;
- source-secret scan with no findings;
- architecture-boundary tests;
- full backend tests (`338 passed / 3 skipped` in the recovery record);
- Dashboard Pro tests and production build;
- production dependency audit with no high vulnerabilities;
- production Compose configuration validation;
- successful Backend Architecture CI `test`, `migrations`, and `containers` jobs on recovery PR heads;
- successful Required Check Compatibility / Dashboard Pro gate.

A green unrelated workflow does not prove end-to-end S.A.G.A. qualification.

### Last recorded full qualification

`docs/production_qualification.md` records a 2026-08-09 accepted run of `Once Upon a Broken Heart.epub` through all nine stages with noncritical warnings.

It also explicitly records:

- backend `243 passed, 3 skipped`;
- dashboard `13 passed` and Vite build success;
- security-sensitive suite `60 passed`;
- real pipeline/provider evidence;
- **non-promotable source provenance because 574 worktree paths were pending**.

Treat this as strong behavioral evidence, not current clean-release proof.

### Protected-asset prerequisite

The manual protected-asset verification workflow exists and ran from GitHub. Run `34432226628` reached Cloudflare R2 but failed with `403 Forbidden` while reading the documented object key.

Therefore the remaining protected-book prerequisite is specific: correct the object placement/read permissions for the configured repository credentials and rerun the workflow. Do not claim protected-book qualification until that succeeds.

## Phase Work

### 0A — Governance and handoff baseline — COMPLETE

- `AGENTS.md` established;
- `PROJECT.md` established;
- `docs/README.md` established;
- `docs/DECISIONS.md` established;
- this phase contract established;
- repository state, research state, validation state, and conversation context made explicitly distinct.

### 0B — Exact-head repository and local-divergence audit — COMPLETE FOR RECOVERY

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

Current handoff/governance docs now supersede stale immediate-next-step text in older snapshots. Historical audits remain useful evidence but do not control current work.

The Studio retirement cleanup updates the authoritative docs to remove the former prototype from active S.A.G.A. architecture while preserving historical recovery evidence.

### 0E — Surface ownership audit — COMPLETE

Ownership is resolved:

- the generic image/video product previously under `apps/studio/` evolved into the standalone `faresmohamed260/renderlab` project;
- S.A.G.A. must not continue generic RenderLab product UI/features internally;
- the owner explicitly authorized focused removal of the retired Studio surface;
- reusable S.A.G.A. visual provider infrastructure remains because it serves stage 7 of the S.A.G.A. pipeline;
- public Modal worker routing metadata is rehomed from the Studio app to `config/modal-worker-registry.json`;
- Studio-only UI docs, patch workflows/helpers, and Studio product schema migration definitions are removed from S.A.G.A.;
- no destructive operation is performed against live Studio-era Supabase/R2/Modal resources as part of repository cleanup.

### 0F — Clean-source requalification — BLOCKED ON PROTECTED ASSET ACCESS

After the repository gates are green on the Studio-retirement head and protected assets are available:

- rerun protected asset verification;
- perform the bounded qualification path required by current production contracts;
- bind evidence to the exact commit SHA/configuration/release identity;
- record warnings and manual-review limitations honestly;
- do not promote/deploy merely because qualification passes.

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
| Qualification | Exact committed source is recorded; no dirty-worktree provenance |
| Documentation | README/project/roadmap/qualification state agree on what is current |
| Studio split | `apps/studio/` and Studio-only automation are absent; reusable stage-7 resources have S.A.G.A.-owned contracts/configuration |

## Exit Criteria

Phase 0 is complete only when:

1. repository-first governance remains consistent with current source;
2. current active/historical/experimental surfaces are classified;
3. exact clean committed source passes required non-live core gates, or every remaining failure is a specific accepted blocker;
4. current documentation no longer points future sessions to stale immediate-next-step instructions;
5. the retired Studio product surface is removed without breaking the retained S.A.G.A. visual runtime;
6. protected-asset verification succeeds and the required clean-source S.A.G.A. qualification runs, or a precise external prerequisite is explicitly accepted as deferred;
7. `PROJECT.md` records verified completion evidence and names the next phase from actual results.

## Current Next Step

1. land and validate the focused Studio retirement cleanup;
2. verify active source/workflows no longer depend on `apps/studio/`;
3. fix the Cloudflare R2 protected-book object/read-permission issue;
4. rerun the manual protected-asset verification workflow;
5. run bounded clean-source S.A.G.A. qualification;
6. update `PROJECT.md`, this phase record, and qualification evidence from the exact validated head;
7. only then choose and expand the next implementation phase from evidence.

## Next Phase Rule

Do not fully specify the next implementation phase yet.

Phase 0 evidence determines whether the next priority is runtime/deployment repair, provider requalification, identity quality improvement, visual quality hardening, cost/usage telemetry, or another concrete blocker discovered by qualification.
