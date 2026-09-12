# 2026-09-12 — Character Identity Challenger: GLiNER Small v2.1 + F-Coref

Status: **CANDIDATE — experiment not yet qualified**

This challenger is intentionally decomposed so S.A.G.A. can distinguish mention/type failures from coreference failures instead of judging only a combined score.

## Pinned components

### GLiNER

- code: `urchade/GLiNER`
- code commit: `cf9e5f7d9fb99158b592132a9ec7cbfabb43a9a0`
- model: `urchade/gliner_small-v2.1`
- model revision: `f23104c107e3c57f5c7aa36d53a9667c67b4b866`
- model size at published revision: approximately 611 MB
- code/model license: Apache-2.0

### F-Coref

- code: `Digital-Insight-Technologies-Ltd/fastcoref`
- code commit: `8888e51d97d4818a25dd5f5d8b541d397fad9362`
- package version at commit: `2.1.6`
- model: `biu-nlp/f-coref`
- model revision: `d5a382c8bfe1105cee1a73007525ee08ab693d9a`
- safetensors artifact at that revision: `362,125,440` bytes
- code/model license: MIT

These exact revisions participate in experiment provenance. A later upstream release is a different candidate configuration and must not silently replace this result.

## Experiment decomposition

### 1. GLiNER typed-span quality

GLiNER is evaluated directly against the same pinned LitBank mention spans used by the identity harness.

Report separately:

- person-span precision/recall;
- proper-person span precision/recall;
- typed-span precision/recall.

This answers whether the front door admits the right person evidence before coreference is involved.

### 2. F-Coref with oracle mentions

LitBank's gold mention boundaries and person/non-person typing are retained, but gold coreference cluster IDs are replaced by F-Coref cluster evidence.

The resulting evidence is passed through the unchanged S.A.G.A. resolver and scored with the normal identity metrics.

This isolates clustering/attachment quality from mention detection. A poor result here means improving NER alone cannot fix the candidate.

### 3. Fully real GLiNER + F-Coref stack

The combined candidate uses real GLiNER spans and real F-Coref clusters.

Safety rule:

- GLiNER person spans may become strong evidence only when S.A.G.A.'s conservative lexical admission classifies the span as a proper name;
- F-Coref-only mentions may attach to a cluster only when that cluster has a GLiNER person anchor;
- **F-Coref-only evidence is always supporting evidence and cannot mint a canonical character**;
- non-person GLiNER evidence remains explicitly non-person;
- provider clusters do not bypass S.A.G.A. canonical admission or merge policy.

This is deliberate. The experiment measures whether coreference recall can improve attachment without recreating BookNLP-style canonical contamination.

## Fixed configuration

Initial smoke configuration:

- CPU-only PyTorch `2.3.1`;
- Transformers `4.51.3`;
- Python `3.10`;
- GLiNER labels: `person`, `location`, `geopolitical entity`, `facility`, `organization`, `vehicle`;
- GLiNER threshold: `0.5`;
- deterministic GLiNER character window: `1400` code points with `180` overlap;
- F-Coref max tokens per batch: `3500`;
- first 5 sorted pinned LitBank documents.

The chunking/threshold/label set are configuration, not hidden tuning. Any change after seeing results becomes a separately recorded experiment.

## Environment qualification attempts

### Attempt 1 — initial pinned environment

GitHub Actions run: `34704189734`

Result: **FAILED before model inference**.

Both pinned code packages installed successfully, but importing `fastcoref` reached spaCy and failed because the bounded environment did not contain `click`:

```text
ModuleNotFoundError: No module named 'click'
```

Classification: benchmark-environment configuration failure. No model-quality evidence was produced. The next attempt added only `click==8.1.7`; model revisions, labels, threshold, chunking and S.A.G.A. identity policy were unchanged.

### Attempt 2 — Click pinned

GitHub Actions run: `34704312565`
S.A.G.A. head: `602c37418ff79cc2239f12c23f43f7f802132207`

Result: **FAILED during GLiNER tokenizer initialization before document inference**.

The run progressed further than Attempt 1:

- GLiNER `0.2.29` installed from the exact pinned code commit;
- fastcoref `2.1.6` installed from the exact pinned code commit;
- `click==8.1.7` resolved correctly;
- both pinned Hugging Face model snapshots downloaded;
- GLiNER began loading `UniEncoderSpanGLiNER`.

Transformers' DeBERTa-v2 tokenizer conversion then failed because the bounded environment did not contain the protobuf runtime:

```text
ImportError: DebertaV2Converter requires the protobuf library but it was not found in your environment.
```

Classification: benchmark-environment configuration failure. No document was processed and no quality metric was produced.

The next attempt pins `protobuf==5.29.6`, a maintained non-yanked 5.29.x release compatible with Python 3.10, and changes nothing about the candidate model/configuration or S.A.G.A. resolver policy.

## Promotion sequence

1. five-document environment/offset/quality smoke;
2. full 100-document LitBank run if the smoke is technically valid;
3. all 17 novel-diversity strata;
4. second identical full run for repeatability;
5. complete-novel stress suite for candidates that remain viable;
6. private contemporary-fiction stress suite before final production adoption.

A bad component may be rejected or narrowed without rejecting the other component. For example, GLiNER may remain useful for typed entities even if F-Coref clustering loses, or F-Coref may remain an attachment candidate paired with another mention detector.

## Comparison target

BookNLP-small full LitBank currently provides the first real baseline:

- canonical precision `0.4613`;
- canonical recall `0.6030`;
- incorrect merge `0.1934`;
- contamination `0.4000`;
- fragmentation `0.4607`;
- linked mention precision `0.2158`;
- linked mention recall `0.1161`.

The oracle-evidence S.A.G.A. policy baseline remains the upper-bound diagnostic, not a provider competitor.

No challenger is adopted merely for beating BookNLP. It must reach a production-acceptable failure profile across novel types and complete books.
