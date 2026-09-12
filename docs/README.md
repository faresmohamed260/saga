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

Authoritative contract:

- `phases/PHASE_V2_2_STORY_INTAKE_CHARACTER_IDENTITY.md`

Repository/CI slice state:

- **2A Product/Data Foundation — COMPLETE**
- **2B Source Storage & Deterministic Ingestion — COMPLETE**
- **2C Character Identity Engine — NEXT**
- **2D Qualification / Hosted Proof — PENDING**

Authoritative Phase-2 evidence:

- `validation/PHASE_V2_2A_PRODUCT_DATA_FOUNDATION_2026-09-12.md`
- `validation/PHASE_V2_2B_SOURCE_INGESTION_2026-09-12.md`

The active loop is:

```text
member-owned project
  -> .txt/.epub source
  -> private B2 object + Supabase metadata
  -> durable Postgres analysis job
  -> services/analysis-worker
  -> deterministic normalized source
  -> precision-first character identity resolution
  -> character / alias / mention evidence in the private app
```

The phase explicitly avoids recreating the old v1 monolithic runtime or jumping to a general agent/LLM framework.

## Active v2 Governance

- `../AGENTS.md` — mandatory working rules, source-of-truth order, phase discipline, v2/v1 boundary, RenderLab boundary
- `../PROJECT.md` — current state, completed 2A/2B baselines, hosted reality, deferred gates and immediate 2C work
- `DECISIONS.md` — durable cross-cutting v2 decisions
- `phases/PHASE_V2_2_STORY_INTAKE_CHARACTER_IDENTITY.md` — active Phase-2 product/data/job/provider/testing/hosted-validation contract
- `phases/PHASE_V2_1_CLOSED_DEMO_APP.md` — completed Phase-1 contract
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
- Phase 2A implementation — PR #177, merge `7a053697e874d8fb6e0b03571b7cf0f2e885dd61`
- Phase 2A closure — PR #178, merge `4b405ecacdb10e2a15b702210c2cdfef4daa2a9b`
- Phase 2B implementation — PR #179, merge `fad0b8e5a3cc5c0e819d86fb41f50fe587574aab`

## Active v2 Architecture / Product Contracts

- `v2/ARCHITECTURE.md` — top-level web/data/storage/deployment ownership boundary
- `v2/FRONTEND_ARCHITECTURE.md` — Next.js route/component/server ownership
- `v2/UI_SYSTEM.md` — S.A.G.A.-specific UI/UX, accessibility/responsive/render-review rules
- `v2/PHASE_1D_UI_CONCEPT.md` — approved Narrative Desk shell direction
- `v2/ACCESS_AND_INVITATIONS.md` — closed-demo identity/account/invitation/admin contract
- `phases/PHASE_V2_2_STORY_INTAKE_CHARACTER_IDENTITY.md` — active source/worker/identity/determinism/qualification contract

## Active v2 Code / Operations

### Web application

- `../apps/web/` — active Next.js product
- `../apps/web/src/components/shell/` — Narrative Desk shell/navigation
- `../apps/web/src/features/auth/` — auth/invitation/password surfaces
- `../apps/web/src/features/admin/` — Admin operations/workspace
- `../apps/web/src/features/projects/` — project actions
- `../apps/web/src/features/library/` — bounded source-upload interaction/action boundary
- `../apps/web/src/server/account/` — fresh identity/access resolution
- `../apps/web/src/server/admin/` — active-admin services
- `../apps/web/src/server/story/` — member-scoped project/source/job/result/upload services
- `../apps/web/src/server/storage/` — provider-neutral `ObjectStorage` + B2 implementation
- `../apps/web/src/server/supabase/` — ordinary SSR and isolated privileged Supabase boundaries
- `../apps/web/supabase/migrations/` — active v2 migration lineage
- `../apps/web/supabase/tests/` — disposable-Postgres contracts

### Analysis worker

- `../services/analysis-worker/` — active v2 separate analysis-worker runtime
- `../services/analysis-worker/src/ingestion/` — deterministic TXT/EPUB normalizers and fingerprints
- `../services/analysis-worker/src/runtime/` — worker Supabase/B2/config boundaries
- `../services/analysis-worker/tests/` — deterministic normalizer/control-plane fixtures

This worker is v2-owned. Do not add new v2 analysis functionality to the historical pre-v2 Python/runtime surfaces.

### CI / storage operations

- `../config/v2-storage.json` — safe Backblaze B2 metadata
- `../.github/workflows/v2-web-ci.yml` — web/database deterministic CI
- `../.github/workflows/v2-analysis-worker-ci.yml` — analysis-worker typecheck + fixture CI
- `../.github/workflows/v2-visual-review.yml` — production-build Chromium validation
- `../.github/workflows/v2-b2-bootstrap.yml` — manual-only B2 bootstrap/storage smoke workflow

## Phase 2 Validation Evidence

### Phase 2A

- validation record: `validation/PHASE_V2_2A_PRODUCT_DATA_FOUNDATION_2026-09-12.md`
- exact implementation head: `51147ddf5855a43c3b50770502f2cf9f8fdf1f54`
- Web CI `34654618229` — success
- Compatibility `34654618239` — success
- Backend Architecture `34654618234` — success
- Visual Review `34654618236` — success
- artifact `10284398956`

### Phase 2B

