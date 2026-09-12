# S.A.G.A. v2 Phase 3 — Local-First Narrative Analysis Rebaseline

Status: **ACTIVE CONTRACT DRAFT — merge before implementation**

Owner direction on 2026-09-12 changes the textual-analysis architecture: S.A.G.A. should achieve its full book/series analysis goals with minimal resources, no paid AI subscriptions/APIs, and no dependency on Modal for textual NLP/reasoning. Modal is reserved for image-generation/media workloads.

This phase is therefore a deliberate rebaseline, not a continuation of the abandoned hosted-xCoRe path.

## 1. Objective

Establish and validate a local-first analysis runtime that preserves the proven v2 application/job/provenance foundations while replacing hosted-model assumptions with a measured cascade of deterministic code, lightweight literary NLP and selective local reasoning.

The phase succeeds when S.A.G.A. has:

1. a durable local worker/runtime contract that can claim existing Supabase analysis jobs using outbound-only access;
2. a reproducible benchmark harness for whole-book resource/quality comparison;
3. an adopted first-pass evidence stack for character/entity, dialogue/speaker and event-candidate analysis chosen by measurement rather than legacy history;
4. a bounded local structured-reasoning interface for later event/relation/state/causal adjudication;
5. no required textual-analysis dependency on Modal or paid inference APIs.

## 2. Starting state

Phase 2 already provides:

- TXT/EPUB source ingestion and deterministic normalization;
- private B2 source storage boundary;
- durable Postgres jobs, leases and immutable runs;
- normalized source/section persistence;
- precision-first S.A.G.A. character identity policy;
- provider-neutral identity evidence contract;
- deterministic identity/LitBank evaluation harness;
- private result/evidence UI.

Phase 2 repository qualification is complete. The previously planned permanent hosted-worker/provider proof is superseded as the architecture path by this owner decision. Hosted end-to-end acceptance remains valuable later, but it must use the new local-first runtime rather than make Modal/text-model hosting a product dependency.

The `ops/phase2-hosted-proof` Modal/xCoRe experiment is experimental evidence only and must not be merged into `main` as the textual-analysis architecture.

## 3. Product target beyond this phase

The eventual analysis system should build an evidence-linked narrative world model covering:

```text
source structure
  -> mentions/entities/characters
  -> dialogue + speakers
  -> scenes
  -> atomic events + participants
  -> relationships + state deltas
  -> narrative-order + story-time timeline
  -> causal/motivational graph
  -> character/world profiles
  -> arcs/tension/themes/summaries
  -> canon-aware retrieval/visualization/generation
```

Phase 3 does not need to finish every layer. It establishes the runtime/evidence strategy that later phases can extend without returning to per-scene paid API extraction.

## 4. Non-negotiable architecture rules

### 4.1 Local-first textual inference

The required analysis path must work with local CPU/GPU inference and public open-source weights.

Paid hosted AI can be evaluated manually in the future, but cannot be necessary for normal book analysis unless the owner explicitly reverses this decision.

### 4.2 Modal boundary

Modal is not a textual analysis host in the active architecture.

Permitted Modal ownership is limited to image/media generation or separately approved media workloads. Any existing text-analysis Modal experiment is temporary and non-authoritative.

### 4.3 Cascade before generative reasoning

For each task:

1. deterministic rules/structure first;
2. lightweight local NLP second;
3. specialized local model only for unresolved ambiguity;
4. small local generative reasoning only for bounded evidence packets that still require judgment.

Do not send the full raw novel repeatedly to a large language model merely because a long context window exists.

### 4.4 Evidence before canon

Provider/model output creates evidence/candidates. Deterministic S.A.G.A. code owns:

- canonical IDs;
- admission/merge policy;
- persistence schema;
- provenance;
- validation;
- timeline/state invariants;
- final accepted/uncertain/rejected status.

### 4.5 Whole-book resource accounting

A candidate cannot be adopted from accuracy alone. Qualification must record at least:

