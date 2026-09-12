# S.A.G.A. Project

S.A.G.A. is being rebuilt as a web-first storytelling intelligence platform. The active architecture is the S.A.G.A. v2 rebuild; pre-v2 runtime material is historical/reference only unless a v2 decision explicitly adopts it.

This file is the short source-of-truth handoff for current work.

## Current Status

**Phase 1 — Closed-Demo Main Site, Accounts & Invitations: COMPLETE.**

**Phase 2 — Story Intake & Character Identity Foundation: ACTIVE.**

- **2A Product/Data Foundation — COMPLETE.**
- **2B Source Storage & Deterministic Ingestion — COMPLETE.**
- **2C Character Identity Engine — COMPLETE.**
- **2D Repository/CI Qualification — COMPLETE.**
- **2D Hosted Proof — BLOCKED ON EXPLICIT OWNER/INFRASTRUCTURE GATES.**

Authoritative Phase-2 contract:

- `docs/phases/PHASE_V2_2_STORY_INTAKE_CHARACTER_IDENTITY.md`

Authoritative Phase-2 validation:

- `docs/validation/PHASE_V2_2A_PRODUCT_DATA_FOUNDATION_2026-09-12.md`
- `docs/validation/PHASE_V2_2B_SOURCE_INGESTION_2026-09-12.md`
- `docs/validation/PHASE_V2_2C_CHARACTER_IDENTITY_2026-09-12.md`
- `docs/validation/PHASE_V2_2D_LITBANK_ORACLE_BASELINE_2026-09-12.md`
- `docs/validation/PHASE_V2_2D_REPOSITORY_QUALIFICATION_2026-09-12.md`

Tracking issue: **#176**.

The repository-qualified product loop is:

```text
admitted member
  -> project
  -> .txt/.epub source
  -> durable source-ingestion job
  -> separate analysis worker
  -> deterministic normalized source
  -> durable character-identity job
  -> provider-neutral evidence
  -> S.A.G.A. precision-first resolver
  -> immutable character / alias / mention evidence
  -> private project evidence UI
```

Do not substitute a general agent framework, chat/RAG layer, canon extractor, or historical v1 runtime for this contract.

## Phase 2D Repository Qualification

Implementation PR **#183**:

- exact qualified implementation head: `d2f9a9bde10f689278b5facd5da027ef03e78615`
- merge: `8463f1686b4ab24cbec2fae67e027b96bd87497f`

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

### First full literary resolver-policy baseline

The dedicated evaluation workflow runs all 100 LitBank texts at pinned upstream commit `3e50db0ffc033d7ccbb94f4d88f6b99210328ed8` using oracle evidence. This isolates S.A.G.A.'s resolver policy from production-provider mention/coreference quality.

Key aggregate metrics:

- canonical precision: **0.9516**
- canonical recall: **0.9970**
- incorrect-merge rate: **0.0000**
- false-canonical rate: **0.0422**
- contaminated-canonical rate: **0.0484**
- fragmentation rate: **0.1422**
- linked-mention precision: **0.9942**
- linked-mention recall: **0.7566**
- non-person quarantine rate: **1.0000**
- cluster purity: **1.0000**

Interpretation: merge safety and precision are strong under oracle evidence. Fragmentation is the primary measured weakness. Do not reduce fragmentation by sacrificing merge safety or canonical precision. This is not a production-provider score.

### Durable lifecycle hardening

Disposable-Postgres qualification additionally proves:

- expired identity leases can be reclaimed with a new token/attempt;
- a stale worker cannot commit after losing ownership;
- invalid identity results roll back without partial run/evidence writes;
- failed validation preserves the valid current lease/job state;
- a valid reclaimed attempt persists exactly one immutable result set;
- duplicate success replay cannot create a second result run.

No Phase-2D schema workaround was added merely for qualification.

## Completed Phase-2 Baselines

### Phase 2A

PR #177, merge `7a053697e874d8fb6e0b03571b7cf0f2e885dd61`; closure `4b405ecacdb10e2a15b702210c2cdfef4daa2a9b`.

Established member-owned projects/sources, forced RLS, durable lease-based jobs, immutable analysis runs, result-table foundations, and private Projects/Library surfaces.

### Phase 2B

PR #179, exact implementation head `20a0e222aac42208b45a4faac3814208afd50762`, merge `fad0b8e5a3cc5c0e819d86fb41f50fe587574aab`; closure `7cf98cffd5b49a85d1b70cc38a6ed6bf0796b8de`.

