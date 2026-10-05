# S.A.G.A. Project Status

S.A.G.A. is being rebuilt as a web-first narrative-intelligence platform. The **accepted target textual-analysis architecture is now S.A.G.A. v3: the Narrative Compiler**. The existing v2 runtime remains the operational/baseline implementation until individual v3 capabilities pass shadow qualification and are explicitly promoted.

This file is the current project handoff. Git history remains authoritative for exact merge/commit state. Use [`docs/README.md`](docs/README.md) for the documentation map.

## Current status

- **Phase 1 — Closed-demo main site, accounts, and invitations: COMPLETE.**
- **Phase 2 — Story intake and character-identity foundation: REPOSITORY FOUNDATION COMPLETE.**
- **Phase v2.3 — Local-first narrative-analysis baseline: FROZEN AS COMPARISON/OPERATIONAL BASELINE.**
- **Phase V3.0 — Narrative Compiler Foundation: ACTIVE ON MERGE.**

The application/control-plane foundation remains in place. V3.0 is an analysis-engine reboot, not a product/auth/storage rewrite.

## Why v3

The v2 work established strong engineering invariants and useful measurements, but it also exposed the limits of treating book understanding primarily as a cascade of third-party literary-NLP providers plus rules.

V3 keeps the proven infrastructure and evidence discipline while replacing the semantic center with a local typed compiler:

```text
SOURCE COMPILER
      -> SEMANTIC LEXER
      -> GLOBAL LINKERS
      -> NARRATIVE IR
      -> SPECIALIST REASONERS
      -> GLOBAL CONSTRAINT SOLVERS
      -> CANONICAL NARRATIVE IR
      -> graph / retrieval / generation projections
```

The governing rule is:

> Models produce evidence. S.A.G.A. owns identity, consistency, provenance and canon.

## V3.0 implementation scope

The first phase is deliberately narrow:

```text
SOURCE COMPILER
      -> SEMANTIC LEXER
      -> GLOBAL CHARACTER LINKER
      -> NARRATIVE IR
      -> V2/V3 BENCHMARK REPORT
```

The execution contract is [`docs/phases/PHASE_V3_0_NARRATIVE_COMPILER_FOUNDATION.md`](docs/phases/PHASE_V3_0_NARRATIVE_COMPILER_FOUNDATION.md).

V3.0 will establish:

- a Python-native compiler package for semantic analysis;
- typed Narrative IR models;
- deterministic source/config/model/stage fingerprints;
- an adapter over the existing normalized source representation;
- a model-independent semantic-lexer contract;
- a first GLiNER2-class lexer challenger;
- book-global identity candidate generation/scoring/resolution contracts;
- a first Ettin-class learned scorer challenger if qualification/license checks remain acceptable;
- a frozen-v2 adapter;
- one comparable v2-v3 benchmark report.

V3 remains shadow-only during this phase. Production reads/writes continue to use the existing path until a later explicit migration decision.

## Foundations preserved from v2

The reboot preserves:

- deterministic TXT/EPUB ingestion and normalized source fingerprints;
- immutable source bytes and exact evidence offsets;
- chapter/section/source structure;
- deterministic quote boundaries while they remain the measured leader;
- Supabase durable jobs, leases and analysis runs;
- B2 object-storage boundaries;
- auth/RLS/application control-plane contracts;
- immutable provenance and explicit uncertainty;
- precision-first canonicalization;
- existing public/private evaluation assets;
- the principle that unresolved evidence is safer than an unsupported canonical assertion.

## Canonical data direction

The v3 Narrative IR is the semantic source of truth. Canonical semantic state belongs in PostgreSQL/Supabase once production persistence is introduced. Neo4j, visualization graphs, search indexes and generation-oriented structures are derived/rebuildable projections rather than independent truth authorities.

The IR explicitly separates:

- `Mention` from `Entity`;
- `EventMention` from `Event`;
- `Observation` from accepted `Fact`;
- attribute observations from persistent traits;
- relationship observations from relationship state;
- narrative/source order from story-world time;
- temporal order from causality.

See [`docs/v3/NARRATIVE_IR.md`](docs/v3/NARRATIVE_IR.md) and [`docs/v3/ONTOLOGY.md`](docs/v3/ONTOLOGY.md).

## Required deployment/cost constraints

