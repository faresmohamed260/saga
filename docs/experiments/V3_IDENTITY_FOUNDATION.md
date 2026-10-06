# V3.0 Identity Foundation — Public Qualification

Status: **ACTIVE DIAGNOSTIC — hybrid retrieval supported; learned scorer and lexer calibration still under qualification**

This record tracks the first public Phase V3.0 measurements for semantic character mentions, identity candidate retrieval, and reranking. None of these public LitBank results alone promote a component into production; protected modern-fiction qualification remains required.

## Fixed public comparison basis

LitBank:

- repository: `dbamman/litbank`
- commit: `3e50db0ffc033d7ccbb94f4d88f6b99210328ed8`
- annotation layer: `coref/tsv`
- license: CC BY 4.0
- full public suite: 100 documents

Frozen V2 BookNLP-small identity baseline:

- canonical precision: `0.4613`
- canonical recall: `0.6030`
- incorrect-merge rate: `0.1934`
- fragmentation rate: `0.4607`
- linked-mention precision: `0.2158`
- linked-mention recall: `0.1161`
- cluster purity: `0.8667`

The V2 baseline remains comparison evidence, not the V3 architecture.

## Experiment A — identity candidate retrieval

Run: `37467363832`

S.A.G.A. experiment head: `3c1357c4765de4cf9cb231b912a756545c4d1cc5`

Artifact:

- ID: `11415706973`
- digest: `sha256:7ddfccca81ab47598862066fd557c04f9699df0797833b87f04b5391b6c651cd`

Method:

- maintain oracle-correct prior character clusters only for benchmark isolation;
- do **not** expose the target mention's gold character ID to retrieval;
- begin evaluating a character only after its first prior proper-name seed;
- evaluate the same `11,737` eligible post-seed mentions for both generators;
- no canonical merge decision is made in this benchmark.

### Lexical-only top-8

Overall:

- non-empty candidate-set rate: `0.3915`
- true-character retrieval rate: `0.2582`
- recall@1: `0.2223`
- recall@3: `0.2522`
- recall@5: `0.2580`
- MRR: `0.2374`
- wall time: `1.21 s`
- peak process-tree RSS: `39,051,264 bytes`

Retrieval by mention kind:

- proper name: `0.9774`
- nominal: `0.1204`
- pronoun: `0.1142`

Conclusion: lexical matching is a useful proper-name feature but is not an adequate global candidate generator for literary identity.

### Hybrid lexical + recent-discourse top-8

Configuration:

- lexical candidates: up to 4;
- recent-discourse candidates: up to 4;
- total candidate cap: 8.

Overall:

- non-empty candidate-set rate: `1.0000`
- true-character retrieval rate: `0.9928`
- recall@1: `0.6923`
- recall@3: `0.9404`
- recall@5: `0.9855`
- MRR: `0.8181`
- wall time: `1.95 s`
- peak process-tree RSS: `39,055,360 bytes`

Retrieval by mention kind:

| Mention kind | Retrieval | Recall@1 | Recall@3 | Recall@5 | MRR |
|---|---:|---:|---:|---:|---:|
| proper name | `0.9985` | `0.9626` | `0.9954` | `0.9985` | `0.9786` |
| nominal | `0.9521` | `0.4061` | `0.8699` | `0.9501` | `0.6317` |
| pronoun | `0.9962` | `0.6654` | `0.9363` | `0.9868` | `0.8041` |

### Retrieval conclusion

**Supported as the V3.0 benchmark candidate-generation baseline.**

This does not mean the true entity is known in production. It means that, given correct prior cluster history on the public diagnostic, a cheap deterministic top-8 union of lexical and recent-discourse candidates almost always contains the true established character. This makes downstream learned reranking tractable without comparing every mention to every book-global entity.

The result also establishes an important architectural separation: candidate retrieval can optimize recall while canonical merge policy remains independently precision-gated.

## Experiment B — GLiNER2.5 semantic lexer + exact-surface identity floor

Run: `37467252992`

S.A.G.A. experiment head: `41d1bb6fa89f491fa8f6155388796659f0d4c433`

