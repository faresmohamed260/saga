# Phase 3A Current State — 2026-09-12

Status: **ACTIVE HANDOFF / AUTHORITATIVE CURRENT-STATE RECORD**

This record captures the state reached during the 2026-09-12 local-first analysis rebaseline so later sessions do not reconstruct progress from chat history.

## Authoritative merged baseline

`main` at the time this record was last updated:

- `201af2638b4df22aa2734b0cac934fa12b8e3e5e`
- PR #193 — `Phase 3A: restore narrative breadth baseline and scene benchmark`

Always verify live `main` before continuing; this SHA is a handoff checkpoint, not permission to ignore newer repository work.

## Locked architecture / owner direction

Phase 3 is a first-principles rebuild of textual book analysis around the real S.A.G.A. product goal: reverse-engineer novels/series into an evidence-linked narrative model rather than produce summaries.

Locked requirements:

- textual analysis must work without paid AI APIs/subscriptions;
- Modal is reserved for image/media generation only;
- prefer deterministic/classical/local methods, then specialized local models, then bounded local generative reasoning only when cheaper tiers leave material ambiguity;
- the existing TypeScript durable worker, Supabase job/lease/run model, B2 source boundary, and deterministic provenance remain the application/control-plane foundation;
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

PR #186 established the local-first architecture reset. PR #187 added the first provider-neutral experiment and BookNLP evidence contracts. Later benchmark hardening requires multiple completed runs before a candidate can be considered repeatable and preserves negative results.

### BookNLP identity experiment

BookNLP-small was evaluated as a broad literary baseline. Two independent 100-document LitBank runs produced the same semantic result fingerprint, proving repeatability of the result rather than random failure.

Full public-regression result:

- canonical precision: `0.4613`;
- canonical recall: `0.6030`;
- incorrect-merge rate: `0.1934`;
- contamination rate: `0.4000`;
- fragmentation rate: `0.4607`;
- linked-mention precision: `0.2158`;
- linked-mention recall: `0.1161`;
- cluster purity: `0.8667`;
- runtime: about `420.2 s` first full run / `352.2 s` second full run on the tested CPU runner;
- peak RAM: about `1.16 GiB`;
- BookNLP model artifacts: about `153 MiB`.

Decision: **BookNLP-small is rejected for the primary character-identity role.** Its quote/speaker/event/syntax outputs remain separate future candidates.

### GLiNER-small-v2.1 + F-Coref challenger

A technically valid five-document public smoke produced:

- GLiNER proper-name PERSON span precision: about `0.763`;
- GLiNER proper-name PERSON span recall: about `0.657`;
- F-Coref with oracle mentions: canonical precision about `0.780`, recall about `0.889`, incorrect merges about `0.180`, fragmentation about `0.611`;
- fully real GLiNER + F-Coref -> S.A.G.A. resolver: canonical precision about `0.412`, canonical recall about `0.500`, linked-mention precision about `0.076`;
- peak RAM for the pair: about `1.99 GiB`;
- model artifacts: about `1.25 GiB`.

The combined stack is **not adoption-ready**. Component decisions remain separate and require primary-suite evidence.

### Whole-book benchmark foundation

PR #191 / merge `88133be6a7d20cfe02fba26f06e0dd636001fbd0` added a provider-neutral whole-book runner recording exact source SHA-256, provider/model/revision/license and command fingerprint, runtime, RAM/VRAM, output size and semantic output fingerprints. Copyrighted source remains outside Git.

### Recovered primary-fiction identity regressions

PR #192 / merge `d6c1a144d0c4b4ad82e7229c583cb22682249f07` restored provider-neutral real-book regression expectations without copyrighted prose, including Harry/Harry Potter, Dumbledore/Professor Dumbledore, Az/Azriel, Cardan/Prince Cardan, supporting-character leakage and fantasy location/group/species contamination.

Opening-prefix cases and full-book cases remain deliberately separate.

## Merged scene-analysis foundation

PR #193 merged as `201af2638b4df22aa2734b0cac934fa12b8e3e5e` after the scene branch first reconciled the latest `main` documentation/governance without rewriting its existing work.

Merged scene additions include:

- `docs/experiments/2026-09-12_CRUEL_PRINCE_HISTORICAL_ANALYSIS_BASELINE.md`;
- `docs/experiments/SCENE_SEGMENTATION_BENCHMARK.md`;
- `services/analysis-worker/benchmarks/historical-narrative-baselines.v1.json`;
- scene annotation workspace + CLI;
- exact and relaxed scene-boundary evaluator + CLI;
- deterministic structural scene baseline + CLI;
- cheap lexical scene-change baseline + CLI;
- deterministic tests for annotation, evaluation and both baselines.

