# Phase 3A Current State — 2026-09-12

Status: **ACTIVE HANDOFF / AUTHORITATIVE CURRENT-STATE RECORD**

This record captures the state reached during the 2026-09-12 local-first analysis rebaseline so later sessions do not reconstruct progress from chat history.

## Authoritative merged baseline

`main` at the time this record was last updated:

- `d029e465bc37d738debd1ebc8d5d831ab9249661`
- PR #201 — `Phase 3A: add dialogue and speaker benchmark foundation`

Always verify live `main` before continuing; this SHA is a handoff checkpoint, not permission to ignore newer repository work.

## Locked architecture / owner direction

Phase 3 is a first-principles rebuild of textual book analysis around the real S.A.G.A. product goal: reverse-engineer novels/series into an evidence-linked narrative model rather than produce summaries.

Locked requirements:

- textual analysis must work without paid AI APIs/subscriptions;
- Modal is reserved for image/media generation only;
- prefer deterministic/classical/local methods, then specialized local models, then bounded local generative reasoning only when cheaper tiers leave material ambiguity;
- the existing TypeScript durable worker, Supabase job/lease/run model, B2 source boundary and deterministic provenance remain the application/control-plane foundation;
- model/provider output is evidence; S.A.G.A. deterministic policy owns canonical IDs, merges, accepted/uncertain/rejected state, persistence and provenance;
- whole-book runtime/RAM/VRAM/model size/license/repeatability are part of provider selection;
- failed and rejected experiments remain in the repository ledger.

Relevant durable decisions: D-026 through D-030.

## Primary evaluation corpus

Primary product qualification remains the private/user-owned modern-fiction suite:

- *Harry Potter and the Philosopher's Stone*;
- *The Cruel Prince*;
- *Caraval*;
- ACOTAR series, with *A Court of Frost and Starlight* as the historical regression anchor.

Authoritative corpus material:

- `docs/phases/PHASE_V2_3_PRIMARY_EVALUATION_CORPUS.md`;
- `services/analysis-worker/benchmarks/whole-book-primary-fiction-suite.v1.json`;
- `docs/experiments/WHOLE_BOOK_BENCHMARK.md`.

LitBank remains **secondary public/gold regression evidence** for component isolation, reproducible metrics and comparisons. It cannot by itself promote a provider into production. If LitBank and the private modern-fiction suite disagree, the private suite governs the product decision and the discrepancy must be documented.

## Merged Phase 3A work

### Governance / experiment process

PR #186 established the local-first architecture reset. PR #187 added the first provider-neutral experiment and BookNLP evidence contracts. Benchmark hardening requires multiple completed runs before a candidate can be considered repeatable and preserves negative results.

### BookNLP identity experiment

BookNLP-small was evaluated as a broad literary baseline. Two independent 100-document LitBank runs produced the same semantic result fingerprint.

Public-regression result:

- canonical precision: `0.4613`;
- canonical recall: `0.6030`;
- incorrect-merge rate: `0.1934`;
- contamination rate: `0.4000`;
- fragmentation rate: `0.4607`;
- linked-mention precision: `0.2158`;
- linked-mention recall: `0.1161`;
- cluster purity: `0.8667`;
- runtime: about `420.2 s` first full run / `352.2 s` second full run;
- peak RAM: about `1.16 GiB`;
- model artifacts: about `153 MiB`.

Decision: **BookNLP-small is rejected for the primary character-identity role.** Its quote/speaker/event/syntax outputs remain separate candidates.

### GLiNER-small-v2.1 + F-Coref challenger

A technically valid five-document public smoke produced useful component evidence, but the fully real combined stack remains **not adoption-ready**. Any component promotion still requires primary-suite evidence.

### Whole-book benchmark foundation

PR #191 / merge `88133be6a7d20cfe02fba26f06e0dd636001fbd0` added a provider-neutral whole-book runner recording exact source SHA-256, provider/model/revision/license and command fingerprint, runtime, RAM/VRAM, output size and semantic output fingerprints. Copyrighted source remains outside Git.

### Recovered primary-fiction identity regressions

PR #192 / merge `d6c1a144d0c4b4ad82e7229c583cb22682249f07` restored provider-neutral real-book regression expectations without copyrighted prose, including Harry/Harry Potter, Dumbledore/Professor Dumbledore, Az/Azriel, Cardan/Prince Cardan, supporting-character leakage and fantasy location/group/species contamination.

Opening-prefix cases and full-book cases remain deliberately separate.

## Merged scene-analysis foundation

PR #193 merged as `201af2638b4df22aa2734b0cac934fa12b8e3e5e`.

Merged scene additions include:

- `docs/experiments/2026-09-12_CRUEL_PRINCE_HISTORICAL_ANALYSIS_BASELINE.md`;
- `docs/experiments/SCENE_SEGMENTATION_BENCHMARK.md`;
- `services/analysis-worker/benchmarks/historical-narrative-baselines.v1.json`;
- scene annotation workspace + CLI;
- exact and relaxed scene-boundary evaluator + CLI;
- deterministic structural scene baseline + CLI;
- cheap lexical scene-change baseline + CLI;
- deterministic tests for annotation, evaluation and both baselines.

The scene benchmark is paragraph-anchored and commits no copyrighted prose. It supports exact F1, relaxed `±1 paragraph` F1, optimal one-to-one tolerant matching, matched-boundary error, ambiguity zones and source/input/provider fingerprints.