- validation record: `validation/PHASE_V2_2B_SOURCE_INGESTION_2026-09-12.md`
- exact implementation head: `20a0e222aac42208b45a4faac3814208afd50762`
- implementation merge: `fad0b8e5a3cc5c0e819d86fb41f50fe587574aab`
- Web CI `34661457524` — success
- Analysis Worker CI `34661457497` — success
- Visual Review `34661457496` — success
- Backend Architecture `34661457500` — success
- Compatibility `34661457516` — success
- artifact `10287611789`, digest `ccadb4a2bd382ea7d69e34b9d72aa8f1ac0b6bbe5d5c8b2f0de8ad43daa61fb6`

The visual artifact retains the shared workflow's older Phase-2A artifact name; use the recorded exact head/digest rather than inferring phase ownership from the artifact label.

## Phase 1 Validation Evidence

- `validation/PHASE_V2_1B_ACCOUNT_ACCESS_2026-09-11.md`
- `validation/PHASE_V2_1C_AUTH_ACCESS_2026-09-11.md`
- `validation/PHASE_V2_1D_NARRATIVE_DESK_2026-09-11.md`
- `validation/PHASE_V2_1E_ADMIN_OPERATIONS_2026-09-11.md`
- `validation/PHASE_V2_1E_HOSTED_SUPABASE_2026-09-11.md`
- `validation/PHASE_V2_1E_HOSTED_VERCEL_2026-09-11.md`
- `validation/PHASE_V2_1_HOSTED_AUTH_LIVE_PROOF_2026-09-11.md`

Key hosted proof runs:

- access/suspension `34647243289` — success
- full invitation lifecycle `34647592382` — success

## Current Hosted Boundary

### Supabase

Dedicated project:

- ref `scmeqnpmhomzcwecjdtu`
- region `eu-central-1`
- public signup disabled
- custom Resend SMTP active
- Auth Site URL currently `https://saga-pi-two.vercel.app`
- future custom-domain redirect allowance includes `https://saga.faresuniform.uk/**`

The existing `AI Studio` project was not reused.

Phase-2A/2B migrations are repository-merged and disposable-Postgres qualified. This index does **not** claim they have been applied to hosted Supabase; that must be proven explicitly during hosted qualification.

### Vercel

Dedicated `saga` project uses `apps/web`.

The historical `studio` project is disconnected. Git-triggered Preview/Production deployments are disabled. Any Vercel deployment requires fresh explicit owner approval after stating the reason, deployment type, and exact SHA.

No Vercel deployment was performed for Phase 2A or Phase 2B.

### Backblaze B2

The dedicated private S.A.G.A. bucket is validated and the Phase-2B repository integration is implemented. Real hosted source object I/O still requires a bucket-scoped non-master runtime application key and any required browser-upload CORS configuration.

Bootstrap/master credentials remain operator-only.

### Analysis worker hosting

`services/analysis-worker/` is repository/CI-proven but not hosted. Permanent host/provider/account/cost selection remains deliberately deferred until Phase 2D hosted proof requires it.

## Open / Deferred Work

- custom domain `saga.faresuniform.uk` — issue #165; not current Phase-2 scope unless explicitly resumed;
- scoped B2 runtime credential + upload CORS — hosted proof gate;
- hosted application of Phase-2 migrations — hosted proof step;
- worker host/provider/cost — hosted proof gate;
- Vercel deployment — explicit per-deployment owner approval required;
- PR #172 release identity concept — closed without merge; reconsider only if a future hosted gate needs it.

## Phase-2 Execution Boundary

1. **2A Product/data foundation — COMPLETE**
2. **2B Source storage + deterministic ingestion — COMPLETE**
3. **2C Character identity engine — NEXT**
4. **2D Qualification — PENDING**

Phase 2C should add the provider-neutral evidence interface, conservative canonical admission, deterministic alias/name clustering, attachment/quarantine/unresolved policy, adversarial historical-failure fixtures, immutable identity-run persistence, and a user-visible character/evidence surface.

Do not embed full-book NLP in Next.js requests.

Do not use a generative LLM as a shortcut around the deterministic identity contract.

Do not let a provider/coreference model bypass S.A.G.A. canonical-admission policy.

## RenderLab Reference Boundary

`faresmohamed260/renderlab` is a separate product and read-only process/architecture/UI reference only.

Do not modify RenderLab or copy its product code, page composition, visual identity, routes, schema/table names, data, credentials, storage or deployment state.

## Historical v1 Material

Historical documents and pre-v2 code remain useful for requirements discovery, algorithms, evaluation history, provider experiments, and lessons learned, but do **not** define active v2 architecture unless deliberately re-adopted.

Important historical docs include:

- `system_agent_roadmap.md`
- `analysis_foundation_runtime.md`
- `identity_runtime.md`
- `canon_extraction_runtime.md`
- `character_world_modeling_runtime.md`
- `retrieval_runtime.md`
- `generation_planning_runtime.md`
- `narrative_generation_runtime.md`
- `visual_generation_runtime.md`
- `audiobook_generation_runtime.md`
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
- account/auth rules -> `v2/ACCESS_AND_INVITATIONS.md`
- broader system/deployment boundary -> `v2/ARCHITECTURE.md`
- dated deterministic/hosted evidence -> `validation/`

If v1 behavior or an external-project convention is reused, document the new v2 ownership instead of making the old source active again.