- Required textual analysis remains local-first and subscription-free.
- Paid AI APIs, hosted GPU subscriptions and per-token SaaS are not required dependencies.
- Modal remains reserved for governed image/media workloads, not required text analysis.
- Normal CI remains deterministic and model-light.
- Heavy model/full-book runs use dedicated local/manual qualification paths.
- Private copyrighted fiction must not enter Git or public CI/log artifacts.

## Frozen v2 baseline

The comparison branch is:

`archive/v2-analysis-baseline-2026-10-05`

Frozen baseline commit:

`e9d24d54d351f9bf7c1cfa582a01db819efdb2fe`

Important measured public baseline values include:

### Character identity — BookNLP-small

- canonical precision `0.4613`;
- canonical recall `0.6030`;
- incorrect merge `0.1934`;
- fragmentation `0.4607`;
- linked-mention precision `0.2158`;
- linked-mention recall `0.1161`;
- cluster purity `0.8667`.

BookNLP-small remains rejected as primary canonical identity truth.

### Quote detection

- S.A.G.A. deterministic quote P/R/F1: `0.8570 / 0.8555 / 0.8563`;
- BookNLP quote P/R/F1: `0.7706 / 0.8640 / 0.8146`.

The deterministic quote detector remains preserved.

### Event triggers

- BookNLP P/R/F1: `0.8003 / 0.7591 / 0.7791`;
- lexical Tier-0 P/R/F1: `0.4914 / 0.0585 / 0.1045`.

BookNLP remains a measured event-trigger baseline/challenger, not an automatic v3 dependency.

Detailed measured state remains in [`docs/validation/PHASE_V2_3_COMPONENT_SCORECARD.md`](docs/validation/PHASE_V2_3_COMPONENT_SCORECARD.md).

## Evaluation policy

Primary product qualification targets representative protected modern-fiction material. Copyrighted text/EPUB bytes remain private and outside Git.

Public corpora such as LitBank remain reproducible secondary evidence. They do not by themselves promote a model into production, especially when a provider was trained on related annotations.

The preferred v3 product metric is **supported coverage at >=97% precision** where suitable gold exists. Raw recall alone is not an adoption target.

Every candidate comparison should include quality plus wall time, peak RAM, peak VRAM when applicable, model/checkpoint revision, license, reproducibility and operational complexity.

## Current non-capabilities

The following must not be represented as shipped merely because v3 schemas or design documents exist:

- production v3 identity/entity analysis;
- production v3 scene segmentation;
- production v3 speaker attribution;
- production event/event-coreference compilation;
- persistent character/world state;
- story-world chronology and flashback resolution;
- causal/motivational graph inference;
- completed arcs/tension/themes;
- final canon-aware retrieval or grounded generation from v3 IR.

## Immediate next action

After the V3.0 phase contract and durable decisions are merged to `main`:

1. create the isolated Python narrative-compiler package;
2. implement the V3.0 Narrative IR subset and deterministic fingerprints;
3. adapt the existing normalized source representation;
4. implement model-independent lexer/linker interfaces with model-light tests;
5. integrate the first qualified GLiNER2-class and Ettin-class challengers behind optional heavyweight paths;
6. produce the first v2-v3 identity/entity comparison.

## Read next

1. [`AGENTS.md`](AGENTS.md) — repository/AI development instructions.
2. [`docs/README.md`](docs/README.md) — documentation map.
3. [`docs/DECISIONS.md`](docs/DECISIONS.md) — durable decisions.
4. [`docs/phases/PHASE_V3_0_NARRATIVE_COMPILER_FOUNDATION.md`](docs/phases/PHASE_V3_0_NARRATIVE_COMPILER_FOUNDATION.md) — active V3.0 contract.
5. [`docs/v3/README.md`](docs/v3/README.md) — reboot package entry point.
6. [`docs/v3/ARCHITECTURE.md`](docs/v3/ARCHITECTURE.md) — target architecture.
7. [`docs/v3/NARRATIVE_IR.md`](docs/v3/NARRATIVE_IR.md) — semantic intermediate representation.
8. [`docs/v3/EVALUATION.md`](docs/v3/EVALUATION.md) — comparison/promotion policy.
9. [`docs/validation/PHASE_V2_3_COMPONENT_SCORECARD.md`](docs/validation/PHASE_V2_3_COMPONENT_SCORECARD.md) — frozen baseline evidence.

Git history owns exact merge state; this handoff owns the high-level active direction.