# S.A.G.A. v2 — 2026 Local-First Narrative Analysis Architecture

Status: **ACTIVE DIRECTION — owner reset 2026-09-12**

This document defines the current engineering direction for textual/book analysis. It supersedes the assumption that S.A.G.A. should find a permanent hosted NLP/model provider simply because the historical runtime used one.

## 1. Product objective

S.A.G.A. does not exist to summarize books. Its analysis runtime should reverse-engineer a novel or series into an evidence-linked narrative model that can support:

- book/chapter/scene structure;
- canonical characters, aliases and mentions;
- dialogue and speaker attribution;
- locations, organizations, objects, creatures, factions and other entities;
- atomic events and event participants;
- relationships and their evolution;
- character/world state over time;
- temporal ordering, flashbacks and explicit time references;
- causal links, motivations and consequences;
- higher-level arcs, tension, conflict and narrative summaries;
- later canon-aware retrieval, visualization and generation.

Every derived claim should remain traceable to source evidence and carry explicit uncertainty/provenance rather than silently becoming canon truth.

## 2. Owner constraints

The 2026 analysis rebuild has the following non-negotiable constraints:

1. **No paid AI API or recurring model subscription is part of the required textual-analysis path.**
2. **Modal is reserved for image-generation/media workloads. Textual book analysis must not depend on Modal.**
3. Prefer deterministic algorithms, classical NLP and small open-source models before generative models.
4. Prefer CPU execution where quality/latency are acceptable; use a local consumer GPU only when it materially improves quality or throughput.
5. Whole novels and eventually multi-book series are the target workload. A design that only works on short chunks is insufficient.
6. Model/provider output is evidence, not product truth. S.A.G.A. deterministic policy owns canonical IDs, state transitions, provenance, validation and persistence.
7. Expensive inference must be **selective**. Do not repeatedly feed an entire book through a large generative model when a deterministic or lightweight pass can narrow the problem first.
8. Normal CI remains model-light and deterministic. Large models/full-book benchmarks run in dedicated local/manual qualification jobs.
9. Prefer permissive/commercial-friendly licenses for the adopted default stack. Non-commercial research weights may remain benchmark candidates but must not become an unnoticed production dependency.

## 3. Foundations that survive the reset

The following v2 work remains valuable and should be preserved:

- deterministic TXT/EPUB ingestion and normalized Unicode offsets;
- immutable source bytes plus normalized-source fingerprints;
- Supabase durable job/lease/run control plane;
- immutable analysis provenance;
- S.A.G.A. precision-first character admission policy;
- unresolved/quarantined evidence as valid output;
- provider-neutral evidence contracts;
- LitBank evaluation harness and deterministic fingerprints;
- private evidence UI and owner/RLS boundaries.

The reset changes **how evidence is produced and how later narrative intelligence is built**, not these application invariants.

## 4. Target deployment topology

The default target is a local analysis worker with outbound-only cloud access:

```text
Browser / apps/web
        |
        v
Supabase durable jobs + structured results
        ^
        | HTTPS outbound only
        |
local analysis worker
  |-- deterministic ingestion/graph logic
  |-- local Python NLP sidecar(s)
  |-- local llama.cpp inference endpoint when escalation is needed
        |
        +----> B2 source read/write boundary
```

Important consequences:

- no public inbound port is required for the analysis host;
- the local worker polls/claims durable jobs and writes results through existing bounded service contracts;
- local model services bind to loopback/private container networking only;
- the web application never talks directly to a local model;
- an offline worker can resume later because Supabase owns durable queue truth;
- cloud hosting is not required to analyze a book.

The existing TypeScript `services/analysis-worker` remains the preferred control-plane/orchestration owner unless measurements justify replacing it. Python-specific NLP should live behind a narrow local provider/sidecar interface rather than forcing NLP libraries into Next.js or duplicating job ownership.

## 5. Analysis cascade

Use a multi-tier cascade so expensive inference is paid only where ambiguity remains.

### Tier 0 — deterministic / structural

Run on every source:

- EPUB/TXT normalization;
- chapter/section/paragraph/sentence boundaries;
- deterministic quote-span discovery where typography is unambiguous;
- lexical/name normalization;
- title/honorific handling;
- structural source-order chronology;
- rule-based temporal/connective cues;
- candidate graph construction;
- evidence/provenance bookkeeping.

### Tier 1 — lightweight local NLP

Run broadly because cost is low:

- POS/dependency parsing;
- literary entity/event tagging;
- PERSON/non-person typing;
- lightweight coreference evidence;
- speaker-attribution evidence;
- small embeddings only where they reduce candidate search space.

### Tier 2 — specialized local models

Run when Tier 0/1 cannot safely decide:

- stronger coreference on ambiguous passages;
- relation classification;
- temporal-relation classification;
- difficult speaker attribution;
- scene/event consolidation.

### Tier 3 — small local generative reasoning

Use only on bounded evidence packets, never as hidden glue over the full raw novel:

