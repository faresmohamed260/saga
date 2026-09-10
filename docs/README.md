# S.A.G.A. Documentation Index

S.A.G.A. is in an owner-authorized fresh v2 rebuild. This index distinguishes the **active v2 contract** from retained **v1 historical/reference material**.

## Read First

For substantial current work, read:

1. `../AGENTS.md`
2. `../PROJECT.md`
3. `DECISIONS.md`
4. the active v2 phase contract referenced by `PROJECT.md`
5. relevant documents under `v2/`

For frontend/UI work also read:

- `v2/UI_SYSTEM.md`
- `v2/DESIGN_WORKFLOW.md`

Do not use an older runtime/qualification document as current architecture merely because it contains more detail.

## Active v2 Governance

- `../AGENTS.md` — mandatory working rules, v2/v1 boundary, closed-demo/security rules, RenderLab reference boundary
- `../PROJECT.md` — current product direction, stack, active phase, verified baseline, next work
- `DECISIONS.md` — durable cross-cutting v2 decisions
- `phases/PHASE_V2_1_CLOSED_DEMO_WEB.md` — active Phase-1 web/account/invitation contract
- `v2/ARCHITECTURE.md` — web-first architecture and ownership boundaries
- `v2/UI_SYSTEM.md` — S.A.G.A.-owned UI system and component policy
- `v2/DESIGN_WORKFLOW.md` — integration/redesign workflow and rendered-review rules

Phase-0 contract is retained as completed evidence:

- `phases/PHASE_V2_0_WEB_FOUNDATION.md`

## Active v2 Code/Operations

- `../apps/web/` — active Next.js web product/backend surface
- `../.github/workflows/v2-web-ci.yml` — deterministic v2 web CI
- `../.github/workflows/v2-b2-bootstrap.yml` — manual Backblaze bootstrap/storage validation
- `../config/v2-storage.json` — validated non-secret B2 bucket metadata

Phase 1 will add the first v2-owned Supabase schema/migrations and account/invitation server boundaries under the active web product rather than reusing legacy v1 persistence ownership.

## Current Product Access Model

S.A.G.A. v2 is a **closed demo**:

- no public self-service signup;
- account access is invitation-only;
- admins invite email addresses;
- Supabase Auth owns identity/session state;
- S.A.G.A. owns admission/role/status separately;
- private application routes require a fresh verified identity plus active S.A.G.A. admission;
- service-role/Auth-admin capability is server-only;
- email invitation delivery requires hosted Auth/SMTP/template configuration before production readiness can be claimed.

## RenderLab Reference Boundary

`faresmohamed260/renderlab` is a separate project and is read-only for S.A.G.A. work.

Its repository may be consulted for proven **rules and setup patterns** such as:

- repository-first continuity;
- Server Component/client-state boundaries;
- Supabase identity vs product admission separation;
- invite/admin security lessons;
- maintained component sourcing;
- design tokens, responsive verification, and design-governance workflow.

Do not modify RenderLab. Do not copy/share its product routes, schema names, visual identity, R2 resources, credentials, deployment state, or implementation wholesale.

## Historical v1 Material

Everything below remains useful for requirements discovery, prior algorithms, evaluations, provider experiments, and lessons learned, but it does **not** define active v2 architecture unless a v2 decision explicitly adopts part of it.

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

The clean pre-v2 boundary is commit:

`b689e17bf2b70ea6c2ade0c3795bb85bb048d57b`

## Documentation Maintenance

When v2 changes:

- current state/phase/next step -> `PROJECT.md`
- durable architecture/product/security decision -> `DECISIONS.md`
- current phase scope/evidence -> active `phases/PHASE_V2_*.md`
- subsystem/UI contract -> `v2/`
- dated validation evidence -> `validation/` when worth preserving

If v1 or RenderLab behavior is useful, document the new S.A.G.A. v2 ownership instead of making the reference document authoritative.
