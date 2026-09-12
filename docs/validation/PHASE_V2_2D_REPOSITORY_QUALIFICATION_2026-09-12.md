# Phase 2D Repository Qualification — 2026-09-12

## Status

The repository/CI portion of **Phase 2D — End-to-End Qualification** is complete.

This record does **not** close Phase 2. The authoritative phase contract still requires hosted lifecycle/security proof against dedicated S.A.G.A. infrastructure. Those remaining steps now require explicit external credentials, infrastructure/provider choices, hosted mutations, and a separately approved Vercel deployment.

## Implementation

Phase-2D repository qualification PR: **#183**

- qualified implementation head: `d2f9a9bde10f689278b5facd5da027ef03e78615`
- merge: `8463f1686b4ab24cbec2fae67e027b96bd87497f`

## What was qualified

### Literary benchmark/evaluation

Phase 2D added a v2-owned evaluation layer under `services/analysis-worker` that:

- consumes S.A.G.A.'s normalized identity evidence/result contracts;
- reports count-based, micro-aggregated identity metrics;
- separates resolver-policy quality from provider/model quality;
- includes deterministic metric tests that deliberately exercise false canonicals, incorrect merges, fragmentation and contamination;
- includes a LitBank TSV/coreference adapter;
- includes a real LitBank-derived Secret Garden smoke fixture;
- runs the complete 100-document LitBank oracle-evidence baseline in a dedicated workflow pinned to upstream commit `3e50db0ffc033d7ccbb94f4d88f6b99210328ed8`;
- keeps the full corpus and heavyweight model/provider work out of ordinary merge CI.

The first baseline is recorded separately in:

- `PHASE_V2_2D_LITBANK_ORACLE_BASELINE_2026-09-12.md`

Key oracle-evidence metrics:

| Metric | Value |
| --- | ---: |
| Canonical precision | 0.9516 |
| Canonical recall | 0.9970 |
| False-canonical rate | 0.0422 |
| Incorrect-merge rate | 0.0000 |
| Contaminated-canonical rate | 0.0484 |
| Fragmentation rate | 0.1422 |
| Linked-mention precision | 0.9942 |
| Linked-mention recall | 0.7566 |
| Non-person quarantine rate | 1.0000 |
| Cluster purity | 1.0000 |

Interpretation remains precision-first: the resolver shows strong merge safety and linked precision under oracle evidence. Fragmentation is the primary measured weakness and must not be reduced by introducing unsafe merges or lower canonical precision.

### Durable job/result hardening

The disposable-Postgres qualification now proves the identity-specific lifecycle beyond the earlier generic queue tests:

- expired `character_identity` lease can be reclaimed by a new worker attempt;
- reclaimed attempt receives a new lease token and incremented attempt count;
- worker that lost lease ownership cannot commit identity success;
- invalid identity result validation is transactionally atomic;
- failed result validation leaves no partial analysis run, character or mention rows;
- failed validation leaves the valid current worker lease/job state intact;
- the valid reclaimed lease persists exactly one immutable run/result set;
- replaying success after the lease is cleared is rejected and cannot create a duplicate run.

These tests exercise the existing production database functions. No Phase-2D production schema workaround was introduced merely to satisfy qualification.

## Exact-head CI evidence

Qualified implementation head:

`d2f9a9bde10f689278b5facd5da027ef03e78615`

All active gates succeeded:

- SAGA v2 Web CI `34685115665` — success
- SAGA v2 Analysis Worker CI `34685115685` — success
- SAGA v2 LitBank Oracle Baseline `34685115664` — success
- SAGA v2 Visual Review `34685115657` — success
- Backend Architecture CI `34685115676` — success
- Required Check Compatibility `34685115693` — success

Exact-head artifacts:

- LitBank baseline artifact `10295097975`
  - name `saga-v2-litbank-oracle-baseline`
  - digest `sha256:c355176afac421e1a040c5e5be20766f4a650f24c697cfb147df6ba17bc4970b`
- rendered visual artifact `10294934622`
  - name `saga-v2-phase-2c-visual-review`
  - digest `sha256:72487b6cc34a91c74427419c0f74d225514b19c5f16d599ffec99faa61bb85c3`

The rendered artifact retains the prior workflow artifact name; phase ownership is established by the exact head/run IDs above.

## Remaining Phase-2 hosted proof

The authoritative phase contract requires a real hosted lifecycle before Phase 2 can close. The remaining proof is:

```text
active member
  -> project
  -> real .txt/.epub upload
  -> object exists in dedicated B2 bucket
  -> content/metadata verified
  -> durable ingestion job
  -> deployed worker normalizes source
  -> durable identity job
  -> production evidence provider + S.A.G.A. resolver
  -> immutable successful run/evidence
  -> private web UI renders results
  -> identical rerun produces same semantic fingerprint
```

Hosted security proof must also demonstrate another admitted member cannot read the owner's project/source/results or obtain object access by guessing an object key, and proof records must be cleaned up afterward.

## Explicit external gates

Repository work has reached the following real gates:

1. **Backblaze B2 runtime credential/CORS**
   - create/authorize a bucket-scoped non-master runtime application key;
   - apply only the browser-upload CORS permissions required by the active source flow.

2. **Hosted Supabase mutation**
   - apply the merged Phase-2 migrations to dedicated project `scmeqnpmhomzcwecjdtu`;
   - record exact migration lineage/state.

3. **Worker hosting decision**
   - select/authorize a permanent host/account/cost path for `services/analysis-worker`;
   - deploy the exact approved worker revision.

4. **Production identity evidence provider decision**
   - select a provider/model path compatible with the normalized evidence contract;
   - if the choice needs external hosting, credentials, GPU spend or a paid API, obtain explicit authorization before enabling it;
   - benchmark that provider separately from this oracle-policy baseline.

5. **Vercel deployment authorization**
   - hosted private-app proof needs a Vercel deployment containing the Phase-2 web/runtime integration;
   - before deployment, state reason, Preview vs Production and exact SHA, then obtain fresh explicit owner approval.

None of those gates was crossed by PR #183 or this documentation closure.

## Phase state after this record

- Phase 2A — COMPLETE
- Phase 2B — COMPLETE
- Phase 2C — COMPLETE
- Phase 2D repository/CI qualification — COMPLETE
- Phase 2D hosted proof — BLOCKED ON EXPLICIT OWNER/INFRASTRUCTURE GATES
- Phase 2 overall — ACTIVE until hosted proof succeeds and is cleaned up/documented
