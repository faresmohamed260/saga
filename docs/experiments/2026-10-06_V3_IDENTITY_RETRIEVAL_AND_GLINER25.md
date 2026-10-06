# 2026-10-06 — V3 Identity Retrieval and GLiNER2.5 Qualification

Status: **MEASURED — hybrid retrieval supported; GLiNER2.5 supported only as a character-seed lexer challenger; no canonical merge policy adopted**

This record preserves the first V3.0 public measurements that separate three different questions which must not be conflated:

1. can the semantic lexer detect useful character mentions?
2. can candidate generation retrieve the already-established character?
3. can a learned scorer rank the retrieved candidates correctly?

The experiments below do **not** authorize a production merge threshold. Gold identity history is used only in the isolated ranking harness to prevent earlier mistakes from cascading into later measurements.

## Fixed corpus

LitBank:

- repository: `dbamman/litbank`
- commit: `3e50db0ffc033d7ccbb94f4d88f6b99210328ed8`
- annotation layer: `coref/tsv`
- license: CC BY 4.0

## Candidate retrieval — full 100-document LitBank

Workflow run: `37467363832`

Artifact:

- ID: `11415706973`
- digest: `sha256:7ddfccca81ab47598862066fd557c04f9699df0797833b87f04b5391b6c651cd`
- S.A.G.A. head: `3c1357c4765de4cf9cb231b912a756545c4d1cc5`

The benchmark evaluates only mentions whose gold character already has a prior proper-name seed. The target gold ID is never passed to candidate generation.

### Lexical-only top-8

- eligible mentions: `11,737`
- non-empty candidate rate: `0.3915`
- true-character retrieval rate: `0.2582`
- recall@1: `0.2223`
- recall@3: `0.2522`
- recall@5: `0.2580`
- MRR: `0.2374`
- pronoun retrieval: `0.1142`
- nominal retrieval: `0.1204`
- repeat proper-name retrieval: `0.9774`
- benchmark wall time: `1.21 s`
- peak process-tree RSS: about `37 MiB`

Conclusion: lexical overlap is an adequate repeat-name baseline but is not a usable literary coreference candidate generator.

### Hybrid lexical + recent-discourse top-8

Configuration: lexical top-4 + recent-discourse top-4, deduplicated to at most eight candidates.

- eligible mentions: `11,737`
- non-empty candidate rate: `1.0000`
- true-character retrieval rate: **`0.9928`**
- recall@1: `0.6923`
- recall@3: `0.9404`
- recall@5: **`0.9855`**
- MRR: `0.8181`
- pronoun retrieval: **`0.9962`**
- nominal retrieval: **`0.9521`**
- repeat proper-name retrieval: **`0.9985`**
- benchmark wall time: `1.95 s`
- peak process-tree RSS: about `37 MiB`

Conclusion: **candidate coverage is no longer the primary identity bottleneck** in this oracle-history isolation. The next measured problem is ranking the small retrieved set and then calibrating a conservative merge/abstain policy.

## GLiNER2.5 semantic lexer — full 100-document downstream identity diagnostic

Model pin:

- model: `fastino/gliner2.5-base-v1`
- revision: `ca906247640776a07753514055be9726f9080ead`
- package: `gliner2==2.0.0`
- license metadata: Apache-2.0
- role: semantic-lexer challenger

Workflow run: `37467252992`

Artifact:

- ID: `11414809558`
- digest: `sha256:d70fc2e9fe218c9141c97ca78b660b0ee2a8b2b894e8a6dda314ef4b771c789c`
- S.A.G.A. qualification head: `41d1bb6fa89f491fa8f6155388796659f0d4c433`

Environment notes:

- CPU-only PyTorch
- `transformers==4.57.6`
- `sentencepiece==0.2.1`
- `protobuf==6.33.0`
- GLiNER model loaded successfully with DeBERTa eager-attention fallback

Configuration:

- GLiNER threshold: `0.5`
- linker: deliberately weak exact-normalized-surface reference linker
- documents: `100`

Measured downstream identity metrics:

- canonical precision: `0.3814`
- canonical recall: `0.7185`
- false-canonical rate: `0.5334`
- incorrect-merge rate: **`0.0087`**
- fragmentation rate: `0.3259`
- linked-mention precision: `0.3874`
- linked-mention recall: `0.1111`
- cluster purity: **`0.9910`**
- predicted mentions: `10,933`
- predicted canonicals: `1,961`
- represented gold characters: `485 / 675`
- wall time: `512.76 s`
- peak process-tree RSS: about `2.10 GiB`

