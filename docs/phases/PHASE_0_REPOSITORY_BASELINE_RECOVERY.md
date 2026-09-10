# Phase 0 — Repository Baseline Recovery & Requalification

**Status:** ACTIVE / GOVERNANCE BASELINE BEING ESTABLISHED

## Goal

Establish a trustworthy, clean, reproducible current S.A.G.A. baseline before broad feature work resumes.

The phase succeeds when a new session can identify exactly what current committed S.A.G.A. builds, tests, runs, and qualifies; stale status documents no longer control work; unrelated repository surfaces are explicitly classified; and remaining defects can be planned from evidence rather than conversation history.

## User / Project Value

S.A.G.A. already contains substantial architecture and prior real-book validation. The immediate problem is not lack of code; it is loss of a single reliable current-state handoff across later repository activity, stale “next step” statements, non-promotable qualification provenance, and mixed S.A.G.A./Studio surfaces.

Recovering the baseline prevents future AI sessions from repeatedly rewriting working architecture or chasing outdated plans.

## Verified Starting State — 2026-09-10

### Repository

- Repository: `faresmohamed260/saga`
- Default branch: `main`
- Audited starting HEAD: `1d1fa6e9bb86feede9c9f5b89eec828eb15a2050`
- Starting tree: `3b582a129e9682bd27cf701438e5182bd6f211be`
- Latest audited `main` commit is the merge of PR #131 for Studio mobile control cleanup.
- Open PR #132 contains additional Studio Gallery/Qwen UI work and must not be merged/closed as a side effect of this phase.

### Local-to-GitHub recovery audit

- Recovery branch: `recovery/local-to-github-handoff`
- Governance source reused: PR #133 commit `5756e1c66df43594b2c6673a88fb6a330dcc13a1`
- Audited local branch: `codex/transaction-pool-rc36`
- Audited local HEAD: `0294bb260d426e81048dd982dae85e64db3f9318`
- Divergence from remote `main`: 1000 remote-side commits and 43 local-side commits.
- Local working tree: dirty, with modified ComfyUI/runtime files and untracked Studio/generation-core files.
- Inventory: `docs/recovery/LOCAL_TO_GITHUB_HANDOFF_INVENTORY.md`
- Reproducibility manifest: `docs/validation/REPRODUCIBILITY.md`
- Secrets manifest: `docs/operations/GITHUB_ACTIONS_SECRETS.md`
- Protected asset manifest: `docs/operations/PROTECTED_TEST_ASSETS.md`
- Model/provider manifest: `docs/operations/MODEL_PROVIDER_MANIFEST.md`

### Active architecture claims

The root README describes:

- modular runtime packages;
- provider integrations;
- FastAPI dashboard API;
- React operator dashboard;
- production deployment topology;
- nine-stage end-to-end orchestration;
- historical implementation isolation under `backup/reference/`.

These claims are plausible and backed by substantial code/docs, but Phase 0 must establish which are currently verified at exact committed source.

### CI / deployment evidence

For starting `main` HEAD, the most recent observed GitHub Actions evidence includes successful Studio CI and Required Check Compatibility. Vercel status is successful for the Studio deployment surface.

Those checks do not by themselves prove S.A.G.A. backend/pipeline qualification.

### Last recorded full qualification

`docs/production_qualification.md` records a 2026-08-09 accepted run of `Once Upon a Broken Heart.epub` through all nine stages with noncritical warnings.

It also explicitly records:

- backend `243 passed, 3 skipped`;
- dashboard `13 passed` and Vite build success;
- security-sensitive suite `60 passed`;
- real pipeline/provider evidence;
- **non-promotable source provenance because 574 worktree paths were pending**.

Treat this as strong behavioral evidence, not current clean-release proof.

### Documentation drift

- `docs/system_agent_roadmap.md` contains a now-dated immediate step to merge a stabilization PR.
- `docs/architecture_hardening_audit.md` is an earlier snapshot whose “next step” predates the later agent rebuild described by the roadmap.
- `apps/studio/` exists and later Studio-specific work dominates recent `main` history, while root architecture documentation does not classify it as a primary S.A.G.A. surface.

## In Scope

### 0A — Governance and handoff baseline

- add `AGENTS.md`;
- add `PROJECT.md`;
- add `docs/README.md`;
- add `docs/DECISIONS.md`;
- establish this active phase contract;
- make repository state, research state, validation state, and conversation context explicitly distinct.

### 0B — Exact-head repository audit

Audit current committed source for:

- package/runtime inventory;
- app surfaces;
- provider integrations;
- migrations/schema ownership;
- production compose/process definitions;
- Python/dashboard dependency locks;
- test suites;
- GitHub Actions gates;
- release/qualification scripts;
- current open PR/issues that materially affect S.A.G.A. recovery.

