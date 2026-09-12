# Phase 3A — BookNLP Small Primary-Identity Decision

Date: 2026-09-12
Status: **CLOSED FOR PRIMARY CHARACTER IDENTITY — NOT ADOPTED**

## Scope

This record closes only the question of whether the measured BookNLP `small` configuration should become S.A.G.A.'s primary character-identity evidence provider.

It does **not** reject BookNLP's quote/speaker, literary-event, syntax, or auxiliary mention capabilities. Those remain independent task-specific candidates.

## Pinned experiment

- LitBank: `dbamman/litbank@3e50db0ffc033d7ccbb94f4d88f6b99210328ed8`
- BookNLP base: `booknlp/booknlp@3d900fc2224e55960c3363826ae28539b77b4204`
- compatibility head: `8875a1b616d764b7d13d1e30e9949cc21ca303c1`
- model: `small`
- CPU-only PyTorch `2.3.1`
- spaCy `3.7.5`
- Transformers `4.43.4`
- TensorFlow absent

## Full-corpus quality

All 100 pinned LitBank documents completed. Aggregate identity quality after BookNLP evidence passed through S.A.G.A.'s unchanged deterministic resolver:

- canonical precision: `0.4613`
- canonical recall: `0.6030`
- false-canonical rate: `0.2642`
- incorrect-merge rate: `0.1934`
- contaminated-canonical rate: `0.4000`
- fragmentation rate: `0.4607`
- linked-mention precision: `0.2158`
- linked-mention recall: `0.1161`
- non-person quarantine rate: `0.9415`
- cluster purity: `0.8667`

Semantic fingerprint:

`01e78b6b539fbe0e8529e38bb61b1d17fb7734126218b507cb1da5014d3d0413`

## Repeatability

Two independent complete 100-document runs produced the **same semantic fingerprint and the same quality counts/metrics**.

First full run:

- run `34700149009`
- artifact `10299538833`
- artifact digest `sha256:5f2f7110244226a27b3d3de32b3064f3086a1e8f93cc82d7dcf962f3ec4a0838`
- wall clock `420.21 s`
- peak RSS `1,164.5 MiB`

Repeatability/diversity run:

- run `34703727551`
- artifact `10300692320`
- artifact digest `sha256:487ee2d7d36b49456d6191bab904cdd5a2a7c5291ad6923714cb840d08cea7b9`
- wall clock approximately `352.2 s`
- same semantic fingerprint as the first full run

Runtime variance therefore did not change semantic output.

## Novel-diversity result

The failure profile is not confined to one unusual subset. The merged stratified evaluator shows material weakness across different novel types and narrative stressors. Examples include:

- western/frontier: incorrect-merge rate approximately `0.3571`, canonical recall approximately `0.3750`;
- speculative/science-fiction: canonical precision approximately `0.3182`;
- children/youth: linked-mention precision approximately `0.0450`.

The complete machine-readable strata and policy live in:

- `services/analysis-worker/benchmarks/litbank-novel-diversity.v1.json`
- `docs/experiments/NOVEL_DIVERSITY_MATRIX.md`

## Resource profile

The measured operational footprint is attractive for a local CPU baseline:

- approximately `153 MiB` BookNLP model artifacts;
- no GPU required;
- approximately `1.16 GiB` peak RSS on the first full run;
- a few minutes for the 100 LitBank excerpts once the environment is pinned.

Resource efficiency does not outweigh the measured identity error profile.

## Decision

BookNLP-small is **not adopted as S.A.G.A.'s primary character-identity provider**.

Reasons:

1. canonical precision is too low for a canon-preserving identity layer;
2. incorrect cross-character merges remain substantial;
3. canonical contamination remains substantial;
4. fragmentation remains high at the same time, so the configuration is not merely trading recall for precision;
5. linked-mention precision/recall are too weak for downstream event, relationship, timeline, and canon reasoning;
6. the weakness repeats deterministically and appears across multiple novel strata;
7. the official model-weight license remains unverified by S.A.G.A.

The decision is based on measured downstream behavior, not on provider reputation or published benchmark scores.

## What remains open

BookNLP may still be benchmarked independently for:

- quote span / speaker attribution;
- literary event triggers;
- syntax and supersense evidence;
- auxiliary mention evidence that cannot mint or merge canonical identities.

Those roles require their own gold/task metrics and must not inherit primary-identity acceptance from this experiment.

## Next comparison

Phase 3A continues with decomposed local challengers, beginning with GLiNER typed spans and F-Coref cluster attachment. Any challenger must use the same S.A.G.A. resolver/evaluation contracts, novel-diversity gate, repeatability requirement, complete-book stress tests, and later contemporary/private fiction coverage before production adoption.
