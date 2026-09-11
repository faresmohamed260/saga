# S.A.G.A. Documentation Index

S.A.G.A. is in an owner-authorized v2 rebuild. This index separates the **active v2 source of truth** from retained **v1 historical/reference material** and from read-only external project references.

## Read First

For substantial current work, read in this order:

1. `../AGENTS.md`
2. `../PROJECT.md`
3. `DECISIONS.md`
4. the current v2 phase contract referenced by `PROJECT.md`
5. the relevant document under `v2/`

GitHub is authoritative. Do not reconstruct project state from chat history when the repository can establish it.

## Current Phase State

**S.A.G.A. v2 Phase 1 — Closed-Demo Main Site, Accounts & Invitations: COMPLETE.**

Authoritative completion records:

- `phases/PHASE_V2_1_CLOSED_DEMO_APP.md`
- `validation/PHASE_V2_1_HOSTED_AUTH_LIVE_PROOF_2026-09-11.md`

**S.A.G.A. v2 Phase 2 — Story Intake & Character Identity Foundation: ACTIVE.**

Authoritative Phase-2 contract:

- `phases/PHASE_V2_2_STORY_INTAKE_CHARACTER_IDENTITY.md`

**Phase 2A — Product/Data Foundation: COMPLETE.**

Authoritative Phase-2A deterministic evidence:

- `validation/PHASE_V2_2A_PRODUCT_DATA_FOUNDATION_2026-09-12.md`

Phase 2 restores the first real storytelling intelligence loop behind the proven private application boundary:

```text
member-owned project
  -> .txt/.epub source
  -> B2 object + Supabase metadata
  -> durable Postgres analysis job
  -> separate analysis worker
  -> deterministic normalized source
  -> precision-first character identity resolution
  -> character / alias / mention evidence in the private app
```

The phase explicitly avoids recreating the old v1 monolithic runtime or jumping directly to a general agent/LLM framework.

The next active slice is **Phase 2B — Source storage + deterministic ingestion**.

## Active v2 Governance

- `../AGENTS.md` — mandatory working rules, source-of-truth order, phase discipline, v2/v1 boundary, RenderLab boundary
- `../PROJECT.md` — current hosted reality, active Phase-2 direction, completed Phase-2A baseline, deferred items and immediate next work
- `DECISIONS.md` — durable cross-cutting v2 decisions
- `phases/PHASE_V2_2_STORY_INTAKE_CHARACTER_IDENTITY.md` — active Phase-2 product/data/job/provider/testing/hosted-validation contract
- `phases/PHASE_V2_1_CLOSED_DEMO_APP.md` — completed Phase-1 contract and exit evidence
- `operations/VERCEL_DEPLOYMENT_POLICY.md` — manual-only Vercel deployment rule

## Phase Baselines

- Phase 0 web foundation — PR #149, merge `261b75ff2a60dfcada681af6b6c918c1ff5e3366`
- Phase 1 contract/governance — PR #152, merge `55beaccab011a4c5337db86dd88b52f6d48734c4`
- Phase 1B account/access — PR #153, merge `5d5b59d17d2bd2f9a5769d2e5c4f9a2b43d1bad9`
- Phase 1C auth/access — PR #156, merge `319b785e43a169b4ffd7b57cd5be32ad3ef5da67`
- Phase 1D Narrative Desk — PR #160, merge `f558a282b4743a15d440eada1c6a7ccefe44215c`
- Phase 1E deterministic Admin — PR #162, merge `39dceaf1254ed7616ed1bd9eb640d9d622a73812`
- Phase 1 deterministic handoff — PR #163, merge `c274f1d26914edf62e30cfd2ef23222df6a8503f`
- manual-only Vercel deployment policy — PR #173, merge `4c592a5590fdd46ac075a20def4b9d03c169f880`
- Phase 1 hosted closure — PR #174, merge `3802222714c300b9777b65b34f94668be50f9582`
- Phase 2 contract — PR #175, merge `bf955d3d02f327a655d4406615b2e1fa6e35e574`
- Phase 2A product/data foundation — PR #177, merge `7a053697e874d8fb6e0b03571b7cf0f2e885dd61`

## Active v2 Architecture / Product Contracts

