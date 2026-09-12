# S.A.G.A. Documentation Index

S.A.G.A. is in an owner-authorized v2 rebuild. This index separates the **active v2 source of truth** from retained **v1 historical/reference material** and read-only external project references.

## Read First

For substantial current work, read in this order:

1. `../AGENTS.md`
2. `../PROJECT.md`
3. `DECISIONS.md`
4. the current phase contract referenced by `PROJECT.md`
5. the relevant `v2/` document

GitHub is authoritative. Do not reconstruct project state from chat history when the repository can establish it.

## Current Phase State

**Phase 1 — Closed-Demo Main Site, Accounts & Invitations: COMPLETE.**

**Phase 2 — Story Intake & Character Identity Foundation: ACTIVE.**

- **2A Product/Data Foundation — COMPLETE**
- **2B Source Storage & Deterministic Ingestion — COMPLETE**
- **2C Character Identity Engine — COMPLETE**
- **2D Repository/CI Qualification — COMPLETE**
- **2D Hosted Proof — BLOCKED ON EXPLICIT OWNER/INFRASTRUCTURE GATES**

Authoritative contract:

- `phases/PHASE_V2_2_STORY_INTAKE_CHARACTER_IDENTITY.md`

Authoritative Phase-2 validation:

- `validation/PHASE_V2_2A_PRODUCT_DATA_FOUNDATION_2026-09-12.md`
- `validation/PHASE_V2_2B_SOURCE_INGESTION_2026-09-12.md`
- `validation/PHASE_V2_2C_CHARACTER_IDENTITY_2026-09-12.md`
- `validation/PHASE_V2_2D_LITBANK_ORACLE_BASELINE_2026-09-12.md`
- `validation/PHASE_V2_2D_REPOSITORY_QUALIFICATION_2026-09-12.md`

The repository-qualified loop is:

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

Phase 2 is not complete until the hosted lifecycle/security proof in the phase contract succeeds.

## Phase Baselines

- Phase 0 web foundation — PR #149, merge `261b75ff2a60dfcada681af6b6c918c1ff5e3366`
- Phase 1 contract/governance — PR #152, merge `55beaccab011a4c5337db86dd88b52f6d48734c4`
- Phase 1B account/access — PR #153, merge `5d5b59d17d2bd2f9a5769d2e5c4f9a2b43d1bad9`
- Phase 1C auth/access — PR #156, merge `319b785e43a169b4ffd7b57cd5be32ad3ef5da67`
- Phase 1D Narrative Desk — PR #160, merge `f558a282b4743a15d440eada1c6a7ccefe44215c`
- Phase 1E deterministic Admin — PR #162, merge `39dceaf1254ed7616ed1bd9eb640d9d622a73812`
- Phase 1 hosted closure — PR #174, merge `3802222714c300b9777b65b34f94668be50f9582`
- Phase 2 contract — PR #175, merge `bf955d3d02f327a655d4406615b2e1fa6e35e574`
- Phase 2A implementation — PR #177, merge `7a053697e874d8fb6e0b03571b7cf0f2e885dd61`
- Phase 2A closure — PR #178, merge `4b405ecacdb10e2a15b702210c2cdfef4daa2a9b`
- Phase 2B implementation — PR #179, merge `fad0b8e5a3cc5c0e819d86fb41f50fe587574aab`
- Phase 2B closure — PR #180, merge `7cf98cffd5b49a85d1b70cc38a6ed6bf0796b8de`
- Phase 2C implementation — PR #181, merge `191e2e4ab4ad9d4023f198b295922b5675e8d269`
- Phase 2C closure — PR #182, merge `3de1d3806c33794ed801314c4e36632d9d3a0c79`
- Phase 2D repository qualification — PR #183, merge `8463f1686b4ab24cbec2fae67e027b96bd87497f`

## Phase 2D Qualification Evidence

Qualified implementation head:

`d2f9a9bde10f689278b5facd5da027ef03e78615`

All exact-head gates succeeded:

- Web CI `34685115665`
- Analysis Worker CI `34685115685`
- LitBank Oracle Baseline `34685115664`
- Visual Review `34685115657`
- Backend Architecture CI `34685115676`
- Required Check Compatibility `34685115693`

Exact-head artifacts:

- LitBank baseline `10295097975`, digest `c355176afac421e1a040c5e5be20766f4a650f24c697cfb147df6ba17bc4970b`
- rendered visual evidence `10294934622`, digest `72487b6cc34a91c74427419c0f74d225514b19c5f16d599ffec99faa61bb85c3`

The 100-document LitBank oracle-evidence baseline reports:

- canonical precision `0.9516`
- canonical recall `0.9970`
- incorrect-merge rate `0.0000`
- fragmentation rate `0.1422`
- linked-mention precision `0.9942`
- linked-mention recall `0.7566`
- non-person quarantine rate `1.0000`
- cluster purity `1.0000`

This is a resolver-policy baseline under oracle evidence, not a production-provider score.

## Active v2 Architecture / Product Contracts