- normalize candidate events into structured schema;
- adjudicate ambiguous relationships/causal links;
- infer state deltas with cited spans;
- compress already-grounded structures into profiles/arcs/summaries.

All generative outputs are schema-constrained, evidence-linked candidate facts that still pass deterministic validators.

## 6. Current 2026 candidate stack

These are **benchmark candidates**, not permanent selections.

### BookNLP small — broad literary baseline

Why it is high priority:

- MIT-licensed package;
- purpose-built for book-length literary text;
- one pipeline already exposes entity tagging, event tagging, name clustering/coreference and quote speaker attribution;
- uses spaCy for syntax;
- its published `small` profile is intended for personal computers;
- published Secret Garden (99K token) timing is ~3.6 min on a 2019 MacBook Pro CPU and ~2.4 min on a 10-core server;
- published small-model scores include entity F1 88.2, event F1 70.6, coreference Avg F1 76.4 and speaker-attribution B3 86.4.

S.A.G.A. should benchmark BookNLP output as **evidence** rather than import its entity IDs as canon.

Reference: https://github.com/booknlp/booknlp

### GLiNER small v2.x — typed open entity baseline/challenger

Why evaluate it:

- Apache-2.0 model family;
- zero-shot/custom entity labels;
- designed for resource-constrained use;
- project explicitly supports CPU, INT8 quantization and ONNX export;
- useful for PERSON / location / organization / artifact / creature / faction typing without a generative LLM;
- RelEx variants provide a later relation-extraction experiment.

Reference: https://github.com/urchade/GLiNER

### F-Coref / LingMess — permissive coreference challengers

`biu-nlp/f-coref`:

- MIT licensed;
- ~362 MB weights;
- fast coreference implementation suitable as a cheap challenger to BookNLP identity evidence.

`biu-nlp/lingmess-coref`:

- MIT licensed;
- stronger/heavier Longformer-based model (~2.36 GB);
- use only if benchmark gains justify extra memory/latency.

References:

- https://github.com/shon-otmazgin/fastcoref
- https://huggingface.co/biu-nlp/f-coref
- https://huggingface.co/biu-nlp/lingmess-coref

### xCoRe / Maverick — research-only candidates by default

The LitBank checkpoints remain useful comparative evidence, but their released weights are CC BY-NC-SA 4.0 and are based on large DeBERTa-class models. They therefore should **not** become the default long-term S.A.G.A. production dependency without an explicit licensing/product decision.

The prior Modal xCoRe hosted-proof branch is superseded by the local-first reset and must not be merged as the textual-analysis architecture.

### Local structured reasoning — Qwen3.5 + llama.cpp

Qwen3.5 4B and 9B are Apache-2.0 and natively support very long contexts. The intended S.A.G.A. use is nevertheless **bounded structured reasoning**, not repeatedly streaming a full novel.

Initial benchmark order:

1. Qwen3.5-4B quantized — default candidate for event/relation/state adjudication;
2. Qwen3.5-9B quantized — quality escalation candidate;
3. smaller 0.8B-class model only for cheap classification if measurements show it is useful.

`llama.cpp` is the preferred initial serving candidate because it provides a lightweight local HTTP server plus JSON-schema/grammar-constrained output, embeddings and reranking without a subscription.

References:

- https://huggingface.co/Qwen/Qwen3.5-4B
- https://huggingface.co/Qwen/Qwen3.5-9B
- https://github.com/ggml-org/llama.cpp

### Small embeddings — optional

Do not introduce vector infrastructure until a measured task needs it. If candidate retrieval across scenes/books benefits from embeddings, first benchmark small permissive models such as:

- `BAAI/bge-small-en-v1.5` (MIT; ~33M parameters);
- `sentence-transformers/all-MiniLM-L6-v2` (Apache-2.0).

Prefer ONNX CPU inference for this class of model.

## 7. Stage-by-stage first architecture

### Structure / scene boundaries

Default:

- preserve deterministic EPUB/chapter structure;
- paragraphs/sentences from deterministic parser + spaCy;
- scene boundaries begin with typography/section-break rules and discourse/location/time-change signals;
- a model may propose additional boundaries but cannot silently rewrite source structure.

### Character identity

Default direction:

- keep the current deterministic S.A.G.A. resolver;
- benchmark BookNLP-small evidence against GLiNER + F-Coref combinations;
- use stronger coreference only for unresolved/ambiguous candidates when possible;
- do not use xCoRe hosted infrastructure as the default path.

### Dialogue / speakers

Default direction:

1. deterministic quotation span recognition;
2. nearby speech-verb/dependency sieve;
3. BookNLP speaker-attribution evidence;
4. sequence/context heuristics;
5. local model adjudication only when multiple plausible speakers remain.

Speaker identity must resolve through canonical character IDs.

### Non-character entities / world

Default direction:

- BookNLP entity/supersense evidence plus GLiNER typed-span challenger;
- deterministic canonicalization/alias rules;
- locations/organizations/objects/factions remain distinct entity classes;
- local LLM is reserved for difficult semantic typing or consolidation, not bulk mention harvesting.

