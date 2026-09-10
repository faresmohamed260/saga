# Phase 0 — Repository Baseline Recovery & Requalification

**Status:** ACTIVE — REPOSITORY/CONTROL-PLANE RECOVERY COMPLETE; EXTERNAL PRODUCTION CONFIGURATION + FRESH PROTECTED SOURCE BLOCK QUALIFICATION

## Goal

Establish a trustworthy, clean, reproducible current S.A.G.A. baseline before broad feature work resumes.

The phase succeeds when a new session can identify exactly what current committed S.A.G.A. builds, tests, runs, and qualifies; stale status documents no longer control work; unrelated repository surfaces are explicitly classified; and remaining defects can be planned from evidence rather than conversation history.

## Verified Repository Baseline — 2026-09-10

- Repository: `faresmohamed260/saga`
- Default branch: `main`
- Verified clean baseline through PR #146: `b689e17bf2b70ea6c2ade0c3795bb85bb048d57b`
- Verified tree: `ffcbbb5cf543cf0800da5d59f7f686f0e50538b8`
- Recovery/cleanup/control-plane/evidence PRs #134, #135, #137, #138, #139, #140, #141, #145, and #146 are merged evidence.

PR #145 final head `8b00e732bfeda213b77dc77a44ebc60fabc46a8e` passed Backend Architecture CI and Required Check Compatibility before adding the clean-source qualification control plane. PR #146 final head `0297b5abd9785b35cbe7e3c842ee40489c97f792` passed Required Check Compatibility run `34515749221` and Backend Architecture CI run `34515749174` before preserving the bounded external-readiness evidence.

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
2. clean-source GitHub qualification workflow + fail-fast readiness script — **COMPLETE through PR #145**;
3. bounded external-readiness evidence — **COMPLETE through PR #146**;
4. standalone no-cost production readiness workflow — **IMPLEMENTED by issue #147 in `.github/workflows/production-qualification-readiness.yml`; pending exact-head CI/merge with this change**;
5. external production persistence/provider/pricing readiness — **BLOCKED**;
6. protected source availability/hash/freshness — **BLOCKED under issue #142**;
7. actual exact-head nine-stage qualification — **NOT YET RUN**.

## Qualification Control Plane

The clean-source production path contains two deliberately separate operator gates.

### Read-only production readiness

`.github/workflows/production-qualification-readiness.yml` is the permanent no-cost preflight entrypoint. It is:

- `workflow_dispatch` only;
- restricted to `main` and exact checked-out `GITHUB_SHA`;
- explicit about one manifest `asset_id`;
- backed by `scripts.check_production_qualification_readiness`;
- read-only with respect to production persistence/configuration;
- free of R2 credentials, protected-book download, `scripts.run_production_qualification`, and paid reasoning/visual/audio provider execution;
- red when the readiness script returns not-ready, so missing configuration cannot look green.

Deterministic contract tests in `tests/test_production_qualification_readiness_workflow.py` prevent this workflow from silently acquiring protected bytes or becoming a paid/live execution path.

### Paid/live clean-source qualification

PR #145 added `.github/workflows/production-qualification.yml`, which remains:

- manual-only and `main`-only;
- explicitly gated by `confirm_live_cost=true`;
- bound to exact `GITHUB_SHA` release provenance;
- source-freshness checked before protected download/provider work;
- bounded by global/stage deadlines and retries;
- private-source/hash verified with unconditional cleanup;
- unable to publish protected EPUB artifacts;
- unable to deploy/promote automatically merely because qualification passes.

Current nine-stage metering requires legitimate versioned provider-wide fallback `CostRate` entries for `ollama`, `mistral`, and `modal`. More-specific model/account rates may override those fallbacks.

## External Readiness Diagnostic — 2026-09-10

Two bounded same-repository GitHub Actions diagnostics were run after PR #145:

- `34514215596`;
- `34514460132`.

They intentionally made no paid reasoning/visual/audio provider calls, uploaded no artifacts, printed no secret values, and removed temporary protected bytes. The temporary push-trigger workflow was deleted after evidence collection and is not part of the production architecture.

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
- actual S.A.G.A. production Supabase DB/API/service-role configuration and current schema;
- exactly one manifest-selected source unseen in production by filename/SHA;
- persisted Modal credentials for `modal_xcore_litbank`, `modal_comfyui`, and `modal_kokoro_tts`;
- usable Ollama authentication, normally persisted or explicit `OLLAMA_API_KEY`;
- Mistral persisted or available through `MISTRAL_API_KEY`;
- legitimate versioned provider-wide pricing fallbacks for `ollama`, `mistral`, and `modal`;
- a S.A.G.A.-owned private protected source reachable through List/Get and matching its committed SHA-256;
- separate explicit `confirm_live_cost=true` only when actually dispatching the paid/live nine-stage workflow.

The standalone readiness workflow should be used after DB/provider/pricing configuration changes and before any paid qualification attempt. Protected R2 availability remains separately owned by issue #142 and `Protected Asset Verification`.

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
| Paid qualification control plane | Merged and exact-head CI validated in PR #145 |
| External readiness evidence | Recorded and CI-validated in PR #146 |
| Read-only production readiness control plane | Implemented under issue #147; deterministic boundary tests included |
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
6. paid qualification and read-only readiness control planes are merged and validated;
7. real S.A.G.A. production persistence/provider/pricing configuration passes the standalone readiness workflow;
8. one protected manifest asset is proven fresh, downloadable through S.A.G.A.-owned private storage, and SHA-valid;
9. exact-head clean-source S.A.G.A. qualification runs and its persisted report is accepted, or a precise external prerequisite is explicitly accepted as deferred;
10. `PROJECT.md` records completion evidence and names the next phase from actual results.

## Current Next Step

1. merge/validate issue #147 so the no-cost readiness workflow is available on `main`;
2. configure the real S.A.G.A. production Supabase/Postgres DB path and API/service-role aliases in GitHub Actions;
3. configure legitimate versioned `SAGA_PROVIDER_COST_RATES_JSON` fallbacks for `ollama`, `mistral`, and `modal`;
4. dispatch **Production Qualification Readiness** for one manifest asset and use its bounded result to validate persisted Modal/Ollama/Mistral state and source freshness without provider calls;
5. reconfigure/rotate R2 credentials to a S.A.G.A.-owned private protected-assets bucket/prefix with List/Get access;
6. rerun `Protected Asset Verification` and require bucket access before object-level diagnosis;
7. select a manifest source that passes production freshness and private hash verification;
8. only then manually dispatch the paid/live clean-source qualification from exact `main` with explicit live-cost authorization;
9. record the resulting persisted evidence and choose the next implementation phase from that result.

## Next Phase Rule

Do not fully specify the next implementation phase yet.

Phase 0 qualification evidence determines whether the next priority is runtime/deployment repair, provider requalification, identity quality improvement, visual quality hardening, cost/usage telemetry, or another concrete blocker.