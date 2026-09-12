# Phase 2D LitBank Oracle-Evidence Baseline — 2026-09-12

## Purpose

This record captures the first full literary benchmark baseline for the S.A.G.A. v2 character-identity policy.

It is a **resolver-policy baseline**, not a production identity-provider/model benchmark.

The benchmark converts LitBank gold entity/coreference annotations into S.A.G.A.'s provider-neutral normalized evidence contract and then evaluates the deterministic S.A.G.A. resolver. That intentionally removes provider/model mention-recall errors so the result answers a narrower question:

> Given high-quality literary mention/coreference evidence, how does S.A.G.A.'s precision-first canonical admission and attachment policy behave?

A future production-provider qualification must run the same evaluator with evidence produced by the selected provider. Do not compare those provider-backed numbers to this oracle baseline without preserving that distinction.

## Dataset provenance

- Dataset: LitBank
- Upstream repository: `dbamman/litbank`
- Pinned upstream commit: `3e50db0ffc033d7ccbb94f4d88f6b99210328ed8`
- Documents evaluated: **100**
- Corpus contents are not vendored into S.A.G.A.
- The dedicated benchmark workflow checks out the pinned corpus revision at runtime.

The v2 adapter consumes LitBank's `coref/tsv` annotation representation, including `MENTION` records with literary entity/mention typing and `COREF` cluster assignments.

## First successful full-corpus run

S.A.G.A. implementation head:

`2deb3b1b6c13953ea2acdfb95cc5f8c17e410627`

Workflow:

- `SAGA v2 LitBank Oracle Baseline`
- run `34684766559`
- conclusion: **success**

Artifact:

- ID: `10295212345`
- name: `saga-v2-litbank-oracle-baseline`
- artifact ZIP digest: `sha256:c5f750c76357a79b62c8fc08af67189eb05fab562419478408847f90c471f146`
- retention: 90 days from the run

## Aggregate counts

| Measure | Count |
| --- | ---: |
| Documents | 100 |
| Gold seed-eligible characters | 675 |
| Predicted canonicals | 805 |
| Pure canonicals | 766 |
| False canonicals | 34 |
| Incorrect merges | 0 |
| Contaminated canonicals | 39 |
| Represented gold characters | 673 |
| Fragmentation excess | 96 |
| Relevant gold mentions | 13,932 |
| Predicted mentions | 29,103 |
| Correct linked mentions | 10,541 |
| Linked mentions | 10,602 |
| Unresolved relevant mentions | 3,315 |
| Quarantined relevant mentions | 54 |
| Non-person predicted mentions | 4,923 |
| Non-person linked mentions | 0 |
| Non-person quarantined mentions | 4,923 |

## Aggregate metrics

| Metric | Value |
| --- | ---: |
| Canonical precision | **0.9516** |
| Canonical recall | **0.9970** |
| False-canonical rate | **0.0422** |
| Incorrect-merge rate | **0.0000** |
| Contaminated-canonical rate | **0.0484** |
| Fragmentation rate | **0.1422** |
| Linked-mention precision | **0.9942** |
| Linked-mention recall | **0.7566** |
| Unresolved relevant-mention rate | **0.2379** |
| Quarantined relevant-mention rate | **0.0039** |
| Non-person quarantine rate | **1.0000** |
| Cluster purity | **1.0000** |

## Interpretation

The result supports the intended precision-first architecture:

- **no incorrect merges** were observed under oracle evidence;
- linked mention decisions were extremely precise (**99.42%**);
- non-person evidence was completely prevented from becoming linked character evidence (**100% quarantined**);
- almost every seed-eligible gold character was represented (**99.70% canonical recall**).

The main observed cost is **fragmentation**:

- 805 canonicals were predicted for 675 seed-eligible gold characters;
- 96 excess canonical fragments were measured;
- aggregate fragmentation rate was **14.22%**.

This is preferable to identity collapse/incorrect merging for the current S.A.G.A. contract, but it is not a completion target. Fragmentation should be the primary resolver-hardening target after the hosted/provider boundary is known, provided improvements do not regress merge safety or canonical precision.

The baseline also shows why linked-mention recall must not be interpreted alone: **75.66%** linked recall coexists with **99.42%** linked precision because the policy deliberately leaves ambiguous evidence unresolved instead of forcing attachment.

## Qualification policy

This baseline is a measurement, not a silently chosen release threshold.

Phase 2D should preserve the following invariants while further hardening proceeds:

1. incorrect-merge rate must remain at or extremely near zero;
2. non-person evidence must not become character canonicals or linked character evidence;
3. canonical and linked-mention precision take priority over forced recall;
4. unresolved/quarantined evidence remains valid output;
5. any fragmentation reduction must be evaluated against merge/contamination regressions, not optimized in isolation.

No production-provider acceptance threshold is established by this record because no production identity provider has yet been selected.

## CI ownership

- committed evaluator tests run inside the normal Analysis Worker CI and require no corpus checkout;
- full LitBank evaluation runs in `.github/workflows/v2-litbank-oracle-baseline.yml`;
- the workflow is pinned to the upstream LitBank commit above;
- the full JSON result is retained as a GitHub Actions artifact;
- ordinary application/runtime changes do not vendor or implicitly update the corpus.

## Hosted boundary

This benchmark required no hosted S.A.G.A. mutation.

It does **not** prove:

- hosted Supabase Phase-2 migration state;
- real Backblaze B2 upload/download with a bucket-scoped runtime credential;
- a deployed permanent analysis worker;
- a production identity evidence provider/model;
- a Vercel-hosted end-to-end Phase-2 lifecycle.

Those remain separate Phase-2D external qualification gates.