Coherent branch review fixed two benchmark-integrity defects before merge:

1. the original distance-first greedy tolerant matcher could undercount valid one-to-one matches; the final evaluator uses deterministic dynamic programming to maximize valid match count before minimizing total paragraph error;
2. partially reviewed annotation workspaces could silently omit pending selected sections; finalization now fails closed until every selected section is complete.

PR #193 exact head `a3fc13dc81c6fe8f30c218c84e6a81943b7ebfb7` passed Analysis Worker CI, LitBank Oracle Baseline, Backend Architecture CI and Required Check Compatibility.

**No scene-segmentation method has been adopted.** The merged code is an experiment/measurement foundation, not a production default.

## Merged dialogue/speaker foundation

PR #201 merged as `d029e465bc37d738debd1ebc8d5d831ab9249661`.

Merged dialogue additions include:

- `docs/experiments/DIALOGUE_SPEAKER_BENCHMARK.md`;
- provider-neutral `saga-dialogue-reference-v1`, prediction and evaluation contracts;
- exact quote anchoring by section key plus absolute Unicode code-point offsets;
- paired curly and straight double-quote deterministic extraction;
- conservative same-side speech-verb + already-resolved-character attribution;
- deterministic provider/config/output fingerprints;
- quote-span precision/recall/F1;
- strict speaker accuracy on matched quotes;
- resolved-speaker accuracy;
- unresolved-speaker rate;
- cross-character contamination rate;
- end-to-end speaker recall;
- explicit `known`, `unknown` and `ambiguous` speaker annotation states;
- deterministic/adversarial tests and prediction/scoring CLIs.

The Tier-0 method intentionally does not claim to solve pronoun attribution, paragraph-spanning dialogue, nested quotations, non-dialogue quotation disambiguation or dependency-aware syntax. It returns unresolved when evidence is weak or competing candidates are too close.

An adversarial regression specifically covers `Alice said to Bob, “Hi.”` so nearest-name heuristics do not incorrectly select Bob over the character linked to the speech verb.

PR #201 exact head:

- `acf0b4cd5759901bb7a0aa65c802c4957413f9c9`

All four exact-head checks completed successfully before merge:

- SAGA v2 Analysis Worker CI — success;
- SAGA v2 LitBank Oracle Baseline — success;
- Backend Architecture CI — success;
- Required Check Compatibility — success.

**No dialogue/speaker method has been adopted.** The next speaker-specific challengers remain dependency-aware/local-NLP attribution, BookNLP quote/speaker evidence and combined candidate stabilization, followed by private-suite qualification.

## Private source availability blocker

The actual user-owned EPUB binaries remain unavailable to the current execution environment.

A 2026-09-12 File Library recheck found historical notes/scripts and old paths, but not the book binaries. Remote Desktop Commander returned no connected devices. Historical paths remain under `B:/Documents/PyCharm/graduationProject/uploads/...`.

Do not replace the private suite with public-domain novels because the EPUBs are temporarily unavailable. Continue source-neutral harness work only where it advances the architecture without pretending to satisfy the product gate.

## Historical full-analysis baseline

The old graduation prototype processed the complete *The Cruel Prince* and reported:

- `111,351` words processed;
- `35` chapters;
- `135` scenes;
- `53` unique characters;
- `55` locations;
- `128` aggregated protagonist mentions;
- `24` key causal events;
- average tension `5.49 / 10`;
- reported climax chapter `16`.

These are **coverage/reference observations, not gold truth**.

## Immediate continuation order

1. Verify live `main`, PRs/issues and mandatory governance docs before writing.
2. While primary EPUBs remain unavailable, continue source-neutral benchmark/evidence infrastructure without claiming product qualification.
3. Next unblocked slice: provider-neutral event-candidate/participant evaluation contracts plus a conservative deterministic verb-candidate floor; leave dependency-aware and BookNLP event challengers explicit.
4. When private EPUBs become reachable, generate scene/dialogue annotation workspaces for Harry Potter, The Cruel Prince, Caraval and ACOFAS and score the merged Tier-0/Tier-1 candidates.
5. Research/test stronger local methods only where cheaper baselines leave a measurable quality gap.
6. Do not select production identity, scene, speaker or event methods before repeatable primary-suite evidence exists.
7. Preserve every adoption/rejection decision and negative experiment with exact source/model/config/resource fingerprints.
8. Do not use Modal for textual analysis, add paid AI dependencies, or deploy Vercel without fresh explicit owner approval.

## References

- Phase 3 tracker: issue #185
- dialogue foundation tracker: issue #196 — completed by PR #201
- primary corpus amendment: `docs/phases/PHASE_V2_3_PRIMARY_EVALUATION_CORPUS.md`
- primary whole-book protocol: `docs/experiments/WHOLE_BOOK_BENCHMARK.md`
- recovered identity regressions: `docs/experiments/2026-09-12_PRIMARY_FICTION_REGRESSION_RECOVERY.md`
- scene protocol: `docs/experiments/SCENE_SEGMENTATION_BENCHMARK.md`
- dialogue protocol: `docs/experiments/DIALOGUE_SPEAKER_BENCHMARK.md`
- historical Cruel Prince analysis baseline: `docs/experiments/2026-09-12_CRUEL_PRINCE_HISTORICAL_ANALYSIS_BASELINE.md`