### Events

Default direction:

1. BookNLP literary-event triggers and dependency verbs supply candidate events;
2. deterministic syntax supplies initial actor/patient/object links;
3. quote/speaker and canonical-entity evidence enrich participants;
4. a small local model normalizes only surviving candidates into the S.A.G.A. event schema;
5. every event stores source evidence and realis/modality status.

This replaces the historical pattern of making a reasoning call over every scene batch.

### Relationships

Relationships are derived from repeated grounded evidence, not one-off narrative guesses.

Candidate evidence comes from:

- explicit kinship/social predicates;
- event participation;
- dialogue interactions;
- possession/affiliation statements;
- optional relation-extraction model output.

A relationship can accumulate/decay/change over the timeline. Local generative reasoning may classify ambiguous candidate relations after retrieval narrows the pair set.

### Timeline

Separate **narrative order** from **story-world time**.

- narrative/source ordering is deterministic;
- explicit dates/durations/relative expressions can be normalized with rule-based temporal tooling such as HeidelTime or equivalent lightweight code;
- before/after/flashback candidates are generated from connectives and event references;
- local reasoning is reserved for ambiguous cross-scene ordering;
- uncertain order remains partial rather than being forced into a false total chronology.

Reference: https://github.com/HeidelTime/heideltime

### Character/world state

Use an event-sourced state ledger rather than repeatedly asking a model for a full profile.

State facts have:

- subject/entity ID;
- predicate/value;
- evidence span(s);
- valid-from / valid-to event or narrative position where known;
- confidence/evidence tier;
- producing engine/version.

Deterministic reducers build current/point-in-time views from state deltas.

### Causality

Do not compare every event to every other event.

Generate candidate causal edges from:

- close narrative/temporal distance;
- shared participants/entities;
- discourse markers (`because`, `therefore`, `so`, `after`, etc.);
- prerequisite/state transitions;
- optional small embedding similarity.

Only top candidate pairs reach local relation/judgment inference. Unsupported causality stays absent/uncertain.

### Higher narrative analysis

Arcs, summaries, tension and themes should consume the compressed evidence graph/timeline/state, not require repeated raw-book passes. This both lowers inference cost and reduces hallucination risk.

## 8. Evaluation philosophy

Adoption is determined by S.A.G.A. product metrics plus resource measurements, not by a model leaderboard alone.

Every candidate benchmark should capture:

- task quality metrics;
- false-positive/contamination behavior;
- whole-book runtime;
- peak RAM;
- peak VRAM when applicable;
- model/download size;
- output determinism/reproducibility;
- license;
- ease of deployment and maintenance.

Task metrics include:

- identity false canonicals / incorrect merges / fragmentation / attachment precision-recall;
- speaker attribution accuracy and unresolved rate;
- entity typing precision and canonicalization contamination;
- event trigger precision-recall plus participant grounding;
- event duplication and unsupported-event rate;
- temporal ordering contradictions;
- relationship support rate;
- state contradiction/unsupported-fact rate;
- causal-edge support precision;
- end-to-end ability to answer who/what/where/when/why with source evidence.

A faster or smaller model wins when quality is close enough. A heavyweight model is adopted only when measured quality justifies its cost.

## 9. Immediate benchmark plan

The first implementation benchmark should compare, on committed/adapted LitBank fixtures plus at least one full public-domain novel:

### Identity/entity pass

- BookNLP small;
- GLiNER small + S.A.G.A. resolver;
- F-Coref combined with typed mention evidence;
- existing oracle baseline as the resolver ceiling/reference;
- xCoRe only as historical/research comparison if convenient locally.

### Dialogue

- deterministic quote/speech-verb sieve;
- BookNLP attribution;
- combined sieve + BookNLP candidate restriction.

### Events

- deterministic dependency candidate baseline;
- BookNLP event tagger;
- combined candidate pass;
- Qwen3.5-4B schema-constrained normalization over only the surviving candidates.

The result should identify the cheapest acceptable default and explicit escalation conditions.

## 10. Cost policy

Textual analysis should remain functional when all paid external AI services are disabled.

Allowed by default:

- existing web/Supabase/B2 application infrastructure within the project's normal free/hobby usage;
- local CPU/GPU inference;
- public model downloads;
- GitHub Actions deterministic CI and bounded benchmark orchestration.

Not allowed as a required textual-analysis dependency without a new owner decision:

- Modal compute;
- OpenAI/Anthropic/Mistral/Gemini or other paid inference APIs;
- hosted GPU subscriptions;
- per-token SaaS extraction/coreference services.

Modal remains available to the separate image/media generation subsystem.

## 11. Architecture rule

The governing principle for each analysis stage is:

> Use the cheapest deterministic method that gets most of the way there, narrow the ambiguity set with lightweight local NLP, and spend generative inference only on the small residue that actually requires judgment.

This rule should be treated as an optimization target and validated with measurements, not as a reason to reject a model that demonstrably earns its resource cost.