- wall-clock time on a complete reference book;
- peak CPU RAM;
- peak VRAM if GPU is used;
- model/download size;
- license;
- task quality metrics;
- deterministic/reproducible output behavior.

## 5. Runtime boundary

The preferred initial topology is:

```text
apps/web
  -> Supabase durable analysis jobs
      -> local S.A.G.A. worker
          -> B2 source bytes
          -> deterministic TypeScript orchestration
          -> local Python literary-NLP sidecar
          -> optional localhost llama.cpp service
          -> structured evidence/results back to Supabase
```

Requirements:

- worker requires outbound HTTPS only;
- no public inbound home-server port is necessary;
- Python/model services are loopback/private-network only;
- web browser never receives local runtime/model credentials;
- source/job ownership and lease semantics remain the existing database authority;
- worker disappearance leaves jobs durable/retryable rather than losing state;
- analysis provider interfaces remain replaceable.

The current TypeScript worker remains orchestration owner unless benchmark/implementation evidence shows a concrete reason to move that responsibility.

## 6. Phase 3A — benchmark foundation

### 6.1 Literary broad baseline

Evaluate **BookNLP small** first as a broad low-cost literary evidence provider because it already supplies:

- literary entity tagging;
- event tagging;
- character/name clustering/coreference;
- quotation speaker attribution;
- syntax/supersense outputs.

Its outputs are normalized into S.A.G.A. evidence records; BookNLP IDs do not become S.A.G.A. canonical IDs directly.

### 6.2 Typed entity challenger

Evaluate **GLiNER small v2.x** for configurable typed spans, prioritizing CPU/ONNX/INT8 execution.

Initial labels should cover at minimum:

- person;
- location / geopolitical location / facility;
- organization / faction;
- object / artifact;
- creature/species where useful;
- vehicle where useful.

### 6.3 Coreference challengers

Evaluate permissively licensed local candidates before non-commercial LitBank weights:

- F-Coref as the cheap challenger;
- LingMess only if stronger accuracy justifies its much larger footprint;
- historical xCoRe/Maverick results as comparative research, not default runtime dependencies.

All coreference evidence still passes through the existing S.A.G.A. precision-first identity resolver.

### 6.4 Dialogue baseline

Benchmark:

1. deterministic quote-span + speech-verb/dependency sieve;
2. BookNLP quote/speaker attribution;
3. combined candidate restriction/stabilization.

Measure speaker accuracy, unresolved rate and character-contamination rate.

### 6.5 Event baseline

Benchmark:

1. deterministic dependency/verb candidate extraction;
2. BookNLP literary event triggers;
3. combined trigger pass;
4. optional Qwen3.5-4B schema-constrained normalization over surviving event candidates only.

Measure event trigger precision/recall, duplicate rate, unsupported event rate and participant grounding.

## 7. Phase 3B — local runtime adapter

Implement a v2-owned local provider boundary that can expose the adopted benchmark winners without provider-specific records leaking into application tables.

Initial requirements:

- versioned provider descriptor and configuration fingerprint;
- Unicode code-point/source offsets preserved exactly;
- bounded batches/chunks with stable IDs;
- deterministic mapping of provider output into S.A.G.A. evidence;
- process/model health reporting that does not reveal secrets;
- optional CPU-only mode;
- optional GPU acceleration mode;
- no network dependency during inference after model artifacts are installed.

Use a narrow local HTTP or subprocess contract. Prefer the simplest measured option rather than introducing distributed infrastructure.

## 8. Local generative reasoning boundary

Phase 3 may add an experimental local structured-reasoning client, but it is not allowed to own core application truth.

Initial candidates:

- Qwen3.5-4B quantized as default benchmark;
- Qwen3.5-9B quantized as quality escalation benchmark;
- llama.cpp as the initial serving layer.

Requirements:

- localhost/private service only;
- JSON-schema or grammar constrained outputs where possible;
- deterministic/low-temperature settings for extraction tasks;
- evidence packets include source spans and resolved entity IDs;
- every returned fact is validated before persistence;
- prompts/config/model revision participate in provenance;
- full-book raw-text prompting is not the default architecture.

