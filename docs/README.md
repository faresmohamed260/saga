# S.A.G.A. Documentation Index

S.A.G.A. is in an owner-authorized fresh v2 rebuild. This index distinguishes the **active v2 contract** from retained **v1 historical/reference material**.

## Read First

For substantial current work, read:

1. `../AGENTS.md`
2. `../PROJECT.md`
3. `DECISIONS.md`
4. the active v2 phase contract referenced by `PROJECT.md`
5. the relevant document under `v2/`

Do not use an older runtime/qualification document as the current architecture merely because it contains more detail.

## Active v2 Governance

- `../AGENTS.md` — mandatory working rules and v2/v1 boundary
- `../PROJECT.md` — current product direction, stack, active phase, and next work
- `DECISIONS.md` — durable v2 decisions plus explicitly historical v1 decisions
- `phases/PHASE_V2_0_WEB_FOUNDATION.md` — active web-foundation/storage-bootstrap phase
- `v2/ARCHITECTURE.md` — current web-first architecture and ownership boundaries

## Active v2 Code/Operations

- `../apps/web/` — new Next.js web product and initial backend/API layer
- `../.github/workflows/v2-web-ci.yml` — v2 web deterministic CI
- `../.github/workflows/v2-b2-bootstrap.yml` — bounded Backblaze B2 bootstrap/storage validation

Additional v2 Supabase/schema and agent-runtime documents will be added only when their phase adopts those surfaces.

## Historical v1 Material

Everything below remains useful for requirements discovery, prior algorithms, evaluations, provider experiments, and lessons learned, but it does **not** define the active v2 architecture unless a v2 decision explicitly adopts part of it.

### v1 system/runtime documents

- `system_agent_roadmap.md`
- `agent_framework.md`
- `production_orchestration_runtime.md`
- `execution_runtime.md`
- `lineage_runtime.md`
- `observability_runtime.md`
- `analysis_foundation_runtime.md`
- `identity_runtime.md`
- `canon_extraction_runtime.md`
- `character_world_modeling_runtime.md`
- `retrieval_runtime.md`
- `generation_planning_runtime.md`
- `narrative_generation_runtime.md`
- `visual_generation_runtime.md`
- `audiobook_generation_runtime.md`
- `persistence_runtime.md`
- `storage_architecture.md`
- `runtime_secrets.md`
- `modal_runtime.md`
- `deployment_operations.md`
- `production_qualification.md`

### v1 recovery/qualification evidence

- `phases/PHASE_0_REPOSITORY_BASELINE_RECOVERY.md`
- `validation/REPRODUCIBILITY.md`
- `validation/PHASE_0_EXTERNAL_READINESS_2026-09-10.md`
- `recovery/`
- `operations/PROTECTED_TEST_ASSETS.md`
- `operations/protected_assets.manifest.json`
- `operations/MODEL_PROVIDER_MANIFEST.md`
- `operations/GITHUB_ACTIONS_SECRETS.md`

### historical code

- pre-v2 Python/runtime packages and integrations
- pre-v2 Dashboard Pro/API applications
- production deployment/qualification machinery
- `backup/reference/`

The repository history at commit `b689e17bf2b70ea6c2ade0c3795bb85bb048d57b` is the clean pre-v2 boundary after the final v1 recovery evidence PR.

## RenderLab Boundary

`faresmohamed260/renderlab` is a separate project. Its mature web engineering patterns and technology choices can inform S.A.G.A. v2, but RenderLab product state, routes, schemas, media ownership, R2 credentials, and deployment state are not S.A.G.A. state.

## Documentation Maintenance

When v2 changes:

- current state/phase/next step -> `PROJECT.md`
- durable cross-cutting architecture decision -> `DECISIONS.md`
- current phase scope/evidence -> active `phases/PHASE_V2_*.md`
- subsystem contract -> `v2/`
- dated validation evidence -> `validation/` when worth preserving

If v1 behavior is reused, document the new v2 ownership instead of making the old document active again.