- `v2/ARCHITECTURE.md` — top-level web-first ownership/deployment boundary
- `v2/FRONTEND_ARCHITECTURE.md` — Next.js route/component/server ownership, state and API direction
- `v2/UI_SYSTEM.md` — S.A.G.A.-specific UI/UX, component sourcing, responsive/accessibility and visual-review rules
- `v2/PHASE_1D_UI_CONCEPT.md` — approved Narrative Desk shell/navigation/composition direction
- `v2/ACCESS_AND_INVITATIONS.md` — closed-demo identity, account access, invitations, admin and email-delivery contract
- `phases/PHASE_V2_2_STORY_INTAKE_CHARACTER_IDENTITY.md` — Phase-2 project/source ownership, analysis runtime, storage, identity-provider, deterministic testing and qualification boundary

## Active v2 Code / Operations

- `../apps/web/` — active Next.js web product
- `../apps/web/src/components/shell/` — Narrative Desk shell and responsive navigation
- `../apps/web/src/features/auth/` — invitation/password/sign-in/sign-out product surfaces
- `../apps/web/src/features/admin/` — Admin server actions and workspace
- `../apps/web/src/features/projects/` — project actions for the Phase-2 private story boundary
- `../apps/web/src/server/account/` — fresh Auth identity and S.A.G.A. account/access resolution
- `../apps/web/src/server/admin/` — active-admin authorization and bounded Admin operations
- `../apps/web/src/server/story/` — member-scoped project/source/job/result domain reads behind authenticated RLS
- `../apps/web/src/server/supabase/` — ordinary SSR/server and isolated privileged Supabase boundaries
- `../apps/web/src/server/storage/` — provider-neutral object-storage boundary + B2 implementation
- `../apps/web/supabase/migrations/` — active v2 Supabase migration lineage
- `../apps/web/supabase/tests/` — disposable-Postgres database contracts
- `../config/v2-storage.json` — safe Backblaze B2 metadata
- `../.github/workflows/v2-web-ci.yml` — deterministic web/database CI
- `../.github/workflows/v2-visual-review.yml` — production-build Chromium rendered validation
- `../.github/workflows/v2-b2-bootstrap.yml` — manual-only Backblaze bootstrap/storage smoke workflow

Phase-2 analysis worker code does not yet exist at Phase-2A completion. Its implementation must follow the runtime boundary in the active phase contract rather than reviving a v1 package as the active runtime.

## Phase 2 Validation Evidence

- `validation/PHASE_V2_2A_PRODUCT_DATA_FOUNDATION_2026-09-12.md` — owner/RLS data foundation, durable lease-based jobs, immutable run/result boundary, Projects/Library/product-workspace rendering and exact-head CI proof

Phase-2A exact-head proof runs:

- Web CI `34654618229` — success
- Required Check Compatibility `34654618239` — success
- Backend Architecture CI `34654618234` — success
- Visual Review `34654618236` — success

Phase-2A rendered artifact:

- ID `10284398956`
- name `saga-v2-phase-2a-visual-review`
- exact head `51147ddf5855a43c3b50770502f2cf9f8fdf1f54`

## Phase 1 Validation Evidence

- `validation/PHASE_V2_1B_ACCOUNT_ACCESS_2026-09-11.md`
- `validation/PHASE_V2_1C_AUTH_ACCESS_2026-09-11.md`
- `validation/PHASE_V2_1D_NARRATIVE_DESK_2026-09-11.md`
- `validation/PHASE_V2_1E_ADMIN_OPERATIONS_2026-09-11.md`
- `validation/PHASE_V2_1E_HOSTED_SUPABASE_2026-09-11.md`
- `validation/PHASE_V2_1E_HOSTED_VERCEL_2026-09-11.md`
- `validation/PHASE_V2_1_HOSTED_AUTH_LIVE_PROOF_2026-09-11.md` — final hosted Auth/email/invitation/access proof; supersedes earlier pending conclusions in the foundation snapshots

Key hosted proof runs:

- access/suspension: `34647243289` — success
- full invitation lifecycle: `34647592382` — success

## Current Hosted Boundary

### Supabase

Dedicated project:

