# S.A.G.A. Documentation Index

S.A.G.A. is in an owner-authorized v2 rebuild. This index separates the **active v2 source of truth** from retained **v1 historical/reference material**.

## Read First

For substantial current work, read in this order:

1. `../AGENTS.md`
2. `../PROJECT.md`
3. `DECISIONS.md`
4. the active phase contract referenced by `PROJECT.md`
5. any active owner-directed phase amendment
6. the relevant `v2/` architecture/runtime contract
7. the current validation/handoff record
8. `validation/PHASE_V2_3_COMPONENT_SCORECARD.md` for measured component state

GitHub is authoritative. Do not reconstruct project state from chat history when the repository can establish it.

## Current Phase State

**Phase 1 — Closed-Demo Main Site, Accounts & Invitations: COMPLETE.**

**Phase 2 — Story Intake & Character Identity Foundation: REPOSITORY FOUNDATION COMPLETE; ORIGINAL HOSTED-TEXT-PROVIDER PATH SUPERSEDED.**

**Phase 3 — Local-First Narrative Analysis Rebaseline: ACTIVE.**

Authoritative Phase-3 material:

- `phases/PHASE_V2_3_LOCAL_FIRST_NARRATIVE_ANALYSIS.md`
- `phases/PHASE_V2_3_PRIMARY_EVALUATION_CORPUS.md`
- `v2/ANALYSIS_ARCHITECTURE_2026.md`
- `v2/LOCAL_LITERARY_PROVIDER_PROTOCOL.md`
- `validation/PHASE_V2_3A_CURRENT_STATE_2026-09-12.md`
- `validation/PHASE_V2_3_COMPONENT_SCORECARD.md`

## Latest Phase 3 Progress

Important merged checkpoints include:

- PR #191 — whole-book benchmark + private modern-fiction suite;
- PR #192 — primary-fiction identity regressions;
- PR #193 — scene benchmark foundation;
- PR #201 — dialogue/speaker benchmark foundation;
- PR #204 — event trigger/participant benchmark foundation;
- PR #207 — generic local literary-NLP subprocess boundary;
- PR #210 — BookNLP quote/speaker/event provider adapter behind that boundary;
- PR #212 — repeatable 100-document public BookNLP component benchmark;
- PR #217 — provider-neutral syntax evidence;
- PR #221 — combined deterministic-quote + BookNLP speaker V2 challenger;
- PR #222 — dependency-aware event participant-grounding challenger;
- PR #223 — patient-candidate failure-mode audit proving zero measured linked-character attachment misses among direct patient candidates;
- PR #225 — real pinned BookNLP proof through the generic one-shot subprocess boundary;
- PR #227 — persistent loaded BookNLP stdio runtime and repeatability proof.

Current merged `main` checkpoint:

`7261d9c31adacdb80b7304f1e47808353f42e152`

Issue #226 is complete. D-032 records the measured transport decision: persistent local stdio is preferred when S.A.G.A. performs repeated BookNLP analysis; one-shot subprocess execution remains the simple correctness/reference path. This is a runtime decision only, not a BookNLP quality promotion.

## Component Benchmark Snapshot

The full ledger is `validation/PHASE_V2_3_COMPONENT_SCORECARD.md`.

### Identity

BookNLP-small is **rejected for primary character identity**: public 100-document canonical precision `0.4613`, recall `0.6030`, incorrect merge `0.1934`, fragmentation `0.4607`, linked-mention precision `0.2158`.

### Quote detection

| Candidate | Precision | Recall | F1 |
| --- | ---: | ---: | ---: |
| deterministic | **0.8570** | 0.8555 | **0.8563** |
| BookNLP-small | 0.7706 | **0.8640** | 0.8146 |

Current direction: deterministic quote boundaries remain preferred.

### Speaker attribution

Current combined V2 public challenger:

- matched-known accuracy `0.7007`;
- resolved accuracy `0.8040`;
- end-to-end recall `0.5994`;
- unresolved rate `0.1285`;
- contamination `0.1709`.

It preserves deterministic quote F1 `0.8563` and is not a production default.

### Event triggers / participants

- BookNLP trigger P/R/F1 `0.8003 / 0.7591 / 0.7791`;
- lexical Tier-0 P/R/F1 `0.4914 / 0.0585 / 0.1045`.

The conservative direct dependency-grounding policy remains the current public participant-grounding challenger. The patient audit found `0` true linked-character grounding misses among `2,546` direct syntactic patient candidates; broad `dobj` semantics, common nouns and pronouns dominate the low patient-opportunity yield. This is coverage/failure-mode evidence, not participant accuracy gold.

### Real runtime boundary

The one-shot generic subprocess path was first validated with exact semantic equality to direct BookNLP evidence. The persistent challenger then reused a loaded local Python runtime over private stdio.

Exact persistent implementation head `2fa30b185cb037180f3e7762f2166067096e08c5`, two independent heavyweight runs:

- median analyze `4.627 s` and `2.853 s`;
- one-shot analyze baselines `6.314 s` and `8.930 s`;
- peak process-tree RSS `1007.1 MiB` / `1028.7 MiB` vs one-shot `1040.5 MiB`;
- all six persistent passes reproduced exact evidence fingerprint `8be0f789a80ecf47c0b902b51e0492c17ef016023c3e215df6a4d57ff3e27add`;
- exact evidence counts remained `230` identities, `230` entities, `5` quotes, `20` event triggers, `2,319` syntax tokens;
- typecheck and **145 / 145** tests passed;
- malformed-request recovery, offline model loading and clean shutdown passed.

Decision: **persistent local stdio is preferred for repeated BookNLP analysis**. RSS improvement is small; the measured benefit is repeated latency/model reuse. Cold startup is not faster than one-shot health.

