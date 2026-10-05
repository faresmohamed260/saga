# Phase V3.0 — Narrative Compiler Foundation

Status: **ACTIVE ON MERGE — IMPLEMENTATION CONTRACT**

This contract authorizes the first implementation phase of S.A.G.A. v3 after this document and the corresponding durable decisions are merged to `main`.

## 1. Goal

Build a model-independent, evidence-preserving narrative compiler foundation that can be benchmarked directly against the frozen v2 analysis baseline without changing production behavior.

V3.0 is intentionally narrow:

```text
SOURCE COMPILER
      -> SEMANTIC LEXER
      -> GLOBAL CHARACTER LINKER
      -> NARRATIVE IR
      -> V2/V3 BENCHMARK REPORT
```

The phase proves the new architecture around identity/entity evidence first. It does not attempt to finish scenes, speakers, events, state, chronology, causality, retrieval, or generation.

## 2. Governing architecture

The authoritative v3 design documents for this phase are:

- [`../v3/ARCHITECTURE.md`](../v3/ARCHITECTURE.md)
- [`../v3/NARRATIVE_IR.md`](../v3/NARRATIVE_IR.md)
- [`../v3/ONTOLOGY.md`](../v3/ONTOLOGY.md)
- [`../v3/PIPELINE_DAG.md`](../v3/PIPELINE_DAG.md)
- [`../v3/PROVENANCE_SPEC.md`](../v3/PROVENANCE_SPEC.md)
- [`../v3/EVALUATION.md`](../v3/EVALUATION.md)
- [`../v3/MODEL_STRATEGY.md`](../v3/MODEL_STRATEGY.md)
- [`../v3/MIGRATION_V2_TO_V3.md`](../v3/MIGRATION_V2_TO_V3.md)

The governing rule is:

> Models produce evidence. S.A.G.A. owns identity, consistency, provenance and canon.

## 3. Non-negotiable constraints

1. Required textual analysis remains local-first and subscription-free.
2. No paid AI API, hosted GPU subscription, or per-token service becomes part of the required path.
3. The existing Supabase durable job/lease/run control plane remains in place for V3.0.
4. Existing B2 source-object boundaries remain in place.
5. Source bytes, normalized source fingerprints, offsets and source structure remain immutable evidence roots.
6. Model/provider output never becomes canon merely because it was emitted by a model.
7. Explicit `unresolved` is valid output and is preferred over unsafe canonicalization.
8. Normal CI remains deterministic and model-light. Heavy model qualification is manual/dedicated.
9. Private copyrighted fiction must not be committed to Git or emitted into public CI/log artifacts.
10. Production behavior remains on v2 during V3.0. V3 runs in shadow/benchmark mode only.
11. Model/checkpoint adoption requires explicit license review and S.A.G.A.-owned benchmark evidence.
12. No v2 code is deleted merely because a v3 replacement exists; removal requires a later migration decision.

## 4. Accepted implementation scope

### 4.1 Python-native narrative compiler package

Create a new isolated Python package/service for semantic compiler code. It must not take ownership of browser/API authorization or Supabase job truth.

The package should own:

- typed Narrative IR structures;
- compiler-stage contracts;
- deterministic content/config/model fingerprints;
- source-compiler adaptation;
- semantic-lexer interfaces;
- identity candidate generation/scoring/resolution interfaces;
- v2/v3 benchmark normalization.

### 4.2 Narrative IR v0

Implement typed forms for the V3.0 subset of the IR, including at minimum:

- document/source identity;
- source units/spans;
- mentions;
- entity candidates/entities;
- evidence/provenance references;
- model/stage run metadata;
- acceptance state (`candidate`, `accepted`, `rejected`, `unresolved`).

Event/state/temporal/causal types may exist as forward-compatible schemas, but V3.0 must not claim those stages are implemented merely because types exist.

### 4.3 Content-addressed artifacts

Every compiler artifact must be reproducibly bound to:

- normalized source fingerprint;
- stage name/version;
- model/checkpoint revision when applicable;
- normalized configuration fingerprint;
- required upstream artifact fingerprints.

Changing a relevant input must change the artifact fingerprint. Re-running an identical stage over identical inputs must reproduce the fingerprint.

### 4.4 Source compiler adapter

Reuse the current normalized source/section semantics rather than creating a second normalization truth.

V3 must be able to prove that its source view is bound to the exact normalized input fingerprint used by the existing analysis system.

### 4.5 Semantic lexer contract

Define a model-independent contract that converts local text windows into typed candidate evidence such as:

- character/person mentions;
- locations/objects/organizations/factions where useful to the V3.0 comparison;
- span attributes and local relations when supported;
- exact source-span provenance;
- confidence/raw score;
- model/checkpoint/config metadata.

The first external challenger is a GLiNER2-class implementation, but the interface must not depend on GLiNER-specific output shapes.

### 4.6 Global character linker contract

Implement a book-global identity layer with separate components for:

1. candidate generation;
2. candidate scoring;
3. hard constraints;
4. merge/attach/unresolved policy.

