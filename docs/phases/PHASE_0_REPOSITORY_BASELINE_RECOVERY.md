# Phase 0 — Repository Baseline Recovery & Requalification

**Status:** ACTIVE — REPOSITORY/CONTROL-PLANE RECOVERY COMPLETE; EXTERNAL PRODUCTION CONFIGURATION + FRESH PROTECTED SOURCE BLOCK QUALIFICATION

## Goal

Establish a trustworthy, clean, reproducible current S.A.G.A. baseline before broad feature work resumes.

The phase succeeds when a new session can identify exactly what current committed S.A.G.A. builds, tests, runs, and qualifies; stale status documents no longer control work; unrelated repository surfaces are explicitly classified; and remaining defects can be planned from evidence rather than conversation history.

## Verified Repository Baseline — 2026-09-10

- Repository: `faresmohamed260/saga`
- Default branch: `main`
- Verified clean baseline through PR #145: `67e852116af2efea9484daa6ddb343397c5322a9`
- Verified tree: `f5cf499f280fbc2fb12c7e1a1bcafeb8577833b9`
- Recovery/cleanup/control-plane PRs #134, #135, #137, #138, #139, #140, #141, and #145 are merged evidence.

PR #145 final head `8b00e732bfeda213b77dc77a44ebc60fabc46a8e` passed Backend Architecture CI and Required Check Compatibility. Its merged `main` commit also passed push-time Required Check Compatibility run `34509072301` and Backend Architecture CI run `34509072302`.

The manual clean-source qualification workflow did not auto-run from the merge.

Detailed post-merge external-readiness evidence: `docs/validation/PHASE_0_EXTERNAL_READINESS_2026-09-10.md`.

## Recovery Results

### 0A — Governance and handoff baseline — COMPLETE

- `AGENTS.md` established;
- `PROJECT.md` established;
- `docs/README.md` established;
- `docs/DECISIONS.md` established;
- this phase contract established;
- repository state, research state, validation state, and conversation context made explicitly distinct.

### 0B — Exact-head repository and local-divergence audit — COMPLETE

- former local Codex branch and 43 local-side divergent commits audited and triaged;
- old branch not merged wholesale because newer GitHub work superseded it;
- recovery evidence stored under `docs/recovery/`;
- active packages/apps/providers/migrations/deployments/tests/workflows inventoried.

### 0C — CI and reproducibility recovery — COMPLETE FOR NON-LIVE BASELINE

Deterministic recovery gates and current hosted CI pass. Expensive/live qualification remains separately gated by secrets, protected assets, production persistence, pricing, and explicit operator authorization.

### 0D — Documentation reconciliation — IN PROGRESS

Current handoff/governance docs supersede stale immediate-next-step text in older snapshots. Historical audits remain evidence only.

### 0E — Surface ownership audit — COMPLETE

- former `apps/studio/` generic image/video prototype evolved into standalone `faresmohamed260/renderlab`;
- generic RenderLab product work does not belong inside S.A.G.A.;
- Studio-only product/UI/workflow/schema surfaces were removed in PR #139;
- reusable stage-7 provider/runtime infrastructure remains where S.A.G.A. owns and consumes it;
- no destructive operation was performed against Studio-era remote infrastructure during repository cleanup.

### 0F — Clean-source requalification — IN PROGRESS

Repository/control-plane work:

1. protected-R2 diagnostic acquisition path — **COMPLETE through PR #141**;
2. clean-source GitHub qualification workflow + readiness gate — **COMPLETE through PR #145**;
3. external production persistence/provider/pricing readiness — **BLOCKED**;
4. protected source availability/hash/freshness — **BLOCKED under issue #142**;
5. actual exact-head nine-stage qualification — **NOT YET RUN**.

## Qualification Control Plane — COMPLETE

PR #145 added:

