# 2026-10-06 — V3 Ettin Pronoun-Only Identity Routing

Status: **MEASURED — mention-kind routing supported; Ettin retained only as a pronoun reranking challenger**

This experiment tests the routing decision produced by the earlier universal Ettin probe. The universal configuration improved pronouns but damaged repeat proper names, so V3 now evaluates a policy that invokes Ettin only for pronouns and preserves deterministic candidate-generator order for every other mention kind.

## Fixed basis

LitBank:

- repository: `dbamman/litbank`
- commit: `3e50db0ffc033d7ccbb94f4d88f6b99210328ed8`
- annotation layer: `coref/tsv`
- license: CC BY 4.0
- documents in bounded probe: first `2`

Ettin:

- model: `cross-encoder/ettin-reranker-68m-v1`
- revision: `d166fa88ddde3c42bc3ee92f7df476d941c8204a`
- role: experimental pronoun identity reranker

Candidate layer:

- hybrid lexical + discourse-recency
- `top_k=4`
- `lexical_k=2`
- `recent_k=2`

Scorer configuration:

- target context radius: `128` characters
- representative entity contexts: `1`
- cross-encoder batch size: `8`
- device: CPU
- scorer routing: `pronoun` only

## Provenance

Workflow run: `37473678820`

Artifact:

- ID: `11418380891`
- digest: `sha256:1d3725d4ceb828342fd1effd2866061510410f7940dd8c319ab0a0b2554c6c56`
- qualification head: `44c0b88213c40d9d48d453bad22cfdbd5172efe5`

## Overall result

Eligible post-seed mentions: `215`.

| Metric | Candidate order | Pronoun-routed policy |
|---|---:|---:|
| Top-1 end-to-end | 0.6279 | **0.6419** |
| Recall@3 end-to-end | 0.9256 | 0.9256 |
| Recall@5 end-to-end | 0.9256 | 0.9256 |
| MRR end-to-end | 0.7682 | **0.7814** |

Routing footprint:

- scorer execution rate: `0.5721`
- pronoun targets scored: `123 / 215`
- candidate pairs scored: `244`
- wall time: `17.74 s`
- peak process-tree RSS: about `948 MiB`

The earlier universal compact probe scored `472` candidate pairs, took `56.51 s`, and produced worse overall top-1/MRR than the candidate order. Pronoun-only routing therefore removes the known proper-name regression while cutting model work roughly in half.

## By mention kind

### Pronouns

Eligible: `123`.

- candidate retrieval: `0.9593`
- candidate top-1: `0.6992`
- candidate MRR: `0.8184`
- Ettin/routed top-1: **`0.7236`**
- Ettin/routed MRR: **`0.8415`**
- conditional Ettin top-1 when the true candidate is available: `0.7542`
- conditional Ettin MRR: `0.8771`

Result: **positive challenger evidence**. Ettin improves both top-1 and MRR for pronouns on the bounded sample.

### Nominals

Eligible: `29`.

Ettin is not invoked. The policy preserves candidate ordering exactly:

- top-1: `0.4138`
- MRR: `0.5287`

Result: **no change by design**. Nominals remain an unresolved ranking problem and need their own larger experiment.

### Repeat proper names

Eligible: `63`.

Ettin is not invoked. The policy preserves candidate ordering exactly:

- top-1: `0.5873`
- MRR: `0.7804`

This removes the severe proper-name regression observed when universal Ettin reranking reduced top-1 to `0.3492` and MRR to `0.6111`.

## Architectural decision

The evidence supports a mention-kind-aware ranking boundary:

- **proper names / aliases:** preserve deterministic lexical/alias-first candidate order unless a future task-specific challenger beats it;
- **pronouns:** Ettin remains a measured reranking challenger;
- **nominals:** preserve current candidate order pending dedicated evidence;
- **merge policy:** remains separate. Ettin scores are relevance scores, not calibrated coreference probabilities.

The V3 benchmark therefore reports three independent views:

1. candidate retrieval/order;
2. raw learned-scorer behavior only on cases where it executes;
3. final routed-policy ordering across all eligible mentions.

This routing contract is supported for continued V3 development. It does **not** establish a production merge threshold or authorize automatic canonical merges.