Detailed evidence:

- `experiments/BOOKNLP_SUBPROCESS_RUNTIME_PROOF.md`
- `experiments/BOOKNLP_PERSISTENT_RUNTIME_PROOF.md`

## Benchmark / Experiment Docs

- `experiments/WHOLE_BOOK_BENCHMARK.md`
- `experiments/SCENE_SEGMENTATION_BENCHMARK.md`
- `experiments/DIALOGUE_SPEAKER_BENCHMARK.md`
- `experiments/EVENT_CANDIDATE_BENCHMARK.md`
- `experiments/BOOKNLP_QUOTE_EVENT_CHALLENGER.md`
- `experiments/BOOKNLP_COMPONENT_BENCHMARK.md`
- `experiments/BOOKNLP_EVENT_DEPENDENCY_GROUNDING.md`
- `experiments/BOOKNLP_EVENT_PATIENT_AUDIT.md`
- `experiments/BOOKNLP_SUBPROCESS_RUNTIME_PROOF.md`
- `experiments/BOOKNLP_PERSISTENT_RUNTIME_PROOF.md`

## Phase 3B Local Provider Boundary

`v2/LOCAL_LITERARY_PROVIDER_PROTOCOL.md` is the active execution-boundary contract.

PR #207 provides the generic provider interface, versioned health/analyze/error protocol, no-shell bounded process execution, fingerprint validation, exact Unicode/source evidence checks and sanitized child environment. PR #210 adds a BookNLP-specific process/runner adapter while normal CI stays model-light. PR #217 adds validated provider-neutral syntax evidence.

PR #225 proves that real BookNLP survives the complete generic one-shot boundary with exact semantic equality. PR #227 proves that keeping the Python BookNLP runtime loaded behind bounded local stdio preserves the same evidence/failure/security semantics while materially lowering repeated analyze latency. D-032 therefore selects persistent stdio specifically for repeated BookNLP use.

Other local NLP providers still require their own measurements before inheriting this transport choice.

## Primary Fiction Evaluation

Primary product qualification material:

- *Harry Potter and the Philosopher's Stone*;
- *The Cruel Prince*;
- *Caraval*;
- ACOTAR series, with *A Court of Frost and Starlight* as historical regression anchor.

Primary-suite metadata/protocols:

- `../services/analysis-worker/benchmarks/whole-book-primary-fiction-suite.v1.json`;
- `experiments/WHOLE_BOOK_BENCHMARK.md`;
- `phases/PHASE_V2_3_PRIMARY_EVALUATION_CORPUS.md`.

The EPUB binaries remain unavailable to the current execution environment. Do not substitute public-domain novels as the product gate.

## Locked Analysis Direction

Owner decisions D-026 through D-030 require:

- no paid AI API/subscription dependency for required textual analysis;
- Modal reserved for image/media generation;
- deterministic/classical/local methods before bounded local generative reasoning;
- whole-book resource accounting as part of provider selection;
- outbound-only local workers using existing Supabase/B2 boundaries;
- provider output treated as evidence while S.A.G.A. owns canonical product truth.

D-031 additionally requires all S.A.G.A. Modal work to fail closed to project-owned accounts `modal-03` through `modal-41`; this does not change the text-analysis prohibition. D-032 resolves the BookNLP repeated-runtime choice to persistent local stdio.

```text
Tier 0 deterministic structure/rules
  -> Tier 1 lightweight local NLP
  -> Tier 2 specialized local model
  -> Tier 3 bounded local structured reasoning
```

## Active v2 Code

- `../apps/web/` — active Next.js product
- `../services/analysis-worker/` — active local analysis worker/control plane
- `../services/analysis-worker/src/ingestion/` — deterministic normalization
- `../services/analysis-worker/src/identity/` — provider-neutral identity evidence/resolution
- `../services/analysis-worker/src/local-analysis/` — local literary provider boundary + BookNLP normalization/runtime
- `../services/analysis-worker/src/evaluation/` — identity/whole-book/scene/dialogue/event benchmark contracts
- `../services/analysis-worker/tests/` — deterministic/model-light regressions

Do not add new v2 analysis behavior to historical pre-v2 runtime packages.

## Immediate Continuation

1. move Phase-3 work back from runtime plumbing to **new semantic capability**;
2. for events, prioritize explicit non-character entity participants and/or negation/modality/realis rather than widening character attachment rules for coverage;
3. keep public/source-neutral event work diagnostic unless suitable gold supports correctness claims;
4. when private EPUB access returns, score primary-suite scenes/dialogue/events and use those results for production decisions;
5. preserve every rejection and negative benchmark instead of patching around it.

## Hosted Resource Boundaries

- **Supabase:** existing v2 durable queue/control plane remains authoritative.
- **Backblaze B2:** source bytes remain behind scoped runtime credentials.
- **Modal:** image/media only; S.A.G.A.-owned labels are `modal-03` through `modal-41`.
- **Vercel:** manual-only; Preview/Production requires fresh explicit owner approval stating reason, deployment type and exact SHA.

## Documentation Maintenance

When v2 changes:

- current state/next action -> `../PROJECT.md`
- cross-cutting decision -> `DECISIONS.md`
- phase scope/evidence -> `phases/` and `validation/`
- component benchmark ledger -> `validation/PHASE_V2_3_COMPONENT_SCORECARD.md`
- experiment protocols/results -> `experiments/`
- textual analysis architecture -> `v2/ANALYSIS_ARCHITECTURE_2026.md`
- provider execution protocol -> `v2/LOCAL_LITERARY_PROVIDER_PROTOCOL.md`