## 9. Benchmark corpus

Use three levels of evidence:

### Merge-gate fixtures

Small committed synthetic/adversarial text and selected license-compatible LitBank snippets. No heavyweight model download in normal CI.

### Literature benchmark

Reuse the existing pinned LitBank adapter/evaluator where applicable and extend metrics for entity/event/dialogue tasks.

### Whole-book benchmark

Use at least one complete public-domain novel with a stable source revision. Whole-book benchmark runs are manual/local/dedicated, not required for every PR.

The benchmark report must record the exact source digest, model revisions, hardware class/configuration and runtime settings.

## 10. Quality gates

### Identity / entities

- canonical precision/recall;
- false canonical rate;
- incorrect merge rate;
- fragmentation rate;
- linked mention precision/recall;
- non-person contamination;
- entity typing precision.

### Dialogue

- quote detection precision/recall;
- speaker attribution accuracy;
- unresolved speaker rate;
- cross-character contamination.

### Events

- trigger precision/recall;
- participant grounding precision/recall;
- unsupported event rate;
- duplicate event rate;
- realis/modality correctness where gold data permits.

### Resource

- CPU time;
- peak RAM;
- peak VRAM;
- model size;
- calls/tokens consumed by local generative stage;
- percentage of source/evidence that needed Tier-3 escalation.

A model is not an improvement if a small quality gain requires dramatically more compute and the downstream product quality does not benefit.

## 11. Data/provenance direction

Phase 3 should prefer reusable evidence layers over monolithic final JSON.

Expected families include:

- structural span;
- typed entity mention;
- quote span;
- speaker evidence;
- event trigger/candidate;
- participant evidence;
- temporal expression/candidate relation;
- model adjudication record.

Later accepted event/relationship/state/timeline rows should retain links to these lower-level evidence records.

Do not create schema merely because a candidate model emits a field. Schema reflects S.A.G.A. product concepts.

## 12. Explicitly out of scope for the first implementation slice

- paid external LLM APIs;
- Modal textual inference;
- final causal graph implementation;
- final series-level world-state synthesis;
- final theme/tension/arc generation;
- public SaaS-scale worker hosting;
- broad model fine-tuning before baseline measurements justify it;
- vector database adoption without a measured retrieval need.

## 13. Validation matrix

Before Phase 3 can be called complete:

| Claim | Required evidence |
|---|---|
| textual path is subscription-free | local/offline provider configuration and successful run with paid APIs disabled |
| worker is durable | real queued job claimed from the existing Postgres control plane and committed through existing lease/run semantics |
| broad NLP is useful | BookNLP/local baseline metrics on literature fixtures + whole-book timing |
| chosen identity evidence is justified | direct provider comparison through the same S.A.G.A. resolver harness |
| speaker path is grounded | quote/speaker benchmark with unresolved/contamination reporting |
| event path is grounded | event/participant benchmark and source-evidence assertions |
| local LLM is bounded | measured escalation rate + schema/evidence validation; no full-book mandatory calls |
| Modal is absent from text path | structural tests/config scan and runtime proof |
| reproducibility is preserved | exact model/config/source fingerprints and deterministic semantic result fingerprints where expected |

## 14. Exit criteria

Phase 3 exits when:

1. this architecture is represented by active v2 code/contracts rather than only research;
2. one local analysis host can process a real supported book from the durable queue without Modal or a paid model API;
3. a measured provider stack is adopted for character/entity, dialogue/speaker and event-candidate evidence;
4. benchmark reports include quality + resource cost and justify the selected defaults/escalation path;
5. outputs remain evidence-linked, private and provenance-complete;
6. the next phase can build event/state/timeline/relationship intelligence on these evidence layers without repeating raw-book inference.

## 15. Next phase dependency

After Phase 3, the likely next contract is an **Event / State / Timeline Narrative Graph** slice using the adopted evidence runtime. It must be specified from Phase-3 measurements rather than inheriting the historical v1 EventAgent/EntityAgent/RelationshipAgent/TimelineAgent topology verbatim.