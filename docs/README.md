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
- `../PROJECT.md` — current product direction, merged baseline, active phase, blockers and immediate work
- `DECISIONS.md` — durable cross-cutting v2 decisions
- `phases/PHASE_V2_1_CLOSED_DEMO_APP.md` — active Phase 1 execution contract; Phase 1A and 1B are complete, Phase 1C is next

Phase 0 is complete and retained for evidence:

- `phases/PHASE_V2_0_WEB_FOUNDATION.md`
- merged through PR #149 at `261b75ff2a60dfcada681af6b6c918c1ff5e3366`

Phase 1 contract/governance merged through PR #152 at `55beaccab011a4c5337db86dd88b52f6d48734c4`.

Phase 1B closed-demo access foundation merged through PR #153 at `5d5b59d17d2bd2f9a5769d2e5c4f9a2b43d1bad9`.

## Active v2 Architecture / Product Contracts

- `v2/ARCHITECTURE.md` — top-level web-first ownership/deployment boundary
- `v2/FRONTEND_ARCHITECTURE.md` — Next.js route/component/server ownership, state and API direction
- `v2/UI_SYSTEM.md` — S.A.G.A.-specific UI/UX, component sourcing, responsive/accessibility and visual-review rules
- `v2/ACCESS_AND_INVITATIONS.md` — closed-demo identity, account access, invitations, admin and email-delivery contract

## Active v2 Code / Operations

- `../apps/web/` — active Next.js web product
- `../apps/web/src/server/auth/` — fresh Auth identity, account/access resolution, admin authorization and invitation-claim services
- `../apps/web/src/server/supabase/` — ordinary SSR/server Supabase boundary plus isolated privileged server client
- `../apps/web/src/server/storage/` — provider-neutral object-storage boundary + B2 implementation
- `../apps/web/supabase/migrations/` — **active v2 Supabase migration lineage**; do not bootstrap v2 from the historical root migration tree
- `../apps/web/supabase/tests/` — disposable-Postgres database-contract tests for the active v2 schema
- `../config/v2-storage.json` — validated safe Backblaze B2 metadata
- `../.github/workflows/v2-web-ci.yml` — v2 web deterministic CI, including disposable-Postgres migration/contract validation
- `../.github/workflows/v2-b2-bootstrap.yml` — manual-only Backblaze bootstrap/storage smoke workflow

Current Phase 1B validation evidence:

- `validation/PHASE_V2_1B_ACCOUNT_ACCESS_2026-09-11.md`

Agent/job runtime surfaces are added only when a later active phase adopts them.

## RenderLab Reference Boundary

`faresmohamed260/renderlab` is a **separate product** and is read-only for S.A.G.A. work.

Its current repository documentation may be inspected for proven setup/process/UI conventions. Particularly useful reference categories include:

- repository-first continuity and progressive phase contracts;
- frontend/server/infrastructure ownership boundaries;
- maintained accessible UI primitives and semantic tokens;
- responsive/accessibility/reduced-motion discipline;
- closed-beta invitation/access concepts above Supabase Auth;
- remote-first CI and rendered UI validation.

Do not modify RenderLab while working on S.A.G.A. Do not copy its product code, page composition, visual identity, routes, table/schema names, data, credentials, R2/Supabase resources or deployment state. Any adopted convention must be restated and implemented as a S.A.G.A.-owned contract.

The S.A.G.A. translation of those principles is authoritative here:

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