- `.github/workflows/production-qualification.yml` — manual-only, `main`-only, explicit live-cost confirmation;
- `scripts/check_production_qualification_readiness.py` — fail-fast production schema/source/provider/pricing readiness check;
- deterministic readiness tests;
- exact `GITHUB_SHA` release provenance;
- one explicit manifest-selected source with source-freshness enforcement;
- bounded global/stage deadlines and retries;
- private protected-source acquisition/hash verification and unconditional cleanup;
- no automatic deployment or promotion;
- no protected EPUB artifact publication.

Current nine-stage metering requires legitimate versioned provider-wide fallback `CostRate` entries for `ollama`, `mistral`, and `modal`. More-specific model/account rates may override those fallbacks.

## External Readiness Diagnostic — 2026-09-10

Two bounded same-repository GitHub Actions diagnostics were run after PR #145:

- `34514215596`;
- `34514460132`.

They intentionally made no paid reasoning/visual/audio provider calls, uploaded no artifacts, printed no secret values, and removed temporary protected bytes. The temporary push-trigger workflow was deleted from its diagnostic branch after evidence collection.

### Production persistence / provider configuration

Observed configuration presence:

- `SAGA_SUPABASE_DB_URL`: absent;
- `SAGA_SUPABASE_DB_HOST`: absent;
- complete S.A.G.A. component DB configuration: absent;
- legacy `SUPABASE_URL`: present;
- legacy `SUPABASE_SERVICE_ROLE_KEY`: present;
- `OLLAMA_API_KEY`: absent;
- `MISTRAL_API_KEY`: absent;
- `SAGA_PROVIDER_COST_RATES_JSON`: absent;
- R2 account/bucket/access-key/secret names: present.

The diagnostic returned `PRODUCTION_DB_RESULT status=not_configured`.

Therefore:

- source freshness cannot yet be proven in Actions;
- persisted `modal_xcore_litbank`, `modal_comfyui`, `modal_kokoro_tts`, Ollama, and Mistral readiness cannot yet be inspected through the real S.A.G.A. persistence path;
- the cost-accounting gate cannot pass;
- no live qualification should be attempted.

The only Supabase project visible through the connected Supabase app was inspected read-only and contains RenderLab/retired-Studio tables (`generation_*`, `media_*`, `renderlab_*`, `studio_*`). It is not S.A.G.A. production and was left untouched.

### Protected R2 access

Run `34514460132` exercised the bounded protected-storage helper against all supported jurisdictions:

- `default`: `access_failed`;
- `eu`: `access_failed`;
- `us`: `access_failed`;
- `fedramp`: `access_failed`.

Aggregate: `R2_PROBE_RESULT status=no_accessible_jurisdiction`.

Because failure occurs at bounded bucket listing for every endpoint, the present blocker is account/bucket/credential/token-scope access. There is no current evidence that any individual manifest object is missing. Object download/hash checks cannot become authoritative until bucket access works.

Historical pre-retirement source proves `apps/studio/api/_r2.js` consumed the exact same `R2_ACCOUNT_ID`, `R2_BUCKET_NAME`, `R2_ACCESS_KEY_ID`, and `R2_SECRET_ACCESS_KEY` namespace and defaulted its bucket to `saga-studio-media`. This proves the namespace was Studio-era infrastructure; GitHub does not expose values, so it does not prove current values are identical. Presence of those names is not evidence of a valid S.A.G.A. protected-assets bucket.

## Last Recorded Full Qualification

`docs/production_qualification.md` records a 2026-08-09 accepted real-book run through all nine stages with noncritical warnings and real provider/runtime evidence.

It is **not promotable** because the source worktree contained 574 pending paths. The current qualifier also rejects a source filename/SHA already present in production persistence, so that historical input must not be assumed fresh for the next qualification.

## Current Qualification Preconditions

Before protected-book processing or paid provider work, current S.A.G.A. qualification requires:

