**Identity Runtime**

Reusable active identity runtime for canonical character clustering, backed by the Modal xcore provider and hardened by an evidence-grounded review pass.

**Active surfaces**

- Package: `packages/identity_runtime`
- Client: `packages/identity_runtime/client.py`
- Contracts: `packages/identity_runtime/contracts.py`
- Review policy: `packages/identity_runtime/review.py`
- Pairwise evaluation: `packages/identity_runtime/canonicalization_evaluation.py`

**Ownership**

Identity contamination handling belongs here.

Downstream slices such as canon extraction and character/world modeling must consume reviewed identity output, not compensate for contaminated clusters.

**Review outputs**

The review layer defines and returns:

- `IdentityAliasEvidence`
- `IdentityQualityDiagnostic`
- `ReviewedIdentityCluster`
- `IdentityGroundingReviewResult`

These contracts capture:

- grounded alias support counts
- chapter and scene support
- matched canonical identities
- accepted aliases
- rejected aliases
- dropped clusters
- structured rejection diagnostics
- canonical merge provenance with every contributing provider cluster ID

**Current deterministic policy**

The active review pass rejects:

- cross-character alias bleed
- pronoun-like aliases
- narrator/second-person contamination
- generic role aliases
- generic non-character clusters
- malformed long-span aliases
- ambiguous aliases claimed by multiple clusters

The review pass preserves grounded named aliases when they remain stable character surface forms.

The same pass canonicalizes fragmented provider clusters only when a provider alias claim and compatible name structure agree. Honorific, full/partial-name, and evidence-linked descriptor variants are supported. Shared surnames and unrelated clusters that merely claim a popular character name do not merge.

Pairwise quality gates report precision, recall, F1, over-merge rate, fragmentation rate, and contamination rate from portable labeled datasets.

**Persistence and reporting**

Analysis foundation persists review results into the canonical identity bundle:

- counters in `source_stats`
- full diagnostics in `metadata.identity_review`

Service-level quality audits surface:

- `review_kept_cluster_count`
- `review_dropped_cluster_count`
- `review_rejected_alias_count`
- `review_diagnostic_codes`

**Real validation reference**

Validated on:

- `D:\Books\Ebooks\Holly Black\The Lost Sisters\The Lost Sisters.epub`

Fresh hardened series:

- `real-holly-black-lost-sisters-v9`

Observed before/after improvement versus earlier contaminated Holly Black runs:

- removed `Prince Cardan -> Locke`
- removed `Vivi -> Taryn`
- removed `Mr. Fox -> Locke`
- removed narrator-style alias noise such as `my sister`, `your sister`, `Twin sister`, `this Heather`
- removed obvious non-character clusters such as `Faerie`, `Revelers in rags`, and `The fiddler`
- reduced pronoun pollution in canonical identity bundles

Validated additionally against persisted `Once Upon a Broken Heart` RC36 data:

- 343 reviewed provider clusters and 107 real scenes evaluated in 36.2 seconds without provider inference
- `Evangeline`, `Evangeline Fox`, `Miss Fox`, `Little Fox`, and titled forms unified with source-cluster provenance
- `Maximilian Fox`, `Liana Fox`, unrelated contaminated clusters, and a malformed combined-name cluster remained separate
- curated 18-pair quality gate: precision 1.0, recall 1.0, F1 1.0, over-merge 0.0, fragmentation 0.0, contamination 0.0