- ref `scmeqnpmhomzcwecjdtu`
- region `eu-central-1`
- public signup disabled
- custom Resend SMTP active
- Auth Site URL currently `https://saga-pi-two.vercel.app`
- future custom-domain redirect allowance includes `https://saga.faresuniform.uk/**`

The existing `AI Studio` Supabase project was not reused or modified.

Phase-2A repository migrations are merged and disposable-Postgres qualified. This index does **not** claim those new migrations have been applied to hosted Supabase until a later hosted validation explicitly proves that state.

### Vercel

Dedicated `saga` project uses `apps/web`.

The historical `studio` project was disconnected from S.A.G.A. Git pushes. Git-triggered Preview and Production deployments are disabled. Any Vercel deployment requires fresh explicit owner approval after stating the reason, deployment type, and exact commit/SHA.

No Vercel deployment was performed for Phase 2A.

### Backblaze B2

The dedicated private S.A.G.A. bucket is validated. Phase 2B requires a real source-object lifecycle, but deterministic repository implementation can proceed against the existing provider-neutral storage boundary without a hosted runtime credential.

A bucket-scoped runtime application key is required only when real hosted source object I/O becomes necessary. Bootstrap/master credentials remain operator-only.

## Open / Deferred Work

- custom domain `saga.faresuniform.uk` — tracked by issue #165; not part of Phase 2 unless explicitly resumed;
- scoped B2 runtime credentials — external gate for real hosted Phase-2 source object I/O;
- worker host/provider — deliberately deferred until the separate worker contract is implemented/proven far enough to require a host/cost choice;
- PR #172 (`Expose hosted release identity in health checks`) — closed without merge after Phase 1 completed without it; reintroduce only as a fresh current-main change if a future hosted gate needs release fingerprinting.

## Phase-2 Execution Boundary

Implement the active phase contract in this order:

1. **2A Product/data foundation — COMPLETE** — project/source/job/run/character schema, owner RLS, atomic job contract, database tests, initial Projects/Library/product-workspace surfaces;
2. **2B Source storage + ingestion — NEXT** — bounded source-object lifecycle, upload completion/fingerprint verification, `.txt`/`.epub` deterministic normalizers, golden fixtures and normalized structure persistence;
3. **2C Character identity engine** — normalized evidence-provider interface, conservative canonical admission, attachment/quarantine, aliases/mentions, adversarial fixtures and user-visible result surface;
4. **2D Qualification** — retries/idempotency, literary benchmark baseline, rendered validation, then hosted B2+worker+app proof after the required explicit approvals.

Do not skip the schema/job/runtime boundary by embedding full-book parsing or NLP in Next.js requests.

Do not use generative LLMs as a shortcut around the deterministic Phase-2 identity contract.

## RenderLab Reference Boundary

`faresmohamed260/renderlab` is a separate product and read-only reference for process/architecture/UI conventions only.

Do not modify RenderLab or copy its product code, page composition, visual identity, routes, schema/table names, data, credentials, storage or deployment state.

S.A.G.A.-owned translations are authoritative:

- `v2/FRONTEND_ARCHITECTURE.md`
- `v2/UI_SYSTEM.md`
- `v2/ACCESS_AND_INVITATIONS.md`
- `phases/PHASE_V2_2_STORY_INTAKE_CHARACTER_IDENTITY.md`

## Historical v1 Material

The following remain useful for requirements discovery, algorithms, evaluation history, provider experiments, and lessons learned, but do **not** define active v2 architecture unless explicitly re-adopted:

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

The clean pre-v2 boundary is commit `b689e17bf2b70ea6c2ade0c3795bb85bb048d57b`.

## Documentation Maintenance

When v2 changes:

- current state/phase/next step -> `PROJECT.md`
- cross-cutting decision -> `DECISIONS.md`
- phase scope/evidence -> `phases/PHASE_V2_*.md`
- frontend/server ownership -> `v2/FRONTEND_ARCHITECTURE.md`
- UI/UX rules -> `v2/UI_SYSTEM.md`
- account/invitation/auth rules -> `v2/ACCESS_AND_INVITATIONS.md`
- broader deployment/system boundary -> `v2/ARCHITECTURE.md`
- dated validation evidence -> `validation/`

If v1 behavior or an external-project convention is reused, document the new v2 ownership instead of making the old source active again.