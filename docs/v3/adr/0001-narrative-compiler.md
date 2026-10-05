# ADR-0001: Reboot Analysis as a Narrative Compiler

Status: **PROPOSED FOR OWNER ACCEPTANCE**

Date: 2026-10-05

## Context

S.A.G.A. v2 established strong infrastructure invariants around source provenance, durable jobs, deterministic evidence and precision-first canonicalization. Its semantic analysis layer, however, grew around literary NLP providers—especially BookNLP—and stage-specific heuristics.

Measured v2 results show a mixed picture:

- deterministic quote boundaries are strong;
- BookNLP event triggers are useful;
- character identity remains materially below product requirements;
- scene segmentation is not adopted;
- speaker attribution remains imperfect;
- relationship/state/time/causality are primarily evidence foundations rather than qualified semantic models.

The 2025-2026 open-model ecosystem provides stronger schema-conditioned extraction, modern encoders/rerankers, structured extraction models and local generative reasoning. A direct provider swap would preserve too much of the older architecture and continue to make model outputs the natural boundaries of the system.

## Decision

Reboot the semantic analysis engine as a **local narrative compiler**.

The compiler will:

1. compile immutable source structure;
2. harvest local semantic candidates through deterministic and learned lexer passes;
3. resolve identities/events globally at book/series scope;
4. emit a provider-independent Narrative IR;
5. use specialized discriminative models for repetitive semantic decisions;
6. use local structured/generative models only for unresolved residue and high-level derived outputs;
7. solve chronology/state/global consistency through deterministic graph/constraint logic;
8. store Narrative IR canonically in PostgreSQL/Supabase;
9. treat Neo4j/vector/search/generative summaries as rebuildable projections;
10. preserve unresolved/unknown when evidence is insufficient.

## Consequences

### Positive

- models can be replaced without replacing product schemas;
- global identity/time/state become explicit architectural problems;
- the system can train S.A.G.A.-specific models over time;
- evidence/provenance remains first-class;
- local zero-subscription analysis remains feasible;
- compute can be concentrated on ambiguous residue;
- graph consistency can be deterministic rather than prompt-dependent;
- v3 can support incremental recompilation.

### Negative

- higher up-front architecture and annotation cost;
- requires a formal Narrative IR and migration layer;
- requires stage-level benchmark discipline;
- likely needs new local Python runtime infrastructure;
- some existing provider-specific code becomes legacy;
- custom specialist models eventually create an ML maintenance burden.

## Rejected alternatives

### Keep v2 and only swap newer models

Rejected as the primary direction because it preserves provider-shaped semantic boundaries and does not sufficiently address global narrative identity/time/state.

### One long-context LLM over each book

Rejected as the critical path because of evidence alignment, runtime/KV cost, structured-output instability, difficult reproducibility and poor separation of local extraction from global consistency.

### GraphRAG/Graphiti as the analysis engine

Rejected as the canonical semantic compiler. Graph/memory frameworks may be useful derived infrastructure but do not replace literary extraction, identity resolution, event consolidation and temporal/state semantics.

### Agentic orchestration as the analysis core

Rejected because the dependency structure is predominantly known ahead of time and is better represented as a typed, cacheable DAG.

## Preserved v2 invariants

The reboot explicitly retains:

- source fingerprints and normalized offsets;
- deterministic source structure;
- current quote-boundary implementation unless defeated by benchmark;
- durable queue/lease/run infrastructure;
- immutable provenance;
- candidate vs accepted semantics;
- unresolved output;
- evaluation harnesses;
- application authentication/storage boundaries.

## Implementation gate

Implementation of the new semantic stack begins only after:

- `NARRATIVE_IR.md` exists;
- ontology boundaries are documented;
- canonical persistence draft exists;
- evaluation/gold corpus contract exists;
- frozen v2 baseline exists;
- v2/v3 comparison policy exists.

These documents are part of this preparation branch.
