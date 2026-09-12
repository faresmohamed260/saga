# Phase 3A Current State — 2026-09-12

Status: **ACTIVE HANDOFF / AUTHORITATIVE CURRENT-STATE RECORD**

This record captures the state reached during the 2026-09-12 local-first analysis rebaseline so later sessions do not reconstruct progress from chat history.

## Authoritative merged baseline

`main` at the time this handoff was written:

- `d6c1a144d0c4b4ad82e7229c583cb22682249f07`
- PR #192 — `Phase 3A: restore primary fiction regression evaluator`

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

## Primary evaluation corpus correction

The owner explicitly corrected the benchmark priority during this work.

**Primary product qualification is the private/user-owned modern-fiction suite:**

- *Harry Potter and the Philosopher's Stone*;
- *The Cruel Prince*;
- *Caraval*;
- ACOTAR series, with *A Court of Frost and Starlight* as the historical regression anchor.

The following are now authoritative:

- `docs/phases/PHASE_V2_3_PRIMARY_EVALUATION_CORPUS.md`
- `services/analysis-worker/benchmarks/whole-book-primary-fiction-suite.v1.json`
- `docs/experiments/WHOLE_BOOK_BENCHMARK.md`

LitBank remains useful only as **secondary public/gold regression evidence** for component isolation, reproducible metrics, and comparisons. It cannot by itself promote a provider into production. If LitBank and the private modern-fiction suite disagree, the private suite governs the product decision and the discrepancy must be documented.

## Merged Phase 3A work

### Governance / experiment process

PR #186 established the local-first architecture reset. PR #187 added the first provider-neutral experiment and BookNLP evidence contracts. Later benchmark hardening requires multiple completed runs before a candidate can be considered repeatable and preserves negative results.

### BookNLP identity experiment

BookNLP-small was evaluated as a broad literary baseline.

Operationally, a bounded CPU-only configuration was viable, but identity quality was not production-grade. Two independent 100-document LitBank runs produced the same semantic result fingerprint, proving repeatability of the result rather than random failure.

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

Decision: **BookNLP-small is rejected for the primary character-identity role.** Its quote/speaker/event/syntax outputs remain separate future candidates and must not be discarded merely because its identity stack lost.

### GLiNER-small-v2.1 + F-Coref challenger

A technically valid five-document public smoke was reached after environment-only dependency failures were preserved in the experiment record.

Smoke results:

- GLiNER proper-name PERSON span precision: about `0.763`;
- GLiNER proper-name PERSON span recall: about `0.657`;
- F-Coref with oracle mentions: canonical precision about `0.780`, recall about `0.889`, incorrect merges about `0.180`, fragmentation about `0.611`;
- fully real GLiNER + F-Coref -> S.A.G.A. resolver: canonical precision about `0.412`, canonical recall about `0.500`, linked-mention precision about `0.076`;
- peak RAM for the pair: about `1.99 GiB`;
- model artifacts: about `1.25 GiB`.

The combined stack was therefore **not adoption-ready**. Component decisions were intentionally separated: GLiNER mention typing and F-Coref attachment quality may still have useful roles. Any larger LitBank run is secondary evidence only and does not replace primary-suite testing.

### Whole-book benchmark foundation

PR #191 / merge `88133be6a7d20cfe02fba26f06e0dd636001fbd0` added a provider-neutral whole-book runner that records:

- exact source SHA-256;
- provider/model/revision/license and command fingerprint;
- runtime;
- peak RAM/VRAM when observable;
- output counts/bytes;
- semantic output fingerprint separate from runtime variance.

The repository never downloads or commits the copyrighted primary-suite books. Operators supply lawful user-owned EPUBs outside Git.

### Recovered primary-fiction identity regressions

PR #192 / merge `d6c1a144d0c4b4ad82e7229c583cb22682249f07` restored provider-neutral real-book regression expectations without copyrighted prose.

Recovered examples include:

- Harry Potter opening: Mr. Dursley / Mrs. Dursley / Mrs. Potter can canonicalize from story evidence, while front-matter/title text must not prematurely mint Harry; `Grunnings` remains a group; `Privet Drive` remains a location; standalone `Professor` cannot become a character;
- Harry Potter full book: `Harry` / `Harry Potter` and `Dumbledore` / `Professor Dumbledore` must merge; Hagrid/Snape/Neville must be canonical;
- ACOFAS: `Azriel` / `Az` must merge; `Illyrian Mountains`, `High Fae`, `Not Cassian`, `Night Court` cannot become character identities;
- Caraval: Julian must canonicalize; `Castillo Maldito` cannot become or attach as a character;
- The Cruel Prince: `Cardan` / `Prince Cardan` must merge; Taryn/Vivi/Valerian/Nicasia must canonicalize.

Opening-prefix cases and full-book cases are deliberately separate so prefix assertions are never misapplied to complete-book results.

## Private source availability blocker

The actual user-owned EPUB binaries are **not currently available in ChatGPT File Library**.

Historical test records identify old local paths under `B:/Documents/PyCharm/graduationProject/uploads/...`, but the connected Remote Desktop Commander currently reports no online authorized device, so those files could not be recovered during this session.

Do not replace the private suite with public-domain books merely because the EPUBs are temporarily unavailable. Continue building/qualifying provider-neutral harnesses and synthetic/reference tests, then run the primary suite once the lawful EPUBs are reachable again.

## Historical full-analysis baseline recovered

