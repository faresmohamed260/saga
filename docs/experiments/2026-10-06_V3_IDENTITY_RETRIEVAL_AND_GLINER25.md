# 2026-10-06 — V3 Identity Retrieval and GLiNER2.5 Qualification

Status: **MEASURED — hybrid retrieval supported; GLiNER2.5 supported as a character-seed lexer challenger; Ettin rejected as a universal reranker; no canonical merge policy adopted**

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

- With the single label `person`, GLiNER2.5 behaves primarily as a **proper-name / explicit entity seeder**.
- Pronoun recall is effectively zero and nominal recall is very low under that label design.
- Raising the threshold improves precision substantially while preserving a still-useful fraction of proper-name recall.
- A follow-up label-prompt experiment is required before concluding that GLiNER2.5 itself cannot recover nominal/pronominal references; the current result is specific to the measured label configuration.

The current supported architecture remains:

`explicit entity seeding` → `mention/reference detection` → `hybrid lexical + discourse candidate retrieval` → `mention-kind-aware ranking` → `conservative merge / abstain policy`

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

The original broad-context 10-document CPU probe proved too slow to be a useful first decision surface. A bounded compact-context probe therefore measured the model on two LitBank documents using:

- hybrid top-4 candidates (`lexical_k=2`, `recent_k=2`)
- target context radius: `128` characters
- one representative prior entity context
- cross-encoder batch size: `8`
- CPU only

Workflow run: `37471995815`

Artifact:

- ID: `11416579306`
- digest: `sha256:ef9d9487da82ed76b1ece76c0d7cd851825ce655c1184d97c635321794d298c3`
- qualification head: `b8d3da637aea2f9a33c34f0958333bb3ba34dc98`

Overall:

- eligible mentions: `215`
- candidate pairs scored: `472`
- candidate retrieval: `0.9256`
- candidate-order top-1: `0.6279`
- candidate-order MRR: `0.7682`
- Ettin top-1 end-to-end: `0.5721`
- Ettin MRR end-to-end: `0.7326`
- Ettin top-1 conditional on true candidate being available: `0.6181`
- Ettin MRR conditional: `0.7915`
- wall time: `56.51 s`
- peak process-tree RSS: about `949 MiB`

### By mention kind

**Pronouns (`123` eligible)**

- candidate top-1: `0.6992`
- candidate MRR: `0.8184`
- Ettin top-1 end-to-end: **`0.7236`**
- Ettin MRR end-to-end: **`0.8415`**
- Ettin conditional top-1: `0.7542`
- Ettin conditional MRR: `0.8771`

Result: **positive challenger signal**. Ettin improved both top-1 and MRR for pronouns on this bounded sample.

**Nominals (`29` eligible)**

- candidate top-1: `0.4138`
- candidate MRR: `0.5287`
- Ettin top-1 end-to-end: `0.4138`
- Ettin MRR end-to-end: `0.5345`
- Ettin conditional top-1: `0.6316`
- Ettin conditional MRR: `0.8158`

Result: **mixed / insufficient evidence**. Top-1 was unchanged and MRR improved slightly; the sample is too small for adoption.

**Repeat proper names (`63` eligible)**

- candidate top-1: `0.5873`
- candidate MRR: `0.7804`
- Ettin top-1 end-to-end: **`0.3492`**
- Ettin MRR end-to-end: **`0.6111`**
- Ettin conditional top-1: `0.3548`
- Ettin conditional MRR: `0.6210`

Result: **strong negative evidence**. The generic relevance reranker substantially damaged proper-name ordering.

### Ettin conclusion

Ettin is **rejected as a universal identity reranker** in the measured configuration. The result supports a mention-kind-aware ranking policy instead:

- repeat proper names / aliases: deterministic lexical or alias-first ordering should remain authoritative unless a future challenger beats it;
- pronouns: Ettin remains a credible reranking challenger and deserves a larger isolated benchmark;
- nominals: unresolved; gather more evidence before routing to Ettin;
- no Ettin score is a merge probability or merge threshold.

The throughput result also matters: `472` candidate pairs over `215` mentions took `56.51 s` on the hosted CPU runner even with compact context. Any eventual production use should batch across targets and/or use GPU inference rather than treating this CPU path as acceptable latency.

## Current V3 decision

Supported now:

- keep the model-independent identity scoring/candidate contracts;
- keep hybrid lexical + discourse-recency top-k retrieval as the leading measured candidate generator;
- keep GLiNER2.5 as an explicit-character/entity seeding challenger while label design is calibrated separately;
- make identity ranking **mention-kind-aware**, rather than applying one learned scorer to every mention;
- keep deterministic lexical/alias evidence ahead of Ettin for repeat proper names;
- continue Ettin qualification only for pronouns and, separately, nominals;
- keep heavy model dependencies outside normal CI;
- keep merge thresholds and production identity policy unset until ranking + abstention evidence exists.

Not supported now:

- lexical-only retrieval for general coreference;
- GLiNER2.5 as a one-model solution for proper names + nominals + pronouns based on the current `person` label experiment;
- exact-surface linking as a production linker;
- Ettin as a universal identity reranker;
- any learned reranker score being interpreted directly as merge probability;
- any canonical merge threshold chosen from these experiments alone.
