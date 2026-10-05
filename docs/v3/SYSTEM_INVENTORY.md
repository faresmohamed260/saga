# S.A.G.A. v3 Preparation — Current System Inventory

Status: **PRE-REBOOT INVENTORY**

This inventory classifies the current analysis system so the v3 reboot can preserve infrastructure that is already sound while replacing semantic components that have reached their ceiling.

## Classification labels

- **KEEP** — preserve architecture and implementation unless a regression is discovered.
- **KEEP / GENERALIZE** — preserve capability but remove model/provider-specific assumptions.
- **REIMPLEMENT** — preserve product behavior but build a new implementation.
- **REPLACE** — current approach is not the intended v3 design.
- **BENCHMARK** — no migration decision until direct v2/v3 comparison exists.

## Repository surfaces

### `services/analysis-worker`

Current responsibility: durable textual-analysis worker, ingestion, provider invocation, identity resolution, local-analysis adapters, runtime/database integration, and evaluation tooling.

Observed major surfaces:

- `src/ingestion/`
- `src/local-analysis/`
- `src/identity/`
- `src/identity-processor.ts`
- `src/evaluation/`
- `src/runtime/`
- `src/processor.ts`
- `src/worker.ts`
- `providers/`
- `benchmarks/`
- `tests/`

### Current local-analysis implementation

The existing local-analysis directory is materially BookNLP-shaped and contains:

- BookNLP output translation;
- persistent BookNLP provider process;
- one-shot BookNLP provider process;
- BookNLP provider abstraction;
- generic subprocess provider;
- typed entity evidence;
- validation and local-analysis types.

This is useful v2 infrastructure but should not define v3's model boundaries.

## Component disposition

| Component | Current role | v3 disposition | Reason |
|---|---|---|---|
| TXT/EPUB source ingestion | normalize source | KEEP | deterministic and foundational |
| source fingerprints | immutable identity | KEEP | critical for reproducibility |
| chapter/section structure | source structure | KEEP | source fact, not inference |
| normalized source offsets | evidence addressing | KEEP | required for provenance |
| deterministic quote boundaries | quotation spans | KEEP | strongest measured public result |
| durable jobs / leases | execution control | KEEP | robust existing control plane |
| retries / terminal failures | execution reliability | KEEP | unrelated to model architecture |
| immutable runs | provenance | KEEP | core invariant |
| analysis fingerprints | reproducibility | KEEP | core invariant |
| evaluation harness | model qualification | KEEP / GENERALIZE | broaden to v3 tasks |
| BookNLP provider transport | literary NLP runtime | BENCHMARK / DEPRECATE | preserve as v2 baseline only if superseded |
| BookNLP identity clusters | identity evidence | REPLACE | measured primary weakness |
| deterministic identity resolver | canon policy | KEEP / GENERALIZE | useful policy concepts; scorer/linker changes |
| current speaker cascade | speaker evidence | BENCHMARK | viable baseline but new joint models may win |
| BookNLP event trigger tagger | event mentions | BENCHMARK | currently strong measured component |
| dependency participant rules | event role grounding | KEEP AS BASELINE | precision-first evidence remains valuable |
| GLiNER Small v2.1 integration | typed participant challenger | REPLACE | pinned configuration failed its slot |
| relationship predicate rules | relationship observations | KEEP AS HIGH-PRECISION SIGNAL | not sufficient as full relationship model |
| temporal cue rules | temporal evidence | KEEP | valuable deterministic candidate generation |
| current life-state rules | state observations | KEEP AS HIGH-PRECISION SIGNAL | should feed new state model, not current-state truth |
| scene heuristics | boundary evidence | BENCHMARK | no adopted scene method |
| generic LLM extraction/adjudication | semantic fallback | REPLACE / NARROW | v3 uses specialist extraction + bounded fallback |
| Neo4j as future canonical graph | knowledge storage | REPLACE AS CANON | graph should be derived from Narrative IR |
| Postgres/Supabase structured persistence | application truth | KEEP / EXPAND | preferred v3 canonical persistence |
| LangGraph/agentic orchestration in critical analysis | dynamic routing | REMOVE FROM CORE | compilation is a typed DAG, not an agent problem |

## Current identity execution contract worth preserving

`identity-processor.ts` already provides strong operational behavior:

- claims durable jobs;
- reconstructs and validates normalized inputs;
- renews leases during long work;
- validates provider input fingerprints;
- separates terminal provider/data failures from transient failures;
- records resolver/config fingerprints;
- commits immutable successful runs.

The semantic resolver can change while these execution guarantees remain.

## Current benchmark assets to preserve

The worker exposes repeatable commands for:

- LitBank oracle and BookNLP baselines;
- component-level BookNLP scoring;
- stratified identity;
- whole-book evaluation;
- primary-fiction regression;
- scene annotation/structural/lexical/boundary scoring;
- dialogue deterministic/scoring;
- event deterministic/scoring/typed participant/qualifier scoring;
- relationship scoring/auditing;
- narrative timeline evidence;
- character life-state evidence.

These commands should be wrapped by a v3 comparison runner instead of discarded.

## Critical coupling to remove

The reboot should specifically eliminate these forms of coupling:

1. semantic contracts that assume BookNLP's output taxonomy;
2. canonical identity logic that treats provider clusters as the natural candidate unit;
3. downstream components consuming provider-specific IDs rather than stable S.A.G.A. IR IDs;
4. model invocation and stage orchestration being the same abstraction;
5. graph persistence and semantic truth being conflated;
6. raw generative JSON being treated as an architectural boundary.

## Inventory exit condition

This inventory is considered complete enough to begin the reboot when every production analysis path can be mapped to one of:

- preserved infrastructure;
- v2 baseline only;
- v3 replacement stage;
- explicitly deferred feature.
