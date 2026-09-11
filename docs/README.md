# S.A.G.A. Documentation Index

S.A.G.A. is in an owner-authorized v2 rebuild. This index separates the **active v2 contract** from retained **v1 historical/reference material** and from **read-only external project references**.

## Read First

For substantial current work, read:

1. `../AGENTS.md`
2. `../PROJECT.md`
3. `DECISIONS.md`
4. the active v2 phase contract referenced by `PROJECT.md`
5. the relevant document under `v2/`

Do not use an older runtime/qualification document as current architecture merely because it contains more detail.

## Active v2 Governance

- `../AGENTS.md` — mandatory working rules, phase discipline, v2/v1 boundary, RenderLab read-only boundary
- `../PROJECT.md` — current product direction, merged baseline, blockers and immediate work
- `DECISIONS.md` — durable cross-cutting v2 decisions
- `phases/PHASE_V2_1_CLOSED_DEMO_APP.md` — active Phase 1 execution contract; deterministic repository slices 1A through 1E are complete, while the Phase 1E hosted operational gate remains pending

Phase baselines:

- Phase 0 web foundation — PR #149, merge `261b75ff2a60dfcada681af6b6c918c1ff5e3366`
- Phase 1 contract/governance — PR #152, merge `55beaccab011a4c5337db86dd88b52f6d48734c4`
- Phase 1B account/access foundation — PR #153, merge `5d5b59d17d2bd2f9a5769d2e5c4f9a2b43d1bad9`
- Phase 1C auth/access surfaces — PR #156, merge `319b785e43a169b4ffd7b57cd5be32ad3ef5da67`
- Phase 1D Narrative Desk — PR #160, merge `f558a282b4743a15d440eada1c6a7ccefe44215c`
- Phase 1E deterministic Admin operations — PR #162, merge `39dceaf1254ed7616ed1bd9eb640d9d622a73812`

## Active v2 Architecture / Product Contracts

- `v2/ARCHITECTURE.md` — top-level web-first ownership/deployment boundary
- `v2/FRONTEND_ARCHITECTURE.md` — Next.js route/component/server ownership, state and API direction
- `v2/UI_SYSTEM.md` — S.A.G.A.-specific UI/UX, component sourcing, responsive/accessibility and visual-review rules
- `v2/PHASE_1D_UI_CONCEPT.md` — approved Narrative Desk shell/navigation/composition direction
- `v2/ACCESS_AND_INVITATIONS.md` — closed-demo identity, account access, invitations, admin and email-delivery contract

## Active v2 Code / Operations

- `../apps/web/` — active Next.js web product
- `../apps/web/src/components/shell/` — Narrative Desk shell and responsive navigation
- `../apps/web/src/features/auth/` — Phase 1C auth actions/surfaces
- `../apps/web/src/features/admin/` — Phase 1E Admin server actions and Narrative Desk Admin workspace
- `../apps/web/src/server/account/` — fresh Auth identity and S.A.G.A. account/access resolution
- `../apps/web/src/server/admin/` — active-admin authorization, bounded Admin operations, HTTP error mapping and identifier validation
- `../apps/web/src/server/supabase/` — ordinary SSR/server Supabase boundary and isolated privileged client
- `../apps/web/src/server/storage/` — provider-neutral object-storage boundary + B2 implementation
- `../apps/web/supabase/migrations/` — **active v2 Supabase migration lineage**
- `../apps/web/supabase/tests/` — disposable-Postgres account/access/Admin database contracts
- `../config/v2-storage.json` — validated safe Backblaze B2 metadata
- `../.github/workflows/v2-web-ci.yml` — v2 web deterministic CI and database contracts
- `../.github/workflows/v2-visual-review.yml` — production Next.js/Chromium rendered Narrative Desk/Admin validation
- `../.github/workflows/v2-b2-bootstrap.yml` — manual-only Backblaze bootstrap/storage smoke workflow

Current Phase 1 validation evidence:

- `validation/PHASE_V2_1B_ACCOUNT_ACCESS_2026-09-11.md`
- `validation/PHASE_V2_1C_AUTH_ACCESS_2026-09-11.md`
- `validation/PHASE_V2_1D_NARRATIVE_DESK_2026-09-11.md`
- `validation/PHASE_V2_1E_ADMIN_OPERATIONS_2026-09-11.md`

## Current Boundary

The deterministic Phase 1E Admin repository slice is merged and validated. Phase 1 remains **active** because the hosted operational claims are still unproven.

Before Phase 1 closes, the repository-defined gate still requires a dedicated S.A.G.A.-owned Supabase project, hosted Auth redirect/template/email configuration, and at least one real bounded invitation acceptance flow.

Creating/configuring that hosted Supabase resource requires explicit organization selection and cost confirmation. Do not infer that authorization from a generic request to continue repository work.

Agent/job runtime surfaces are added only when a later active phase adopts them. Do not begin the agentic AI phase while Phase 1 hosted exit criteria remain unmet.

## RenderLab Reference Boundary

`faresmohamed260/renderlab` is a **separate product** and is read-only for S.A.G.A. work.

Its documentation may be inspected for proven setup/process/UI conventions, but do not modify RenderLab or copy its product code, page composition, visual identity, routes, table/schema names, data, credentials, storage or deployment state.

The S.A.G.A.-owned translations are authoritative here:

- `v2/FRONTEND_ARCHITECTURE.md`
- `v2/UI_SYSTEM.md`
- `v2/ACCESS_AND_INVITATIONS.md`

## Historical v1 Material

Everything below remains useful for requirements discovery, prior algorithms, evaluations, provider experiments and lessons learned, but it does **not** define active v2 architecture unless a v2 decision explicitly adopts part of it.

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

The clean pre-v2 boundary is commit `b689e17bf2b70ea6c2ade0c3795bb85bb048d57b`.

## Documentation Maintenance

When v2 changes:

- current state/phase/next step -> `PROJECT.md`
- durable cross-cutting architecture/product decision -> `DECISIONS.md`
- current phase scope/evidence -> active `phases/PHASE_V2_*.md`
- frontend/server ownership -> `v2/FRONTEND_ARCHITECTURE.md`
- UI/UX/component/design rules -> `v2/UI_SYSTEM.md`
- account/invitation/auth rules -> `v2/ACCESS_AND_INVITATIONS.md`
- broader system/deployment boundary -> `v2/ARCHITECTURE.md`
- dated validation evidence -> `validation/`

If v1 behavior or an external-project convention is reused, document the new v2 ownership instead of making the old source active again.