Workflow artifact:

- ID: `11414809558`
- digest: `sha256:d70fc2e9fe218c9141c97ca78b660b0ee2a8b2b894e8a6dda314ef4b771c789c`

Candidate provenance:

- model: `fastino/gliner2.5-base-v1`
- model revision: `ca906247640776a07753514055be9726f9080ead`
- package: `gliner2==2.0.0`
- license: Apache-2.0
- resolved model files: `10`
- resolved model bytes: `784,259,224`
- aggregate model artifact SHA-256: `d648657917932f5f24f4bb36cdceb8f349cdd944afa72b984df2d10483a3891d`
- device: CPU
- confidence threshold: `0.5`

Qualification environment required separate GLiNER dependencies because GLiNER2 local inference currently pins Transformers `<5`; the successful environment used Transformers `4.57.6` plus explicit SentencePiece/protobuf tokenizer-fallback dependencies.

### Full 100-document result

- canonical precision: `0.3814`
- canonical recall: `0.7185`
- false-canonical rate: `0.5334`
- incorrect-merge rate: `0.0087`
- contaminated-canonical rate: `0.6135`
- fragmentation rate: `0.3259`
- linked-mention precision: `0.3874`
- linked-mention recall: `0.1111`
- cluster purity: `0.9910`
- wall time: `512.76 s`
- peak process-tree RSS: `2,257,235,968 bytes`
- GPU/VRAM: none

### Interpretation against frozen V2 BookNLP-small

GLiNER2.5 + the deliberately weak exact-surface linker is:

- lower canonical precision (`0.3814` vs `0.4613`);
- higher canonical recall (`0.7185` vs `0.6030`);
- dramatically lower incorrect merges (`0.0087` vs `0.1934`);
- lower fragmentation (`0.3259` vs `0.4607`);
- higher linked-mention precision (`0.3874` vs `0.2158`);
- approximately equal/slightly lower linked-mention recall (`0.1111` vs `0.1161`);
- much higher cluster purity (`0.9910` vs `0.8667`).

The high false-canonical/contamination rates mean this configuration is **not supported as a complete identity path**. The low merge contamination and high purity, however, support continued evaluation of GLiNER2.5 as a **semantic mention lexer feeding a stronger global linker**.

The exact-surface linker remains only a safety/reference floor. Its downstream identity metrics must not be used to claim that the GLiNER lexer itself has been fully evaluated.

## Experiment C — direct GLiNER mention calibration

Status: **RUNNING**.

A direct character-mention benchmark now measures exact-span precision/recall independently of identity clustering, including recall split by proper names, nominals, and pronouns. A 10-document threshold sweep evaluates `0.30 / 0.50 / 0.65 / 0.75 / 0.85` using one loaded pinned model while performing a real extraction pass at each threshold.

The purpose is to find a precision-first operating region before combining GLiNER evidence with the hybrid linker.

## Experiment D — Ettin learned reranker

Status: **RUNNING**.

Candidate:

- `cross-encoder/ettin-reranker-68m-v1`
- exact revision: `d166fa88ddde3c42bc3ee92f7df476d941c8204a`
- Apache-2.0

The first probe uses 10 LitBank documents and the hybrid top-8 candidate generator. Ettin receives the target mention/context plus deterministic representative contexts from each candidate cluster. Candidate pairs are scored in batches.

The raw reranker output is treated as **experimental relevance evidence, not a calibrated coreference probability**. No canonical merge threshold will be selected unless ranking quality first demonstrates value over the deterministic candidate ordering.

## Current V3.0 identity conclusion

1. Hybrid lexical + recent-discourse retrieval is supported as the first V3.0 candidate-generation baseline for further qualification.
2. GLiNER2.5 remains a viable semantic-lexer challenger because its full-corpus path shows strong purity/merge cleanliness, but threshold-level lexer precision must be measured directly before adoption.
3. Exact-surface identity remains only a deterministic safety floor.
4. Ettin is not adopted; its first ranking probe is still pending.
5. No merge threshold, canonical-production path, or protected-fiction promotion has been authorized from these public diagnostics.