Established provider-neutral B2 upload/read contracts, upload verification, worker-side source hashing, deterministic TXT/EPUB normalization, normalized persistence, separate v2 analysis worker and source-ingestion UI.

### Phase 2C

PR #181, exact qualified head `9643a6c997f37074b8e6827c4ad0027858040f77`, merge `191e2e4ab4ad9d4023f198b295922b5675e8d269`; closure `3de1d3806c33794ed801314c4e36632d9d3a0c79`.

Established provider-neutral identity evidence, precision-first canonical admission, attachment/quarantine/unresolved policy, deterministic alias clustering/stabilization, atomic ingestion-to-identity handoff, identity worker lifecycle, immutable Character/Alias/Mention persistence and private evidence UI.

## Hosted Resources / Current Reality

### Supabase

Dedicated S.A.G.A. project:

- ref: `scmeqnpmhomzcwecjdtu`
- organization: `Fares Home Lab`
- region: `eu-central-1`
- API URL: `https://scmeqnpmhomzcwecjdtu.supabase.co`
- public signup disabled
- custom Resend SMTP active

The historical `AI Studio` project was not reused.

Phase-2 migrations are repository-merged and disposable-Postgres qualified. **They are not yet claimed applied to hosted Supabase.** Applying them is a Phase-2D hosted mutation gate.

### Backblaze B2

Dedicated private bucket:

- bucket: `saga-v2-faresmohamed260-1207062480`
- region: `us-east-005`
- endpoint: `https://s3.us-east-005.backblazeb2.com`

Bootstrap/master credentials remain operator-only. Real hosted source I/O requires a bucket-scoped non-master runtime application key and any required browser-upload CORS. This is an explicit credential/configuration gate.

### Analysis worker / identity provider

`services/analysis-worker/` is active v2 code and repository/CI-proven, but no permanent worker host has been selected or deployed.

The production identity evidence provider/model is intentionally unselected. Oracle LitBank results measure resolver policy only. A production provider must be benchmarked against the same normalized contract and may introduce a host/GPU/API credential or cost decision.

### Vercel

Dedicated project:

- project: `saga`
- root: `apps/web`
- current temporary production alias: `https://saga-pi-two.vercel.app`

Automatic Git-triggered Preview/Production deployments are disabled.

**Deployment rule:** before any Vercel deployment, state why it is needed, Preview vs Production, and the exact commit/SHA, then obtain fresh explicit owner approval. Implementation, testing, merging, or a generic request to continue is not deployment permission.

No Phase-2 Vercel deployment has been performed.

## Required Hosted Proof Before Phase 2 Can Close

The contract now requires a real hosted lifecycle:

```text
active member
  -> creates project
  -> uploads supported source
  -> original exists in dedicated B2
  -> metadata/content digest match
  -> durable ingestion job
  -> deployed worker claims it
  -> normalization succeeds
  -> durable identity job
  -> production evidence provider + S.A.G.A. resolver
  -> immutable successful run/evidence
  -> private app renders results
  -> identical rerun yields identical semantic fingerprint
```

Security proof must also show:

- another admitted member cannot read the owner's project/source/results;
- guessing another member's object key cannot grant object access;
- suspending the owner blocks private-app access through the existing account gate;
- hosted proof data/objects are cleaned up afterward.

## Current Stop Gate

Ordinary repository implementation is no longer the blocker. Continuing Phase 2 requires explicit owner/infrastructure authorization for the hosted proof plan:

1. authorize creation/use of a **bucket-scoped B2 runtime key** and required upload CORS;
2. authorize applying the merged **Phase-2 migrations to hosted Supabase**;
3. choose/authorize a **permanent worker host/account/cost path**;
4. choose/authorize a **production identity evidence provider/model** if it requires external hosting, credentials or spend;
5. approve a **Vercel deployment** separately after the exact deploy SHA and Preview/Production target are stated.

Do not cross these gates silently.

## Open / Deferred Items

- custom domain `saga.faresuniform.uk` — issue #165; not part of Phase 2 unless explicitly resumed;
- PR #172 release identity concept — closed without merge; revisit only if hosted proof specifically needs it;
- fragmentation improvement beyond the measured baseline — future resolver optimization, not a reason to bypass hosted qualification.

## Working Convention

Every new session starts from:

1. `AGENTS.md`
2. `PROJECT.md`
3. `docs/README.md`
4. `docs/DECISIONS.md`
5. the active phase contract
6. relevant `docs/v2/` documents

GitHub is authoritative. Durable decisions, evidence and phase state go back into the repository; chat history is secondary context only.
