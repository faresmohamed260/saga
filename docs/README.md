# S.A.G.A. Documentation Index

This directory contains architecture, runtime, operations, evaluation, and historical evidence for S.A.G.A.

`PROJECT.md` is the short current-state handoff. This file maps detailed documentation and defines how to interpret it.

## Read First

For substantial work, read:

1. `../AGENTS.md`
2. `../PROJECT.md`
3. `DECISIONS.md`
4. the active phase contract referenced by `PROJECT.md`
5. the subsystem documents relevant to the task

## Authority and Time

Documentation is not automatically current merely because it exists.

Use documents according to their purpose:

- **Current handoff:** `PROJECT.md`, `DECISIONS.md`, and the active phase contract.
- **Current subsystem contract:** runtime/architecture documents whose behavior is verified against active code during the relevant work.
- **Qualification evidence:** dated validation records such as `production_qualification.md`; they prove only the source/configuration recorded there.
- **Audit snapshot:** documents such as `architecture_hardening_audit.md`; valuable evidence of a point in time, but their old “next step” text does not override the current project handoff.
- **Historical/migration reference:** documents explicitly labeled historical/reference; never treat them as active implementation requirements without verification.

If a detailed document conflicts with current code or the current handoff, investigate and update the authoritative project record rather than silently choosing a convenient version.

## Project Governance

- `../AGENTS.md` — mandatory AI/session working rules and validation discipline
- `../PROJECT.md` — current architecture summary, verified baseline, active phase, blockers, and next step
- `DECISIONS.md` — durable decisions and unresolved decisions requiring explicit resolution
- `phases/PHASE_0_REPOSITORY_BASELINE_RECOVERY.md` — current recovery/requalification phase contract

## System Architecture and Orchestration

- `system_agent_roadmap.md` — system intent, agent groups, runtime constraints, and accumulated progress record; current-status/next-step text must be reconciled against the current handoff
- `agent_framework.md` — agent runtime/framework design
- `production_orchestration_runtime.md` — top-level production orchestration
- `execution_runtime.md` — execution/queue/runtime behavior
- `lineage_runtime.md` — lineage and provenance
- `observability_runtime.md` — observability contracts
- `architecture_hardening_audit.md` — earlier architecture-hardening audit snapshot; not the current project handoff

## Analysis / Canon

- `analysis_foundation_runtime.md` — ingestion/scene-analysis foundation
- `identity_runtime.md` — active identity clustering/review ownership and validation reference
- `canon_extraction_runtime.md` — canon extraction
- `character_world_modeling_runtime.md` — character/world state modeling
- `retrieval_runtime.md` — retrieval behavior and contracts

## Generation

- `generation_planning_runtime.md` — story planning / blueprint generation
- `narrative_generation_runtime.md` — narrative generation
- `visual_generation_runtime.md` — S.A.G.A. stage-7 visual generation and QA; generic image/video product UI belongs in the separate RenderLab repository
- `audiobook_generation_runtime.md` — audiobook generation and QA
- `qwen-image-edit-2511-integration.md` — retained S.A.G.A. Qwen provider/runtime contract
- `qwen-image-edit-2511-deployment-plan.md` — Qwen worker deployment gates
- `qwen-image-edit-2511-status.md` — dated Qwen worker/provider evidence

## Persistence / Providers / Operations

- `persistence_runtime.md` — persistence runtime
- `storage_architecture.md` — storage/provider boundaries
- `runtime_secrets.md` — runtime secret ownership
- `operations/GITHUB_ACTIONS_SECRETS.md` — GitHub Actions secret names, owning services, workflow consumers, and migration status without values
- `operations/PROTECTED_TEST_ASSETS.md` — protected/private book asset metadata, hashes, and secure CI acquisition rules
- `operations/protected_assets.manifest.json` — machine-readable protected-asset IDs, object keys, filenames, and hashes consumed by manual verification
- `operations/MODEL_PROVIDER_MANIFEST.md` — active/evaluation/historical model and provider identities without model weights or credentials
- `modal_runtime.md` — Modal/general compute provider runtime
- `modal-worker-fleet-design.md` — S.A.G.A.-owned Modal worker-fleet contract and public registry ownership
- `../config/modal-worker-ecosystems.json` — machine-readable S.A.G.A. worker ecosystem definitions
- `../config/modal-worker-registry.json` — non-secret active worker routing metadata rehomed from the retired Studio prototype
- `deployment_operations.md` — production build, rollout, rollback, backup, and recovery

## Product / UI Surfaces

- `dashboard_pro.md` — S.A.G.A. operator dashboard

The former S.A.G.A. `apps/studio/` prototype is retired. Its standalone successor is `faresmohamed260/renderlab`. Studio product/UI plans, polish checklists, visual-review workflows, and product persistence schema are not active S.A.G.A. documentation or architecture.

## Qualification and Evidence

- `production_qualification.md` — last recorded real-book nine-stage qualification; accepted as evidence but explicitly non-promotable because the recorded source worktree was dirty
- `validation/REPRODUCIBILITY.md` — validation tiers, required secrets/assets/models, runner expectations, and live-gate boundaries
- `.github/workflows/protected-asset-verification.yml` — manual R2-backed protected asset availability/hash verification; never uploads protected bytes
- additional validation scripts/tests under `scripts/` and `tests/` are authoritative only for the behavior they actually exercise

## Migration / Historical Material

- `MIGRATION_REFERENCE.md` — migration/reference material; verify its intended use before applying it to active architecture
- `recovery/LOCAL_TO_GITHUB_HANDOFF_INVENTORY.md` — 2026-09-10 local-to-GitHub recovery inventory and reconciliation decisions; references to Studio describe historical recovery state
- `recovery/LOCAL_COMMIT_TRIAGE.md` — commit-by-commit classification of the 43 local-side commits from `codex/transaction-pool-rc36`
- `recovery/HANDOFF_REPORT_2026-09-10.md` — final durable report for the 2026-09-10 local-to-GitHub recovery pass
- `../backup/reference/` — isolated historical implementation, not active dependency

## Documentation Maintenance Rules

When durable project state changes:

- update `PROJECT.md` for baseline/phase/next-step changes;
- update `DECISIONS.md` for durable decisions;
- update the active phase contract for scope/evidence/exit state;
- update the owning subsystem document when its contract changes;
- update `production_qualification.md` only with qualification evidence that actually ran.

Do not create a new status file when an existing authoritative file already owns that information.

Do not mark work complete from a plan, attempted run, or unrelated green CI check.
