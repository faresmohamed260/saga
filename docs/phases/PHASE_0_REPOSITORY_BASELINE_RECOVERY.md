# Phase 0 — Repository Baseline Recovery & Requalification

**Status:** ACTIVE — REPOSITORY CONTINUITY RECOVERED; STUDIO SPLIT COMPLETE; PROTECTED-ASSET STORAGE DIAGNOSIS / REQUALIFICATION REMAINS

## Goal

Establish a trustworthy, clean, reproducible current S.A.G.A. baseline before broad feature work resumes.

The phase succeeds when a new session can identify exactly what current committed S.A.G.A. builds, tests, runs, and qualifies; stale status documents no longer control work; unrelated repository surfaces are explicitly classified; and remaining defects can be planned from evidence rather than conversation history.

## Verified Recovery Baseline — 2026-09-10

### Repository

- Repository: `faresmohamed260/saga`
- Default branch: `main`
- Verified clean baseline through PR #140: `961e679cd98405822f80def395ea83a8b43231d9`
- Verified tree: `92463b32f5e090a65900dcafb165105d1b1f5870`
- Recovery/cleanup PRs #134, #135, #137, #138, #139, and #140 are merged evidence.

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

On exact clean baseline `961e679cd98405822f80def395ea83a8b43231d9`, GitHub validation passed:

- frozen dependency install as part of Backend Architecture CI;
- one Alembic migration head;
- source-secret scan;
- architecture-boundary checks;
- active backend tests;
- migration upgrade, rollback, re-upgrade, and isolated restore;
- production Compose validation;
- runtime container build;
- frontend container build;
- Required Check Compatibility / Dashboard Pro gate.

PR #140 also proved that ordinary `main` merges no longer auto-trigger the retained FLUX live deployment workflows; those are explicit/manual operations.

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

Protected commercial book bytes are intentionally absent from the public repository. Recovery recorded their filenames, hashes, purposes, and intended private object keys, but did not migrate the bytes.

The first manual protected-asset verification run (`34432226628`) reached Cloudflare R2 with the required repository secrets present and failed with `403 Forbidden` on `HeadObject` for `once-upon-a-broken-heart`.

The old workflow could not distinguish among:

- wrong account/bucket/token scope or insufficient Object Read permission;
- wrong R2 jurisdiction endpoint;
- missing object at the committed manifest key.

Phase 0 therefore hardens the protected-asset acquisition gate before assigning the blocker to one cause. The revised workflow/helper:

- supports `default`, `eu`, `us`, and `fedramp` R2 endpoints;
- attempts a bounded exact-prefix listing without printing the listing;
- classifies bucket/credential/jurisdiction access separately from an absent manifest object;
- distinguishes a visible object that still cannot be downloaded;
- continues to verify the downloaded file against the committed SHA-256 and delete temporary bytes.

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

The current authoritative handoff is reconciled through Studio retirement and the protected-asset diagnostic work. Older subsystem snapshots may still contain dated historical next-step text and should be corrected only when their owning subsystem is touched.

### 0E — Surface ownership audit — COMPLETE

Ownership is resolved:

- the generic image/video product previously under `apps/studio/` evolved into the standalone `faresmohamed260/renderlab` project;
- S.A.G.A. must not continue generic RenderLab product UI/features internally;
- `apps/studio/`, Studio-only workflows/docs/helpers, and Studio-owned product schema definitions were removed in PR #139;
- reusable S.A.G.A. visual provider infrastructure remains because it serves stage 7 of the S.A.G.A. pipeline;
- public Modal worker routing metadata is owned by `config/modal-worker-registry.json`;
- retained live FLUX deployments are manual-only after PR #140;
- no destructive operation was performed against Studio-era remote database/storage/compute resources as part of repository cleanup.

### 0F — Clean-source requalification — IN PROGRESS; BLOCKED ON PROTECTED ASSET AVAILABILITY

Required sequence:

1. land the protected-R2 diagnostic helper/workflow with core CI green;
2. rerun the protected asset verification for `once-upon-a-broken-heart` using the correct jurisdiction;
3. if the result is `access_failed`, repair account/bucket/jurisdiction/token scope;
4. if the result is `object_missing`, migrate the authorized protected bytes to the committed manifest key outside the public repository;
5. if the result is `download_failed`, repair object read access;
6. once the object downloads and its SHA-256 matches, perform the bounded qualification path required by current production contracts;
7. bind evidence to the exact commit SHA/configuration/release identity;
8. record warnings and manual-review limitations honestly;
9. do not promote/deploy merely because qualification passes.

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
| Qualification | Exact committed source is recorded; no dirty-worktree provenance |
| Documentation | README/project/roadmap/qualification state agree on what is current |
| Studio split | `apps/studio/` and Studio-only automation are absent; reusable stage-7 resources have S.A.G.A.-owned contracts/configuration |

## Exit Criteria

Phase 0 is complete only when:

1. repository-first governance remains consistent with current source;
2. current active/historical/experimental surfaces are classified;
3. exact clean committed source passes required non-live core gates, or every remaining failure is a specific accepted blocker;
4. current documentation no longer points future sessions to stale immediate-next-step instructions;
5. the retired Studio product surface remains removed without breaking the retained S.A.G.A. visual runtime;
6. protected-asset verification succeeds and the required clean-source S.A.G.A. qualification runs, or a precise external prerequisite is explicitly accepted as deferred;
7. `PROJECT.md` records verified completion evidence and names the next phase from actual results.

## Current Next Step

1. merge and validate the protected-R2 diagnostic helper/workflow;
2. dispatch the protected-asset verification for `once-upon-a-broken-heart`;
3. fix the exact category reported by that run rather than treating every 403 as the same failure;
4. rerun until protected asset acquisition and hash verification succeed;
5. run bounded clean-source S.A.G.A. qualification;
6. update `PROJECT.md`, this phase record, and qualification evidence from the exact validated head;
7. only then choose and expand the next implementation phase from evidence.

## Next Phase Rule

Do not fully specify the next implementation phase yet.

Phase 0 evidence determines whether the next priority is runtime/deployment repair, provider requalification, identity quality improvement, visual quality hardening, cost/usage telemetry, or another concrete blocker discovered by qualification.