### Scene benchmark contract

A scene is a contiguous narrative span coherent across time, space/location, local action/objective and active character/POV constellation.

The benchmark is paragraph-anchored and commits no copyrighted prose. It supports:

- exact boundary precision/recall/F1;
- relaxed `±1 paragraph` precision/recall/F1;
- one-to-one tolerant matching;
- mean absolute matched-boundary error;
- explicit ambiguous/disputed boundary zones that are neither required gold nor false-positive traps;
- source/input/provider fingerprints.

Historical design evidence remains: the old LLM design's useful idea was **semantic boundary proposal + deterministic source anchoring**. Phase 3 aims to retain that strength using measured local tiers rather than paid/full-chapter LLM calls.

Initial cascade under experiment:

1. Tier 0 deterministic structural boundary baseline;
2. Tier 1 cheap lexical/local semantic-change challenger;
3. later small permissively licensed local embedding/classifier candidates if measurements justify them;
4. bounded local semantic adjudication only for ambiguous candidate windows if cheaper tiers leave a measurable gap.

### Integrity findings fixed before PR #193 merge

Coherent branch review found two benchmark-integrity issues and fixed both before qualification:

1. **Relaxed matching cardinality:** the first tolerant scorer greedily consumed the shortest-distance pair. That can undercount a valid one-to-one assignment, for example gold internal boundaries `[1,2]` versus predictions `[2,3]` at tolerance `±1`. The final evaluator uses deterministic dynamic programming to maximize valid match count first and minimize total paragraph error second.
2. **Partial annotation finalization:** the first finalizer rejected a wholly pending workspace but could silently omit pending sections when another selected section was marked complete. Finalization now fails closed until every selected section is complete.

Regression tests cover both failure modes.

### Exact-head qualification

PR #193 head:

- `a3fc13dc81c6fe8f30c218c84e6a81943b7ebfb7`

All four exact-head checks completed successfully before merge:

- SAGA v2 Analysis Worker CI — success;
- SAGA v2 LitBank Oracle Baseline — success;
- Backend Architecture CI — success;
- Required Check Compatibility — success.

**No scene-segmentation method has been adopted.** The merged code is an experiment/measurement foundation, not a production default.

## Private source availability blocker

The actual user-owned EPUB binaries remain unavailable to the current execution environment.

A 2026-09-12 File Library recheck found historical notes/scripts and the old paths, but not the book binaries. A Remote Desktop Commander recheck returned no connected devices. Historical paths remain under `B:/Documents/PyCharm/graduationProject/uploads/...`.

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
2. When the private EPUBs become reachable, generate scene annotation workspaces for Harry Potter, The Cruel Prince, Caraval and ACOFAS first.
3. Annotate representative chapters covering dialogue-heavy scenes, action/fights, travel/location changes, explicit and subtle time jumps, flashbacks/recollections, POV/focal changes, decorative breaks and long scenes that should not be over-segmented.
4. Compare the merged structural and lexical baselines first using exact + relaxed metrics and resource measurements.
5. Research/test stronger local scene methods only if cheaper baselines leave a measurable quality gap.
6. Do not select a production scene method before repeatable primary-suite evidence exists.
7. After scene segmentation has a measured baseline, proceed independently to dialogue/speaker attribution, event/participant extraction, location/entity extraction, tension, relationships/state, timeline and causality.
8. Preserve every adoption/rejection decision and negative experiment with exact source/model/config/resource fingerprints.
9. Do not use Modal for textual analysis, add paid AI dependencies, or deploy Vercel without fresh explicit owner approval.

## References

- Phase 3 tracker: issue #185
- primary corpus amendment: `docs/phases/PHASE_V2_3_PRIMARY_EVALUATION_CORPUS.md`
- primary whole-book protocol: `docs/experiments/WHOLE_BOOK_BENCHMARK.md`
- recovered identity regressions: `docs/experiments/2026-09-12_PRIMARY_FICTION_REGRESSION_RECOVERY.md`
- scene protocol: `docs/experiments/SCENE_SEGMENTATION_BENCHMARK.md`
- historical Cruel Prince analysis baseline: `docs/experiments/2026-09-12_CRUEL_PRINCE_HISTORICAL_ANALYSIS_BASELINE.md`