- `../AGENTS.md` — mandatory working rules/source-of-truth order
- `../PROJECT.md` — current handoff and explicit hosted stop gates
- `DECISIONS.md` — durable cross-cutting decisions
- `v2/ARCHITECTURE.md` — web/data/storage/deployment ownership
- `v2/FRONTEND_ARCHITECTURE.md` — Next.js route/component/server ownership
- `v2/UI_SYSTEM.md` — Narrative Desk UI/UX/render-review rules
- `v2/ACCESS_AND_INVITATIONS.md` — closed-demo identity/account/admin contract
- `phases/PHASE_V2_2_STORY_INTAKE_CHARACTER_IDENTITY.md` — active Phase-2 contract
- `operations/VERCEL_DEPLOYMENT_POLICY.md` — manual-only Vercel deployment rule

## Active v2 Code / Operations

### Web application

- `../apps/web/` — active Next.js product
- `../apps/web/src/features/library/` — source upload interaction
- `../apps/web/src/features/characters/` — private identity evidence UI
- `../apps/web/src/server/story/` — owner-scoped project/source/job/result services
- `../apps/web/src/server/storage/` — provider-neutral `ObjectStorage` + B2 implementation
- `../apps/web/src/server/supabase/` — ordinary SSR and isolated privileged Supabase boundaries
- `../apps/web/supabase/migrations/` — active v2 migration lineage
- `../apps/web/supabase/tests/` — disposable-Postgres contracts, including Phase-2D identity hardening

### Analysis worker

- `../services/analysis-worker/` — active v2 separate analysis-worker runtime
- `../services/analysis-worker/src/ingestion/` — deterministic TXT/EPUB normalizers
- `../services/analysis-worker/src/identity/` — provider-neutral evidence + precision-first resolver
- `../services/analysis-worker/src/evaluation/` — v2 identity evaluation/LitBank adapter
- `../services/analysis-worker/src/runtime/` — worker Supabase/B2/config boundaries
- `../services/analysis-worker/tests/` — deterministic ingestion/identity/evaluation fixtures

Do not add new v2 analysis behavior to historical pre-v2 runtime packages.

### CI / storage operations

- `../config/v2-storage.json` — safe B2 metadata
- `../.github/workflows/v2-web-ci.yml` — web/database CI
- `../.github/workflows/v2-analysis-worker-ci.yml` — worker deterministic CI
- `../.github/workflows/v2-litbank-oracle-baseline.yml` — pinned 100-document literary baseline
- `../.github/workflows/v2-visual-review.yml` — production-build Chromium validation
- `../.github/workflows/v2-b2-bootstrap.yml` — manual-only B2 bootstrap/storage smoke

## Hosted Boundary / Current Stop Gate

The repository implementation is no longer the blocker. Phase 2 now needs real hosted proof and therefore explicit owner/infrastructure authorization.

### Supabase

Dedicated project ref `scmeqnpmhomzcwecjdtu` in `eu-central-1`. Phase-2 migrations are repository-qualified but are **not yet claimed applied** to hosted Supabase.

### Backblaze B2

Dedicated private bucket `saga-v2-faresmohamed260-1207062480` in `us-east-005`. Real hosted source I/O requires a bucket-scoped non-master runtime key and any required browser-upload CORS mutation.

### Worker / production evidence provider

`services/analysis-worker/` is CI-proven but not permanently hosted. A worker host/account/cost path must be selected and authorized. A production identity evidence provider/model must also be selected and benchmarked; external hosting/credentials/spend require explicit authorization.

### Vercel

Dedicated project `saga`, root `apps/web`, with Git-triggered deployments disabled. Any Preview or Production deployment requires fresh explicit owner approval after stating the reason, deployment type and exact SHA.

Do not interpret implement/merge/test/review/continue as deployment approval.

## Open / Deferred Work

- hosted B2 runtime key/CORS;
- hosted Phase-2 Supabase migration application;
- permanent worker host/provider/cost;
- production identity evidence provider/model;
- separately approved Vercel deployment;
- hosted cross-user/object-isolation/deterministic-rerun proof and cleanup;
- custom domain `saga.faresuniform.uk` — issue #165, outside Phase 2 unless explicitly resumed;
- PR #172 release identity concept — closed without merge.

## Historical v1 / RenderLab Boundaries

Historical S.A.G.A. code/docs remain reference-only unless explicitly re-adopted into v2. The clean pre-v2 boundary is `b689e17bf2b70ea6c2ade0c3795bb85bb048d57b`.

`faresmohamed260/renderlab` remains a separate product and read-only process/architecture/UI reference only. Do not modify it or copy its product code, visual identity, routes, schema, data, credentials, storage assumptions, or deployment state.

## Documentation Maintenance

When v2 changes:

- current state/next gate -> `PROJECT.md`
- cross-cutting decision -> `DECISIONS.md`
- phase scope/evidence -> `phases/` and `validation/`
- frontend/server ownership -> `v2/FRONTEND_ARCHITECTURE.md`
- UI rules -> `v2/UI_SYSTEM.md`
- account/auth rules -> `v2/ACCESS_AND_INVITATIONS.md`
- system/deployment boundary -> `v2/ARCHITECTURE.md`
