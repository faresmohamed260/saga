# Phase 3 Current State — 2026-09-12

Status: **ACTIVE HANDOFF / AUTHORITATIVE CURRENT-STATE RECORD**

This record captures the current local-first analysis rebaseline so later sessions do not reconstruct progress from chat history. Always verify live `main` before continuing.

## Authoritative merged baseline

`main` at this handoff:

- `c1dfa9f9e57545a7a3565b21e779f2514abacd04`
- PR #207 — `Phase 3B: add local literary NLP subprocess boundary`

Qualified PR head:

- `551f22dd318740695a3e1922e56d79fcdcf09ecf`
- Required Check Compatibility — success
- SAGA v2 Analysis Worker CI — success
- Backend Architecture CI — success

No LitBank workflow was required/run for PR #207's path-triggered runtime-boundary change; do not record one as qualification evidence for that PR.

## Locked architecture / owner direction

Phase 3 rebuilds textual book analysis around S.A.G.A.'s actual product goal: reverse-engineer novels/series into an evidence-linked narrative model rather than produce summaries.

Locked requirements:

- textual analysis works without paid AI APIs/subscriptions;
- Modal is reserved for image/media generation only;
- prefer deterministic/classical/local methods, then specialized local models, then bounded local generative reasoning only when cheaper tiers leave material ambiguity;
- the existing TypeScript durable worker, Supabase job/lease/run model, B2 source boundary and deterministic provenance remain the application/control-plane foundation;
- provider output is evidence; deterministic S.A.G.A. policy owns canonical IDs, merges, accepted/uncertain/rejected state, persistence and provenance;
- whole-book runtime/RAM/VRAM/model size/license/repeatability are part of provider selection;
- failed/rejected experiments remain durable repository evidence.

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

LitBank remains **secondary public/gold regression evidence** for component isolation and reproducibility. It cannot by itself promote a provider into production. If LitBank and the private suite disagree, the private suite governs the product decision and the discrepancy must be documented.

## Character / identity evidence

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
- runtime: about `420.2 s` first run / `352.2 s` second run;
- peak RAM: about `1.16 GiB`;
- model artifacts: about `153 MiB`.

Decision: **BookNLP-small is rejected for the primary character-identity role.** Quote/speaker/event/syntax outputs remain separate candidates.

GLiNER-small-v2.1 + F-Coref produced useful five-document component smoke evidence, but the fully real combined stack is **not adoption-ready**. Any component promotion still requires primary-suite evidence.

PR #192 / merge `d6c1a144d0c4b4ad82e7229c583cb22682249f07` restored provider-neutral real-book regression expectations without copyrighted prose, including Harry/Harry Potter, Dumbledore/Professor Dumbledore, Az/Azriel, Cardan/Prince Cardan, supporting-character leakage and fantasy location/group/species contamination.

## Whole-book benchmark foundation

PR #191 / merge `88133be6a7d20cfe02fba26f06e0dd636001fbd0` added the provider-neutral whole-book runner recording exact source SHA-256, provider/model/revision/license and command fingerprint, runtime, RAM/VRAM, output size and semantic fingerprints. Copyrighted source remains outside Git.

## Scene-analysis foundation

PR #193 / merge `201af2638b4df22aa2734b0cac934fa12b8e3e5e` added:

- recovered *Cruel Prince* historical full-analysis coverage as reference evidence;
- `docs/experiments/SCENE_SEGMENTATION_BENCHMARK.md`;
- scene annotation workspace + CLI;
- exact and relaxed scene-boundary evaluator + CLI;
- deterministic structural scene floor;
- cheap lexical scene-change floor;
- deterministic tests.

Benchmark-integrity review fixed two defects before merge:

1. the original distance-first greedy relaxed matcher could undercount valid one-to-one assignments; the final evaluator maximizes match count before minimizing total paragraph error;
2. partially reviewed annotation workspaces could silently omit pending sections; finalization now fails closed until all selected sections are complete.

PR #193 exact head `a3fc13dc81c6fe8f30c218c84e6a81943b7ebfb7` passed Analysis Worker CI, LitBank Oracle Baseline, Backend Architecture CI and Required Check Compatibility.

**No scene method is adopted.** Primary-suite scene annotations and direct candidate measurement remain required.

## Dialogue / speaker foundation

PR #201 / merge `d029e465bc37d738debd1ebc8d5d831ab9249661` added:

- `docs/experiments/DIALOGUE_SPEAKER_BENCHMARK.md`;
- provider-neutral exact quote-span reference/prediction/evaluation contracts;
- paired curly/straight double-quote deterministic extraction;
- conservative speech-verb + already-resolved-character attribution;
- exact Unicode code-point source anchors and semantic fingerprints;
- quote precision/recall/F1;
- strict/resolved speaker accuracy;
- unresolved-speaker rate;
- cross-character contamination;
- end-to-end speaker recall;
- known/unknown/ambiguous speaker annotation states;
- deterministic/adversarial tests and CLIs.

The Tier-0 method intentionally does not claim pronoun attribution, paragraph-spanning dialogue, nested quotations, non-dialogue quotation disambiguation or dependency-aware syntax. It returns unresolved where evidence is weak.

PR #201 exact head `acf0b4cd5759901bb7a0aa65c802c4957413f9c9` passed all four then-active qualification gates.

**No dialogue/speaker method is adopted.** Dependency-aware attribution, BookNLP quote/speaker evidence and combined stabilization remain challengers.

## Event / participant foundation

PR #204 / merge `0b638058f355c9e0610b7d13b9364948e4aa003f` added:

- `docs/experiments/EVENT_CANDIDATE_BENCHMARK.md`;
- provider-neutral exact trigger reference/prediction/evaluation contracts;
- exact Unicode code-point source anchors/fingerprints;
- trigger precision/recall/F1;
- participant precision/recall/F1 using canonical character keys and coarse actor/patient/other roles;
- duplicate and unsupported prediction rates;
- end-to-end participant recall that includes missed known event triggers;
- explicit unknown-participant gold that stays unscored;
- a dependency-free lexical verb floor;
- bounded already-resolved-character attachment without crossing sentence-ending punctuation;
- deterministic/adversarial tests and prediction/scoring CLIs.

PR #204 exact head `6a8b39b2d1e4461a420e2ecb0122cba1fb7fbbc2` passed Analysis Worker CI, LitBank Oracle Baseline, Backend Architecture CI and Required Check Compatibility.

The merged Tier-0 event implementation is explicitly a **dependency-free lexical floor**, not the final dependency/verb solution. **No production event method is adopted.**

Open event challengers:

- POS/dependency-aware local extraction;
- BookNLP event triggers;
- combined/deduplicated candidate pass;
- stronger participant grounding and non-character participants;
- negation/modality/realis;
- private-suite annotations and qualification.

## Phase 3B local literary-NLP execution boundary

PR #207 merged as `c1dfa9f9e57545a7a3565b21e779f2514abacd04` and closed issue #206.

The merged boundary deliberately sits **behind** the TypeScript analysis/evaluation stack and does not create provider-specific application persistence.

Merged components:

- generic `LocalLiteraryEvidenceProvider` interface with health/analyze ownership;
- `saga-local-literary-subprocess-v1` protocol;
- one JSON request on stdin and one JSON response on stdout;
- `health`, `analyze` and structured `error` response kinds;
- `shell: false` process execution;
- bounded stdin/stdout/stderr and timeout;
- explicit terminal/retryable provider failure classification;
- exact configured provider descriptor and configuration fingerprint checks;
- exact normalized-input fingerprint checks;
- fail-closed provider-neutral evidence validation for identity, typed entity, quote/speaker and event evidence;
- exact Unicode code-point spans checked against source text;
- structural-locator containment checks;
- duplicate evidence-ID rejection;
- partial quote-speaker spans rejected;
- malformed provider response descriptors converted into explicit terminal provider errors;
- code-point-to-code-unit source index built once per result rather than rescanning the entire book for each evidence span;
- sanitized inherited environment; ambient worker Supabase/B2/arbitrary `SAGA_*` secrets do not flow to model subprocesses automatically;
- model-light Node fixture CI only;
- protocol/security/operational contract in `docs/v2/LOCAL_LITERARY_PROVIDER_PROTOCOL.md`.

This slice intentionally does **not**:

- choose subprocess permanently over loopback HTTP;
- run/adopt BookNLP or another heavyweight model in normal CI;
- create a new durable narrative-analysis job/schema;
- promote any provider;
- satisfy private-suite product quality.

A persistent loopback provider remains a valid alternative. Compare it only after a real provider produces startup/runtime measurements worth comparing.

## Private source availability blocker

The user-owned primary-suite EPUB binaries remain unavailable to the current execution environment.

A 2026-09-12 File Library recheck found historical notes/scripts and old paths, but not the book binaries. Remote Desktop Commander returned no connected devices. Historical paths remain under `B:/Documents/PyCharm/graduationProject/uploads/...`.

Do not replace the private suite with public-domain novels. Continue source-neutral infrastructure only where it advances the architecture without pretending to satisfy the product gate.

## Historical full-analysis baseline

The old graduation prototype processed the complete *The Cruel Prince* and reported:

- `111,351` words;
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

1. Verify live `main`, open PRs/issues and mandatory governance docs before writing.
2. Use the merged local literary provider boundary to instantiate a real provider experiment without adding heavyweight downloads to normal CI.
3. Prefer reusing `src/local-analysis/booknlp-output.ts` for BookNLP quote/speaker/event evidence rather than inventing a second BookNLP evidence contract.
4. Keep executable/model/revision/license/configuration fingerprints and runtime/resource measurements explicit.
5. Do not wire an experimental local provider into durable application jobs before benchmark evidence justifies it.
6. Compare one-shot subprocess versus persistent loopback only after real startup/runtime evidence makes the comparison useful.
7. When private EPUBs become reachable, generate scene/dialogue/event annotation workspaces for Harry Potter, The Cruel Prince, Caraval and ACOFAS and score merged floors/challengers.
8. Do not select production identity, scene, speaker or event methods before repeatable private-suite evidence exists.
9. Preserve every adoption/rejection decision and negative experiment with exact source/model/config/resource fingerprints.
10. Do not use Modal for textual analysis, add paid AI dependencies, or deploy Vercel without fresh explicit owner approval.

## References

- Phase 3 tracker: issue #185
- dialogue foundation: issue #196 / PR #201
- event foundation: issue #203 / PR #204
- local provider boundary: issue #206 / PR #207
- primary corpus amendment: `docs/phases/PHASE_V2_3_PRIMARY_EVALUATION_CORPUS.md`
- primary whole-book protocol: `docs/experiments/WHOLE_BOOK_BENCHMARK.md`
- recovered identity regressions: `docs/experiments/2026-09-12_PRIMARY_FICTION_REGRESSION_RECOVERY.md`
- scene protocol: `docs/experiments/SCENE_SEGMENTATION_BENCHMARK.md`
- dialogue protocol: `docs/experiments/DIALOGUE_SPEAKER_BENCHMARK.md`
- event protocol: `docs/experiments/EVENT_CANDIDATE_BENCHMARK.md`
- local provider protocol: `docs/v2/LOCAL_LITERARY_PROVIDER_PROTOCOL.md`
- historical Cruel Prince baseline: `docs/experiments/2026-09-12_CRUEL_PRINCE_HISTORICAL_ANALYSIS_BASELINE.md`