The first learned scorer challenger is an Ettin-class cross-encoder/reranker if current package/checkpoint/license qualification remains acceptable. The architecture must allow replacing it without changing Narrative IR.

The linker may use lexical aliases, local coreference evidence, context representations and learned pair/cluster scores, but canonical identity decisions remain S.A.G.A.-owned.

### 4.7 V2 adapter

Create an adapter that projects frozen v2 identity/entity output into the same comparison contract used by v3.

The adapter must not alter v2 behavior or quietly repair its outputs.

### 4.8 Benchmark runner

Provide one top-level, reproducible V2-vs-V3 comparison path that reports at minimum:

- canonical precision/recall where gold exists;
- incorrect merge / false-canonical rate;
- fragmentation;
- mention attachment precision/recall;
- unresolved rate;
- supported coverage at the configured precision target;
- wall-clock runtime;
- peak RAM;
- peak VRAM when applicable;
- model/checkpoint/revision;
- artifact/config/source fingerprints;
- license classification.

## 5. Explicitly rejected or deferred in V3.0

The following are out of scope for this implementation phase:

- changing the production web/application data path to v3;
- deleting or rewriting the v2 analysis worker;
- making Neo4j canonical truth;
- production SQL migrations for the complete Narrative IR;
- production scene segmentation;
- production speaker attribution;
- full event/event-coreference implementation;
- persistent character/world state;
- story-world chronology/flashback resolution;
- causal graph inference;
- theme/arc/tension generation;
- whole-novel generative extraction as the primary analysis method;
- agentic/LangGraph control of deterministic compiler stages;
- required paid/cloud AI inference;
- automatic adoption of GLiNER2, Ettin, NuExtract, Qwen, BookNLP, xCoRe, Maverick, CorPipe, or any other named model based on external benchmarks alone.

## 6. Baseline that must remain reproducible

The frozen comparison branch is:

`archive/v2-analysis-baseline-2026-10-05`

Frozen baseline commit:

`e9d24d54d351f9bf7c1cfa582a01db819efdb2fe`

Important measured v2 evidence includes:

- BookNLP identity canonical precision `0.4613`;
- canonical recall `0.6030`;
- incorrect merge `0.1934`;
- fragmentation `0.4607`;
- linked-mention precision `0.2158`;
- linked-mention recall `0.1161`;
- deterministic quote F1 `0.8563`;
- BookNLP event-trigger F1 `0.7791`.

Detailed baseline evidence remains in [`../validation/PHASE_V2_3_COMPONENT_SCORECARD.md`](../validation/PHASE_V2_3_COMPONENT_SCORECARD.md).

## 7. V3.0 acceptance gates

V3.0 implementation can be considered technically complete only when all of the following are true.

### Architecture/contract

- [ ] Narrative IR V3.0 subset has typed implementation and contract tests.
- [ ] Compiler stages depend on S.A.G.A.-owned interfaces rather than model-specific structures.
- [ ] Source spans and source fingerprint binding are validated.
- [ ] Artifact/config/model fingerprints are deterministic and covered by tests.
- [ ] Candidate and canonical/accepted state are structurally distinct.
- [ ] `unresolved` is supported end to end.

### Model-light CI

- [ ] Package imports without heavyweight optional model dependencies installed.
- [ ] Unit/contract tests do not download model weights.
- [ ] deterministic fixtures cover source, IR, fingerprint, lexer-interface, linker-interface and v2-adapter behavior.
- [ ] existing v2 model-light tests remain green.

### Model qualification

- [ ] exact candidate model package/checkpoint revisions are pinned for a qualification run;
- [ ] license ledger is updated from first-party model/repository metadata;
- [ ] GLiNER2-class lexer run is reproducible on the selected public qualification corpus;
- [ ] learned linker/scorer challenger run is reproducible;
- [ ] peak RAM/VRAM and wall time are recorded;
- [ ] no model is called production-adopted without the product-quality gate.

### Quality

- [ ] v2 and v3 are scored through the same benchmark contract;
- [ ] v3 reduces unsafe identity behavior relative to the frozen v2 baseline;
- [ ] useful coverage does not collapse merely to obtain precision;
- [ ] unsupported canonical facts are not introduced by the compiler;
- [ ] disagreements can be traced to source evidence and stage/model provenance.

## 8. Promotion rule

The preferred product metric is **supported coverage at >=97% precision** where suitable gold exists.

A V3.0 prototype may proceed with public/model-light fixtures even while the protected modern-fiction suite is unavailable, but **production promotion is blocked** until representative private-fiction qualification can be run.

## 9. Migration rule

During V3.0:

```text
source
  |-- v2 -> existing results
  `-- v3 -> shadow Narrative IR + benchmark artifacts
```

No user-facing read path may switch to v3 solely because the prototype exists. Promotion requires a later explicit migration decision backed by benchmark evidence.

## 10. Exit

When the gates above are met, the next phase is selected from measured failure modes rather than roadmap order. Expected candidates are dialogue/speaker attribution, scenes, or event/event-coreference, but benchmark evidence decides priority.