Classify each important surface as active, experimental, historical/reference, or unresolved.

### 0C — CI and reproducibility recovery

From a clean committed branch/head:

- verify `uv sync --frozen --extra dev` expectations;
- run/inspect the complete repository backend test gate rather than Studio-only checks;
- verify `apps/dashboard_pro` install/test/build;
- verify architecture-boundary and migration/release gates;
- identify failures caused by stale dependencies, environment assumptions, missing secrets, provider drift, or actual implementation defects;
- fix only blockers needed to establish the clean baseline.

### 0D — Documentation reconciliation

Reconcile current state across:

- root `README.md`;
- `PROJECT.md`;
- `docs/system_agent_roadmap.md`;
- `docs/production_qualification.md`;
- relevant architecture/runtime documents.

Do not erase useful historical evidence. Re-label dated audits/results where necessary and remove stale instructions from current handoff paths.

### 0E — Surface ownership audit

Audit `apps/studio/` plus Studio-specific workflows, deployment, schema/storage coupling, open issues, and PR #132.

Produce an explicit decision proposal. Do not delete, migrate, or merge the surface during this subphase unless separately authorized.

### 0F — Clean-source requalification

After repository gates are green on committed source and required provider environments are available:

- perform the bounded qualification path required by current production contracts;
- bind evidence to exact commit SHA/configuration/release identity;
- record warnings and manual-review limitations honestly;
- do not promote/deploy merely because qualification passes.

If full live providers are unavailable, record the exact blocker and complete all offline/CI portions rather than fabricating qualification.

## Explicitly Out of Scope

- broad architecture redesign;
- replacing LangGraph, Supabase, Modal, XCore, ComfyUI, TTS, or other providers without evidence and explicit scope;
- implementing research proposals merely because they appear promising;
- broad identity-resolver redesign before baseline recovery;
- deleting historical/reference code;
- merging/closing unrelated Studio PRs/issues;
- production deployment or promotion;
- unrelated new product features;
- UI redesign.

## Validation Matrix

Phase 0 should accumulate evidence for these gates:

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
| Studio surface | Ownership/status is explicitly decided or remains a clearly documented blocker |

## Handoff Evidence Added During Recovery

- Local heavy generated outputs were classified as non-migratable by default, including multi-GB SQLite files, dumps, artifact zips, vector indices, audiobook outputs, caches, and build outputs.
- Local secret-bearing files were inventoried only by path and field/variable name; values were not copied into repository files.
- Commercial EPUB validation assets were recorded by filename, purpose, and SHA-256 while preserving the rule that bytes must not be committed to the public repository.
- Current Actions were classified into deterministic CI, bounded integration, and expensive/live-provider tiers.
- Ollama is documented as local/remote endpoint dependent, not as an assumed GitHub-hosted runner dependency and not as requiring an invented `OLLAMA_API_KEY`.
- Deterministic local validation on the clean recovery worktree passed: frozen `uv` sync, one Alembic head `202608090400`, source secret scan with 850 files and 0 findings, architecture-boundary tests 4/4, full backend tests 338 passed / 3 skipped, Dashboard Pro tests 13/13, Dashboard Pro production build, production dependency audit with 0 high vulnerabilities, and production Compose config validation.
- Remote GitHub validation on PR #134 head `97b8200ad48dc835b8c7952de10dec998148da61` passed: Backend Architecture CI `test`, `migrations`, and `containers`; Required Check Compatibility `dashboard-pro`; Vercel status context.

## Exit Criteria

Phase 0 is complete only when:

1. repository-first governance is merged;
2. current active/historical/experimental/unresolved surfaces are classified;
3. exact clean committed source passes the required non-live core gates, or every remaining failure is a specific accepted blocker;
4. current documentation no longer points future sessions to stale immediate-next-step instructions;
5. the S.A.G.A. core has a clean-source qualification result, or a precise external prerequisite blocking that result is recorded;
6. `apps/studio/` status is explicitly decided or intentionally deferred with its coupling documented;
7. `PROJECT.md` records the verified completion evidence and names the next phase from actual results.

Current status: this handoff branch improves repository continuity, records missing local knowledge, and verifies Tier 1 deterministic gates locally and in GitHub Actions for PR #134. Phase 0 is not complete until the branch is reviewed/merged, local-side commits are ported or rejected, Studio ownership is decided/deferred with coupling evidence, and live/protected-asset qualification either runs or has explicit accepted prerequisites recorded.

## Next Phase Rule

Do not fully specify the next implementation phase yet.

Phase 0 evidence determines whether the next priority is:

- runtime/deployment repair;
- provider requalification;
- identity quality improvement;
- visual quality hardening;
- cost/usage telemetry;
- repository surface separation;
- or another concrete blocker discovered by the audit.

Expand only the selected next phase after Phase 0 establishes the evidence needed to choose it.