- exact committed `main` source and clean tracked checkout;
- explicit `confirm_live_cost=true`;
- actual S.A.G.A. production Supabase DB/API/service-role configuration and current schema;
- exactly one manifest-selected source unseen in production by filename/SHA;
- persisted Modal credentials for `modal_xcore_litbank`, `modal_comfyui`, and `modal_kokoro_tts`;
- usable Ollama authentication, normally persisted or explicit `OLLAMA_API_KEY`;
- Mistral persisted or available through `MISTRAL_API_KEY`;
- legitimate versioned provider-wide pricing fallbacks for `ollama`, `mistral`, and `modal`;
- a S.A.G.A.-owned private protected source reachable through List/Get and matching its committed SHA-256.

If a live provider or source prerequisite remains unavailable, record the exact external blocker and complete all unaffected validation rather than fabricating qualification.

## Validation Matrix

| Surface | Current evidence |
| --- | --- |
| Governance | Repository-first startup/handoff contract established |
| Python/dependency graph | Frozen install passes in hosted CI |
| Backend | Current core backend gate passes |
| Architecture boundaries | Active/reference dependency guard passes |
| Migrations | Upgrade/rollback/re-upgrade and isolated restore pass |
| Dashboard Pro | Required compatibility gate passes |
| Containers | Production Compose plus runtime/frontend builds pass |
| Qualification control plane | Merged and exact-head CI validated in PR #145 |
| Production persistence | **Blocked:** S.A.G.A. DB configuration absent from Actions |
| Provider pricing | **Blocked:** `SAGA_PROVIDER_COST_RATES_JSON` absent |
| Persisted provider readiness | **Unknown/blocked:** real S.A.G.A. DB unavailable |
| Protected R2 bucket access | **Blocked:** all supported jurisdictions return `access_failed` |
| Protected object presence/hash | **Not yet classifiable:** bucket access fails first |
| Source freshness | **Not yet classifiable:** production persistence unavailable |
| Clean-source qualification | **Not yet run** |

## Explicitly Out of Scope

- broad architecture redesign;
- replacing providers without evidence and explicit scope;
- implementing research proposals merely because they are promising;
- broad identity-resolver redesign before Phase 0 closes;
- deleting `backup/reference/`;
- production promotion merely because deterministic CI passes;
- destructive deletion of Studio/RenderLab remote infrastructure;
- generic RenderLab product development inside S.A.G.A.

## Exit Criteria

Phase 0 is complete only when:

1. repository-first governance remains consistent with current source;
2. active/historical/experimental surfaces are classified;
3. exact clean committed source passes required non-live gates;
4. authoritative documentation reflects current state;
5. retired Studio product surface remains removed without breaking retained S.A.G.A. runtime ownership;
6. clean-source qualification workflow/readiness path remains merged and validated;
7. real S.A.G.A. production persistence/provider/pricing configuration is qualification-ready;
8. one protected manifest asset is proven fresh, downloadable through S.A.G.A.-owned private storage, and SHA-valid;
9. exact-head clean-source S.A.G.A. qualification runs and its persisted report is accepted, or a precise external prerequisite is explicitly accepted as deferred;
10. `PROJECT.md` records completion evidence and names the next phase from actual results.

## Current Next Step

1. configure the real S.A.G.A. production Supabase/Postgres DB path and API/service-role aliases in GitHub Actions;
2. configure legitimate versioned `SAGA_PROVIDER_COST_RATES_JSON` fallbacks for `ollama`, `mistral`, and `modal`;
3. validate the persisted Modal/Ollama/Mistral provider state through that real production database;
4. reconfigure/rotate R2 credentials to a S.A.G.A.-owned private protected-assets bucket/prefix with List/Get access;
5. rerun `Protected Asset Verification` and require bucket access before object-level diagnosis;
6. select a manifest source that passes production freshness and private hash verification;
7. only then manually dispatch the paid/live clean-source qualification from exact `main` with explicit live-cost authorization;
8. record the resulting persisted evidence and choose the next implementation phase from that result.

## Next Phase Rule

Do not fully specify the next implementation phase yet.

Phase 0 qualification evidence determines whether the next priority is runtime/deployment repair, provider requalification, identity quality improvement, visual quality hardening, cost/usage telemetry, or another concrete blocker.