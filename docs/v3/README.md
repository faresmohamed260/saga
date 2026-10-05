# S.A.G.A. v3 Reboot Preparation

Status: **READY TO BEGIN V3 IMPLEMENTATION PROTOTYPE**

Preparation branch: `v3/reboot-preparation`

Frozen v2 baseline: `archive/v2-analysis-baseline-2026-10-05`

Baseline commit: `e9d24d54d351f9bf7c1cfa582a01db819efdb2fe`

## Purpose

This directory is the reboot contract for S.A.G.A.'s textual narrative-analysis engine. It separates preparation/architecture decisions from implementation so the project does not repeat the v2 provider-driven design under newer model names.

## Reboot gates

The minimum gates defined before implementation are now present:

- [x] frozen v2 baseline — `BASELINE.md`
- [x] current-system inventory — `SYSTEM_INVENTORY.md`
- [x] keep/replace/benchmark matrix — `SYSTEM_INVENTORY.md`
- [x] Narrative IR v0 — `NARRATIVE_IR.md`
- [x] semantic ontology boundaries — `ONTOLOGY.md`
- [x] canonical Postgres/Supabase persistence draft — `DATABASE_SCHEMA.md`
- [x] gold-corpus/evaluation contract — `EVALUATION.md`
- [x] v2-v3 comparison/promotion gates — `EVALUATION.md`
- [x] target architecture ADR — `adr/0001-narrative-compiler.md`

Additional preparation completed:

- [x] target architecture — `ARCHITECTURE.md`
- [x] pipeline DAG/invalidation model — `PIPELINE_DAG.md`
- [x] model strategy — `MODEL_STRATEGY.md`
- [x] initial license ledger — `MODEL_LICENSES.md`
- [x] provenance/artifact specification — `PROVENANCE_SPEC.md`
- [x] shadow migration strategy — `MIGRATION_V2_TO_V3.md`

## What is preserved from v2

- source normalization and fingerprints;
- exact evidence offsets;
- deterministic source/chapter structure;
- deterministic quote-boundary implementation while it remains the benchmark leader;
- durable Supabase jobs/leases/runs;
- immutable provenance;
- explicit unresolved state;
- precision-first canonicalization principle;
- existing evaluation/benchmark assets;
- application auth/storage boundaries.

## What is being rebooted

- provider-shaped semantic evidence contracts;
- BookNLP-centered identity architecture;
- global identity/event linking;
- scene/speaker/event semantic models where challengers win;
- event/state/relationship representation;
- timeline and causality as global reasoning layers;
- canonical graph persistence assumptions;
- generic LLM extraction as semantic glue.

## First implementation milestone: V3.0

Do **not** start with timeline, causality or a large generative model.

V3.0 is:

```text
SOURCE COMPILER
      -> SEMANTIC LEXER
      -> GLOBAL CHARACTER LINKER
      -> NARRATIVE IR
      -> V2/V3 BENCHMARK REPORT
```

Required V3.0 deliverables:

1. Python-native compiler package/runtime skeleton.
2. Narrative IR typed models matching `NARRATIVE_IR.md`.
3. content-addressed stage/artifact fingerprint implementation.
4. adapter over existing normalized source compiler.
5. semantic-lexer benchmark interface.
6. first GLiNER2-class lexer challenger.
7. linker candidate-generation interface.
8. first Ettin-class linker/scorer challenger.
9. v2 adapter producing comparable identity/entity output.
10. top-level v2/v3 benchmark report for the selected corpus.

## V3.0 success gate

V3.0 is not promoted merely because the new models look better on examples.

It must demonstrate:

- complete evidence/provenance linkage;
- lower false-canonical / wrong-merge behavior than the frozen v2 identity path;
- competitive or improved useful coverage;
- acceptable whole-document runtime and memory;
- explicit unresolved behavior;
- no production-incompatible model license;
- reproducible stage/config/model fingerprints.

## Deferred until later milestones

### V3.1

Dialogue + speaker attribution.

### V3.2

Scene segmentation.

### V3.3

Event mentions, participants and event coreference.

### V3.4

Attributes, relationship observations and state deltas.

### V3.5

Story-world temporal constraints and solver.

### V3.6

Causal candidate generation/scoring.

### V3.7

Derived graph/retrieval/summaries/arcs/generation.

## Preparation caveats still open

These are not blockers for starting the prototype, but they are blockers for production promotion:

- exact model checkpoint/revision pinning and final license audit;
- private modern-fiction gold suite availability in the execution environment;
- exact physical SQL schema/index design after prototype cardinalities are measured;
- final event-role ontology depth;
- narrator/character belief and dream/hypothetical epistemic scopes;
- exact series-level entity-promotion policy;
- whether `Proposition` remains a first-class persisted object or is compiled into typed observations.

## Governing rule

> S.A.G.A. models produce evidence. S.A.G.A. owns identity, consistency, provenance and canon.