The old graduation prototype successfully analyzed the complete *The Cruel Prince*. A new Phase-3 reference record preserves those observations as **coverage evidence, not gold truth**.

Recovered historical measurements:

- `111,351` words processed;
- `35` chapters;
- `135` scenes;
- `53` unique characters;
- `55` locations;
- `128` aggregated protagonist mentions;
- `24` key causal events;
- average tension `5.49 / 10`;
- reported climax chapter `16`.

These counts must never become pass/fail targets. They establish the breadth the new local-first architecture should eventually reproduce more reliably and cheaply.

Reference files on the active WIP branch:

- `docs/experiments/2026-09-12_CRUEL_PRINCE_HISTORICAL_ANALYSIS_BASELINE.md`
- `services/analysis-worker/benchmarks/historical-narrative-baselines.v1.json`

## Active unmerged scene-analysis work

Active branch:

- `v2/phase-3a-cruel-prince-analysis-baseline`

Head at handoff:

- `cc28f37270c389f7be288f48245105d4f9fdefc7`

This branch is `21` commits ahead of the merged `main` checkpoint above and has exact-head green checks:

- SAGA v2 Analysis Worker CI — success;
- SAGA v2 LitBank Oracle Baseline — success;
- Backend Architecture CI — success;
- Required Check Compatibility — success.

Do **not** recreate this work. Inspect the branch first.

Current scene-analysis additions include:

- `docs/experiments/SCENE_SEGMENTATION_BENCHMARK.md`;
- `services/analysis-worker/src/evaluation/scene-annotation-workspace.ts`;
- `services/analysis-worker/src/evaluation/scene-annotation-cli.ts`;
- `services/analysis-worker/src/evaluation/scene-boundary-evaluation.ts`;
- `services/analysis-worker/src/evaluation/scene-boundary-cli.ts`;
- `services/analysis-worker/src/evaluation/scene-structural-baseline.ts`;
- `services/analysis-worker/src/evaluation/scene-structural-cli.ts`;
- `services/analysis-worker/src/evaluation/scene-lexical-baseline.ts`;
- `services/analysis-worker/src/evaluation/scene-lexical-cli.ts`;
- deterministic tests for annotation workspaces, boundary metrics, structural baseline and lexical baseline.

### Scene benchmark contract

A scene is a contiguous narrative span coherent across time, space, local action/objective, and active character/POV constellation.

The benchmark is paragraph-anchored and records no copyrighted prose. It supports:

- exact boundary precision/recall/F1;
- relaxed `±1 paragraph` precision/recall/F1;
- one-to-one tolerant matching;
- mean absolute matched-boundary error;
- explicit ambiguous/disputed boundary zones that are neither required gold nor false-positive traps;
- per-chapter and whole-book scene distributions/resource measurements;
- source/input/provider fingerprints.

The historical lesson is preserved: formatting-only/TextTiling-style segmentation was inconsistent, while the old LLM design's useful idea was **semantic boundary proposal + deterministic source anchoring**. Phase 3 aims to retain that quality using local measured tiers rather than paid/full-chapter LLM calls.

Initial cascade under experiment:

1. Tier 0 deterministic structural boundary baseline;
2. Tier 1 cheap lexical/local semantic-change challenger;
3. later small permissively licensed local embedding/classifier candidates if measurement justifies them;
4. bounded local semantic adjudication only for ambiguous candidate windows if cheaper tiers leave a measurable gap.

No scene approach is adopted yet.

## Immediate continuation order

1. Verify live `main`, the active scene branch, PRs and issue #185 before writing.
2. Read `AGENTS.md`, `PROJECT.md`, `docs/README.md`, `docs/DECISIONS.md`, both active Phase-3 phase documents, `docs/v2/ANALYSIS_ARCHITECTURE_2026.md`, this current-state record, and the scene benchmark protocol.
3. Continue from `v2/phase-3a-cruel-prince-analysis-baseline`; do not recreate the scene foundation.
4. Review the 21-commit scene branch as a coherent slice, fix any remaining benchmark-integrity issues, and open/qualify a PR when appropriate.
5. Preserve the private-fantasy corpus as the primary promotion gate. LitBank remains secondary diagnostics only.
6. When the EPUBs become reachable, generate annotation workspaces for Harry Potter, The Cruel Prince, Caraval and ACOFAS first, annotate representative chapter types, then compare Tier 0/Tier 1 and later candidates using exact + relaxed metrics.
7. After scene segmentation has a measured baseline, proceed independently to dialogue/speaker, event/participant, location/entity and tension experiments; do not assume the historical provider topology is correct.
8. Keep every adoption/rejection decision and negative experiment in `docs/experiments/` / validation records with exact source/model/config/resource fingerprints.
9. Do not use Modal for textual analysis, do not add paid AI dependencies, and do not deploy Vercel without the repository-required fresh explicit approval.

## References

- Phase 3 tracker: issue #185
- primary corpus amendment: `docs/phases/PHASE_V2_3_PRIMARY_EVALUATION_CORPUS.md`
- primary whole-book protocol: `docs/experiments/WHOLE_BOOK_BENCHMARK.md`
- recovered identity regressions: `docs/experiments/2026-09-12_PRIMARY_FICTION_REGRESSION_RECOVERY.md`
- active scene protocol (WIP branch): `docs/experiments/SCENE_SEGMENTATION_BENCHMARK.md`
- historical Cruel Prince analysis baseline (WIP branch): `docs/experiments/2026-09-12_CRUEL_PRINCE_HISTORICAL_ANALYSIS_BASELINE.md`
