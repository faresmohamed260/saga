# S.A.G.A. Documentation Index

S.A.G.A. is in an owner-authorized v2 rebuild. This index separates the **active v2 source of truth** from retained **v1 historical/reference material** and read-only external project references.

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

**S.A.G.A. v2 Phase 2 — Story Intake & Character Identity Foundation: ACTIVE.**

Authoritative contract:

- `phases/PHASE_V2_2_STORY_INTAKE_CHARACTER_IDENTITY.md`

Repository/CI slice state:

- **2A Product/Data Foundation — COMPLETE**
- **2B Source Storage & Deterministic Ingestion — COMPLETE**
- **2C Character Identity Engine — COMPLETE**
- **2D Qualification / Hosted Proof — ACTIVE**

Authoritative Phase-2 validation records:

- `validation/PHASE_V2_2A_PRODUCT_DATA_FOUNDATION_2026-09-12.md`
- `validation/PHASE_V2_2B_SOURCE_INGESTION_2026-09-12.md`
- `validation/PHASE_V2_2C_CHARACTER_IDENTITY_2026-09-12.md`

The active loop is now implemented in repository/CI:

```text
member-owned project
  -> .txt/.epub source
  -> private object-storage contract + Supabase metadata
  -> durable source-ingestion job
  -> services/analysis-worker
  -> deterministic normalized source
  -> durable character-identity job
  -> provider-neutral evidence
  -> precision-first S.A.G.A. resolver
  -> immutable character / alias / mention evidence
  -> private project UI
```

Phase 2D must qualify this loop; it must not replace it with the historical v1 runtime or a general agent/LLM framework.

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
- Phase 2B closure — PR #180, merge `7cf98cffd5b49a85d1b70cc38a6ed6bf0796b8de`
- Phase 2C implementation — PR #181, merge `191e2e4ab4ad9d4023f198b295922b5675e8d269`

## Active v2 Architecture / Product Contracts

- `../AGENTS.md` — mandatory working rules and source-of-truth order
- `../PROJECT.md` — current Phase-2D handoff and hosted reality
- `DECISIONS.md` — durable cross-cutting v2 decisions
- `v2/ARCHITECTURE.md` — top-level web/data/storage/deployment boundary
- `v2/FRONTEND_ARCHITECTURE.md` — Next.js route/component/server ownership
- `v2/UI_SYSTEM.md` — S.A.G.A.-specific UI/UX and rendered-review rules
- `v2/ACCESS_AND_INVITATIONS.md` — closed-demo identity/account/admin contract
- `phases/PHASE_V2_2_STORY_INTAKE_CHARACTER_IDENTITY.md` — Phase-2 source/worker/identity/determinism/qualification contract
- `operations/VERCEL_DEPLOYMENT_POLICY.md` — manual-only Vercel deployment rule

## Active v2 Code / Operations

### Web application

- `../apps/web/` — active Next.js product
- `../apps/web/src/features/library/` — bounded source-upload interaction/action boundary
- `../apps/web/src/features/characters/` — private identity evidence UI
- `../apps/web/src/server/story/` — owner-scoped project/source/job/result/evidence services
- `../apps/web/src/server/storage/` — provider-neutral `ObjectStorage` + B2 implementation
- `../apps/web/src/server/supabase/` — ordinary SSR and isolated privileged Supabase boundaries
- `../apps/web/supabase/migrations/` — active v2 migration lineage
- `../apps/web/supabase/tests/` — disposable-Postgres contracts

### Analysis worker

- `../services/analysis-worker/` — active v2 separate analysis-worker runtime
- `../services/analysis-worker/src/ingestion/` — deterministic TXT/EPUB normalizers
- `../services/analysis-worker/src/identity/` — provider-neutral evidence + precision-first resolver
- `../services/analysis-worker/src/runtime/` — worker Supabase/B2/config boundaries
- `../services/analysis-worker/tests/` — deterministic ingestion/identity/control-plane fixtures

Do not add new v2 analysis behavior to historical pre-v2 runtime packages.

### CI / storage operations

- `../config/v2-storage.json` — safe Backblaze B2 metadata
- `../.github/workflows/v2-web-ci.yml` — web/database deterministic CI
- `../.github/workflows/v2-analysis-worker-ci.yml` — worker typecheck + deterministic fixture CI
- `../.github/workflows/v2-visual-review.yml` — production-build Chromium validation
- `../.github/workflows/v2-b2-bootstrap.yml` — manual-only B2 bootstrap/storage smoke workflow

## Phase 2 Validation Evidence

### Phase 2A

- validation: `validation/PHASE_V2_2A_PRODUCT_DATA_FOUNDATION_2026-09-12.md`
- exact head `51147ddf5855a43c3b50770502f2cf9f8fdf1f54`
- Web CI `34654618229`, Compatibility `34654618239`, Backend `34654618234`, Visual `34654618236` — success
- artifact `10284398956`

### Phase 2B

