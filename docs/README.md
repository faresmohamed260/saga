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

Important merged checkpoints:

- PR #191 / `88133be6a7d20cfe02fba26f06e0dd636001fbd0` — whole-book benchmark + private modern-fiction suite;
- PR #192 / `d6c1a144d0c4b4ad82e7229c583cb22682249f07` — primary-fiction identity regressions;
- PR #193 / `201af2638b4df22aa2734b0cac934fa12b8e3e5e` — scene benchmark foundation;
- PR #201 / `d029e465bc37d738debd1ebc8d5d831ab9249661` — dialogue/speaker benchmark foundation;
- PR #204 / `0b638058f355c9e0610b7d13b9364948e4aa003f` — event trigger/participant benchmark foundation;
- PR #207 / `c1dfa9f9e57545a7a3565b21e779f2514abacd04` — generic local literary-NLP subprocess boundary;
- PR #210 / `9dfdd7e0c1234c021c9b2d2e5526a27b3d89bfe3` — BookNLP quote/speaker/event provider adapter behind that boundary;
- PR #212 / `a3aba893f92e9e98e29d5e6f97e08672cc80637f` — repeatable 100-document public BookNLP component benchmark.

PR #212 final head `280a2132d78ba8312d38f2d1f74267160830cd74` passed Required Check Compatibility, Analysis Worker CI, LitBank Oracle Baseline and Backend Architecture CI.

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

With oracle LitBank identity used only to isolate attribution quality:

- BookNLP matched-known accuracy `0.7830` vs deterministic `0.3265`;
- end-to-end recall `0.6765` vs `0.2793`;
- contamination `0.1889` vs `0.2921`;
- unresolved rate `0.0282` vs `0.3815`.

BookNLP is a strong speaker challenger but is **not adopted**. Issue #213 / PR #215 test a combined deterministic-quote + confidence-gated BookNLP-speaker policy intended to reduce contamination without surrendering the recall gain.

### Event triggers

- BookNLP P/R/F1 `0.8003 / 0.7591 / 0.7791`;
- lexical Tier-0 P/R/F1 `0.4914 / 0.0585 / 0.1045`.

BookNLP improves trigger F1 by about `+0.6746`. Participant grounding is not scored by this LitBank layer and remains open under issue #214.

### Repeatability / resources

Two independent 100-document CPU runs produced identical semantic fingerprint:

`e0ec94d8d1f678f98057a29117d365926a3253a4a6d5e6e0f7c96e36cab3bef9`

- run 1: `452.68 s`, `1123.8 MiB` peak RSS;
- run 2: `293.66 s`, `1157.2 MiB` peak RSS;
- model artifacts: `160,398,571 bytes`;
- `100 / 100` documents, zero failures on both runs;
- `111 / 111` analysis-worker tests passed on both heavyweight attempts.

BookNLP model-weight licensing remains unverified and blocks production adoption.

## Benchmark / Experiment Docs

- `experiments/WHOLE_BOOK_BENCHMARK.md`
- `experiments/SCENE_SEGMENTATION_BENCHMARK.md`
- `experiments/DIALOGUE_SPEAKER_BENCHMARK.md`
- `experiments/EVENT_CANDIDATE_BENCHMARK.md`
- `experiments/BOOKNLP_QUOTE_EVENT_CHALLENGER.md`
- `experiments/BOOKNLP_COMPONENT_BENCHMARK.md`

## Phase 3B Local Provider Boundary

`v2/LOCAL_LITERARY_PROVIDER_PROTOCOL.md` is the active execution-boundary contract.

PR #207 provides the generic provider interface, versioned health/analyze/error protocol, no-shell bounded process execution, fingerprint validation, exact Unicode/source evidence checks and sanitized child environment. PR #210 adds a BookNLP-specific process/runner adapter while normal CI stays model-light.

Important distinction: PR #212's real 100-document benchmark used the dedicated benchmark harness. A real BookNLP run **through the generic subprocess boundary** remains a separate open measurement. Subprocess also remains an experimental transport baseline; persistent loopback HTTP can be compared if startup/runtime evidence warrants it.

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
- `../services/analysis-worker/src/local-analysis/` — local literary provider boundary + BookNLP normalization
- `../services/analysis-worker/src/evaluation/` — identity/whole-book/scene/dialogue/event benchmark contracts
- `../services/analysis-worker/tests/` — deterministic/model-light regressions

Do not add new v2 analysis behavior to historical pre-v2 runtime packages.

## Immediate Continuation

1. measure PR #215's combined speaker policy against the same pinned 100-document component gold;
2. implement/measure dependency-aware event participant grounding under #214;
3. execute real BookNLP through the generic subprocess boundary with preinstalled exact artifacts/caches;
4. when private EPUB access returns, score primary-suite scenes/dialogue/events and use those results for production decisions;
5. preserve every rejection and negative benchmark instead of patching around it.

## Hosted Resource Boundaries

- **Supabase:** existing v2 durable queue/control plane remains authoritative.
- **Backblaze B2:** source bytes remain behind scoped runtime credentials.
- **Modal:** image/media only.
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