Interpretation:

- GLiNER2.5 produces **much cleaner merge behavior and cluster purity than the frozen BookNLP-small identity candidate** in this diagnostic.
- The high false-canonical rate and low linked-mention recall make `threshold=0.5 + exact-surface linking` unsuitable as a complete identity system.
- This run is primarily evidence about the lexer + weak-linker combination; it must not be read as a rejection of GLiNER or as proof that exact-surface linking is adequate.

## Direct GLiNER character-mention calibration — 10 documents

A separate direct benchmark scores the lexer on exact character-span detection and excludes identity clustering. The same loaded model is reused, but each threshold performs a real extraction pass because threshold-sensitive decoding must be measured rather than assumed equivalent to post-hoc filtering.

Workflow run: `37469350815`

Artifact:

- ID: `11417145639`
- digest: `sha256:d573fecbf69feca23821e2b7f0e82be751f72ea9a8574788674b779eb913048f`
- qualification head: `5814f9f0126c47123974a9fd5ba8f5b41dbbc198`

| Threshold | Precision | Recall | F1 | Proper-name recall | Nominal recall | Pronoun recall |
|---:|---:|---:|---:|---:|---:|---:|
| 0.30 | 0.4384 | 0.0911 | 0.1509 | 0.6761 | 0.0606 | 0.0021 |
| 0.50 | 0.4751 | 0.0868 | 0.1467 | 0.6761 | 0.0485 | 0.0007 |
| 0.65 | 0.5207 | 0.0820 | 0.1417 | 0.6640 | 0.0364 | 0.0007 |
| 0.75 | 0.5931 | 0.0746 | 0.1326 | 0.6275 | 0.0242 | 0.0007 |
| 0.85 | **0.6723** | 0.0694 | 0.1258 | 0.5992 | 0.0167 | 0.0007 |

Direct-lexer conclusion:

- GLiNER2.5 is **not a complete literary mention detector** in this configuration.
- It behaves primarily as a **proper-name / explicit entity seeder**.
- Pronoun recall is effectively zero; nominal recall is very low.
- Raising the threshold improves precision substantially while preserving a still-useful fraction of proper-name recall.

Therefore the current supported architecture is:

`GLiNER / explicit entity seeding` → `separate pronoun + nominal mention detection` → `hybrid lexical + discourse candidate retrieval` → `learned or deterministic ranking` → `conservative merge / abstain policy`

GLiNER should not be asked to solve pronoun or nominal coreference by itself.

## Comparison with frozen BookNLP-small identity candidate

The existing full LitBank BookNLP-small record reports:

- canonical precision: `0.4613`
- canonical recall: `0.6030`
- incorrect-merge rate: `0.1934`
- fragmentation rate: `0.4607`
- linked-mention precision: `0.2158`
- linked-mention recall: `0.1161`
- cluster purity: `0.8667`
- wall time: `420.21 s`
- peak RAM: `1,164.5 MiB`

GLiNER2.5 at threshold 0.5 is heavier on CPU/RAM and has lower canonical precision in the weak-linker diagnostic, but it is dramatically cleaner on incorrect merges and cluster purity while representing more gold characters. This supports keeping GLiNER as a V3 semantic-lexer challenger, not adopting it as a standalone identity provider.

## Ettin reranker

Model pin:

- model: `cross-encoder/ettin-reranker-68m-v1`
- revision: `d166fa88ddde3c42bc3ee92f7df476d941c8204a`
- package: `sentence-transformers==6.1.0`
- role: identity-score challenger

A separate 10-document CPU probe is measuring whether this generic relevance reranker improves ordering of the hybrid top-8 candidate set. The adapter batches candidate pairs and its score is treated only as experimental ranking evidence, not a calibrated coreference probability.

**Status at this record revision: probe still running; no adoption claim.**

## Current V3 decision

Supported now:

- keep the model-independent identity scoring/candidate contracts;
- keep hybrid lexical + discourse-recency top-k retrieval as the leading measured candidate generator;
- keep GLiNER2.5 as an explicit-character/entity seeding challenger;
- keep heavy model dependencies outside normal CI;
- keep merge thresholds and production identity policy unset until ranking + abstention evidence exists.

Not supported now:

- lexical-only retrieval for general coreference;
- GLiNER2.5 as a one-model solution for proper names + nominals + pronouns;
- exact-surface linking as a production linker;
- any learned reranker score being interpreted directly as merge probability;
- any canonical merge threshold chosen from these experiments alone.