- validation: `validation/PHASE_V2_2B_SOURCE_INGESTION_2026-09-12.md`
- exact head `20a0e222aac42208b45a4faac3814208afd50762`
- merge `fad0b8e5a3cc5c0e819d86fb41f50fe587574aab`
- Web `34661457524`, Worker `34661457497`, Visual `34661457496`, Backend `34661457500`, Compatibility `34661457516` — success
- artifact `10287611789`, digest `ccadb4a2bd382ea7d69e34b9d72aa8f1ac0b6bbe5d5c8b2f0de8ad43daa61fb6`

### Phase 2C

- validation: `validation/PHASE_V2_2C_CHARACTER_IDENTITY_2026-09-12.md`
- exact head `9643a6c997f37074b8e6827c4ad0027858040f77`
- merge `191e2e4ab4ad9d4023f198b295922b5675e8d269`
- Web `34664464705`, Worker `34664464659`, Visual `34664464727`, Backend `34664464655`, Compatibility `34664464685` — success
- artifact `10288233985`, digest `03fc83ee8dad10a05e7edc33db77d7295cc02f70e90e0a4fdd3cd5dfb04d7f55`

## Current Hosted Boundary

### Supabase

Dedicated project ref `scmeqnpmhomzcwecjdtu` in `eu-central-1`; public signup disabled and custom Resend SMTP active.

The historical `AI Studio` project was not reused.

Phase-2A/2B/2C migrations are repository-merged and disposable-Postgres qualified. This index does **not** claim they have been applied to hosted Supabase.

### Vercel

Dedicated `saga` project uses `apps/web`; stable temporary production alias is `https://saga-pi-two.vercel.app`.

Git-triggered Preview/Production deployments are disabled. Any Vercel deployment requires fresh explicit owner approval after stating the reason, deployment type and exact SHA.

No Vercel deployment was performed for Phase 2A, 2B or 2C.

### Backblaze B2

Dedicated private bucket `saga-v2-faresmohamed260-1207062480` in `us-east-005`; endpoint `https://s3.us-east-005.backblazeb2.com`.

Repository B2 contracts are implemented. Real hosted source I/O still requires a bucket-scoped non-master runtime key and any required browser-upload CORS mutation. Bootstrap/master credentials remain operator-only.

### Worker / evidence provider

`services/analysis-worker/` is repository/CI-proven but not hosted. No permanent worker host or production identity evidence provider/model has been selected.

## Phase-2D Execution Boundary

Phase 2D is active.

Repository-only work may continue without hosted credentials:

1. retry/idempotency/concurrency hardening;
2. offline literature-oriented benchmark/evaluation harness;
3. first v2 baseline report for false canonicals, fragmentation/merge behavior, mention quality and coreference/identity metrics where gold data permits;
4. dedicated/manual heavyweight evaluation workflow if useful, without model/dataset downloads in normal merge CI;
5. final deterministic/rendered qualification packaging;
6. a precise hosted proof plan.

Hosted execution stops at the explicit gates in the phase contract:

- bucket-scoped B2 runtime key / upload CORS;
- hosted Phase-2 Supabase migration application;
- worker host/provider/account/cost selection and deployment;
- paid/proprietary evidence-provider credential selection;
- Vercel Preview or Production deployment.

Do not interpret a request to implement, merge, test, review, finish or continue as deployment approval.

## Open / Deferred Work

- custom domain `saga.faresuniform.uk` — issue #165; not current Phase-2 scope unless explicitly resumed;
- hosted B2 runtime key/CORS;
- hosted Phase-2 Supabase migrations;
- worker host/provider/cost;
- production identity evidence provider choice;
- explicitly approved Vercel deployment;
- PR #172 release identity concept — closed without merge; reconsider only if hosted proof needs it.

## Historical v1 Material

Historical docs/code remain useful for requirements, algorithms, evaluation history and lessons, but they are not active v2 architecture unless deliberately re-adopted. Important references include `analysis_foundation_runtime.md`, `identity_runtime.md`, `canon_extraction_runtime.md`, `system_agent_roadmap.md`, and the other retained runtime documents. The clean pre-v2 boundary is commit `b689e17bf2b70ea6c2ade0c3795bb85bb048d57b`.

## RenderLab Reference Boundary

`faresmohamed260/renderlab` is a separate product and read-only process/architecture/UI reference only. Do not modify it or copy its product code, visual identity, routes, schema, data, credentials, storage assumptions or deployment state.

## Documentation Maintenance

When v2 changes:

- current state/phase/next step -> `PROJECT.md`
- cross-cutting decision -> `DECISIONS.md`
- phase scope/evidence -> `phases/` and `validation/`
- frontend/server ownership -> `v2/FRONTEND_ARCHITECTURE.md`
- UI/UX rules -> `v2/UI_SYSTEM.md`
- account/auth rules -> `v2/ACCESS_AND_INVITATIONS.md`
- broader system/deployment boundary -> `v2/ARCHITECTURE.md`

If v1 behavior or an external-project convention is reused, document the new v2 ownership instead of making the old source active again.
