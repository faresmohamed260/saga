# S.A.G.A. v3 Narrative Compiler Architecture

Status: **DRAFT TARGET ARCHITECTURE**

## 1. Objective

S.A.G.A. v3 compiles a novel or series into an evidence-linked Narrative IR. It is not an agent that repeatedly asks an LLM what happens in a book.

The critical path is a typed, reproducible dataflow:

```text
Source
  -> Source Compiler
  -> Semantic Lexer
  -> Global Linkers
  -> Narrative IR
  -> Specialized Reasoners
  -> Constraint Solvers
  -> Canonical Facts
  -> Derived Views / Graphs / Retrieval / Generation
```

## 2. Non-negotiable constraints

1. Required textual analysis remains local and subscription-free.
2. Models may propose evidence; S.A.G.A. policy owns canon.
3. Every accepted semantic claim must be traceable to source evidence.
4. Unknown/unresolved is valid.
5. Whole novels and eventually multi-book series are first-class workloads.
6. Reprocessing should be incremental and content-addressed.
7. The architecture is model-independent.
8. Research-only/non-commercial weights may be benchmark ceilings but not silent production dependencies.

## 3. Layer A — Source Compiler

Responsibilities:

- source-byte preservation;
- EPUB/TXT normalization;
- normalized text fingerprint;
- chapter/section/paragraph/sentence structure;
- exact offsets;
- deterministic quote spans;
- narrative/source order.

This layer performs no story-world interpretation.

Outputs are immutable structural artifacts.

## 4. Layer B — Semantic Lexer

Purpose: harvest local semantic candidates cheaply and at high recall while retaining exact spans.

Candidate capabilities:

- entity mentions;
- event mentions;
- local semantic roles;
- explicit attributes;
- local relation observations;
- modality/negation cues;
- semantic classifications.

Initial challengers:

- GLiNER2/2.5-class schema-conditioned encoders;
- retained BookNLP components where measured strength remains competitive;
- deterministic syntax and lexical rules.

The lexer does not perform book-global identity or canonical event consolidation.

## 5. Layer C — Global Linkers

### Entity linker

Inputs:

- mentions;
- local coreference evidence;
- aliases/names/titles;
- context embeddings;
- structural context;
- existing entity clusters.

Process:

1. cheap candidate generation;
2. top-k retrieval;
3. cross-encoder or learned pair/cluster scoring;
4. hard consistency checks;
5. merge / attach / unresolved decision.

Provider/model cluster IDs are never canonical IDs.

### Event linker

Performs event coreference/consolidation across local event mentions using:

- participant overlap;
- lexical semantics;
- temporal compatibility;
- source proximity;
- location/state evidence;
- pair/cluster scoring.

## 6. Layer D — Narrative IR

The Narrative IR is the canonical semantic interchange layer.

Core objects:

- source spans;
- mentions/entities;
- propositions/observations;
- event mentions/events/participants;
- state observations/deltas;
- relationship observations/states;
- temporal constraints;
- causal candidates;
- accepted facts.

Models are adapters into this IR, not owners of downstream schemas.

## 7. Layer E — Specialized Reasoners

Specialized discriminative models should handle repetitive decisions whenever sufficient training/evaluation data exists.

Target modules:

- `SAGA-Linker`
- `SAGA-Speaker`
- `SAGA-Scene`
- `SAGA-Event`
- `SAGA-Temporal`
- `SAGA-Causal`

Likely base families include modern open encoders/cross-encoders such as Ettin-class models. Exact adoption is benchmark-driven.

## 8. Layer F — Structured Extraction Escalation

Hard local passages that remain unresolved after specialist passes may be sent to an extraction-specialized local generative model.

Initial challenger:

- NuExtract3-class structured extraction model.

Responsibilities may include:

- ambiguous event frames;
- difficult explicit attributes;
- relation normalization;
- bounded proposition extraction.

Outputs remain candidate evidence.

## 9. Layer G — General Semantic Adjudication

A general local reasoning model is the final semantic escalation, not the default extractor.

Initial direction:

- Qwen3.5-class local model;
- structured/grammar-constrained output;
- non-thinking mode for simple adjudication;
- thinking mode only for genuinely hard cases.

Never use repeated full-book prompts as the default analysis method.

## 10. Layer H — Constraint Solvers

Some correctness problems are global graph problems and should not be delegated to text generation.

### Temporal solver

Consumes pairwise temporal constraints and applies:

- inverse relations;
- transitive closure where valid;
- cycle/contradiction detection;
- partial-order construction;
- unresolved preservation.

### State solver

Consumes accepted state observations/deltas and produces point-in-time views without losing event provenance.

### Canonicalization policy

Promotes candidate observations to facts using:

- confidence/calibration;
- agreement/disagreement;
- hard constraints;
- contradiction checks;
- provenance quality;
- task-specific thresholds.

## 11. Persistence

### Canonical store

PostgreSQL/Supabase stores:

- source structure;
- Narrative IR;
- analysis artifacts;
- provenance;
- accepted/rejected/unresolved facts;
- stage/model/config versions.

### Derived stores

Neo4j, vector indexes and generated summaries are derived materializations.

They must be reconstructible from canonical IR.

## 12. Runtime architecture

Preferred runtime boundary:

```text
Supabase durable jobs
        |
        v
thin worker supervisor
        |
        v
long-lived Python narrative compiler
        |
        +-- model registry
        +-- batch scheduler
        +-- GPU lifecycle manager
        +-- stage cache
        +-- evaluation hooks
        |
        v
validated Narrative IR artifacts
        |
        v
Supabase/Postgres canonical persistence
```

The current durable queue/lease semantics remain valuable. ML execution should become Python-native instead of growing a provider wrapper around every individual library.

## 13. Scheduling principle

Process by model/stage batches rather than repeatedly swapping models per chapter.

Preferred pattern:

1. compile all structural units;
2. load semantic lexer, process all windows, unload;
3. perform global linking;
4. load specialist scorers, batch candidates;
5. load structured extraction/generative models only for unresolved residue;
6. run graph/state/canonicalization solvers.

## 14. Training flywheel

Human corrections become first-class training data.

```text
model candidate
 -> evidence review
 -> accept/correct/reject
 -> gold example
 -> specialist retraining
 -> active-learning selection
```

Long-term goal: external models bootstrap S.A.G.A.-specific specialist models rather than permanently defining the stack.

## 15. What v3 deliberately does not do

- no single model owns the whole story graph;
- no LLM-generated JSON is canon by default;
- no Neo4j-only truth;
- no N^2 whole-book event/entity pair scoring;
- no agentic orchestration for the deterministic compilation DAG;
- no forced total chronology;
- no trait/relationship labels inferred from a single weak observation;
- no model migration without common benchmark evidence.
