# Phase 3 Current State — 2026-09-12

Status: **ACTIVE HANDOFF / AUTHORITATIVE CURRENT-STATE RECORD**

This record captures the current local-first analysis rebaseline so later sessions do not reconstruct progress from chat history. Always verify live `main`, open PRs/issues and current checks before continuing.

## Authoritative merged baseline

`main` at this handoff:

- `a3aba893f92e9e98e29d5e6f97e08672cc80637f`
- PR #212 — repeatable BookNLP quote/speaker/event component benchmark

PR #212 exact final head:

- `280a2132d78ba8312d38f2d1f74267160830cd74`
- Required Check Compatibility — success
- S.A.G.A. v2 Analysis Worker CI — success
- S.A.G.A. v2 LitBank Oracle Baseline — success
- Backend Architecture CI — success

The earlier provider-specific runtime adapter merged in PR #210 / `9dfdd7e0c1234c021c9b2d2e5526a27b3d89bfe3`.

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
- ACOTAR series, with *A Court of Frost and Starlight* as historical regression anchor.

LitBank remains **secondary public/gold regression evidence** for component isolation and reproducibility. It cannot by itself promote a provider into production. BookNLP's speaker/event models use LitBank-derived literary annotations, so private-suite generalization evidence is especially important.

## Component benchmark scorecard

The compact authoritative ledger is:

- `docs/validation/PHASE_V2_3_COMPONENT_SCORECARD.md`

### Character identity

BookNLP-small remains **rejected for primary character identity** based on repeatable 100-document LitBank evidence:

- canonical precision `0.4613`;
- canonical recall `0.6030`;
- incorrect-merge rate `0.1934`;
- fragmentation rate `0.4607`;
- linked-mention precision `0.2158`;
- linked-mention recall `0.1161`;
- cluster purity `0.8667`.

GLiNER-small-v2.1 + F-Coref produced useful component smoke evidence but are not adoption-ready. Primary-suite qualification remains mandatory.

### Scene segmentation

PR #193 / merge `201af2638b4df22aa2734b0cac934fa12b8e3e5e` added the scene annotation workspace, exact and relaxed ±1-paragraph evaluation, optimal one-to-one tolerant matching, structural floor, lexical floor and deterministic tests.

Pre-merge review fixed greedy tolerant matching and fail-open partial annotation finalization.

**No scene method is adopted.** Primary-suite annotations remain blocked by private source availability.

### Dialogue / quote detection

PR #201 established the provider-neutral dialogue/speaker benchmark and deterministic speech-verb attribution floor. PR #212 added direct public BookNLP comparison.

100-document pinned LitBank quote result:

| Candidate | Precision | Recall | F1 |
| --- | ---: | ---: | ---: |
| S.A.G.A. deterministic quote detector | **0.8570** | 0.8555 | **0.8563** |
| BookNLP-small | 0.7706 | **0.8640** | 0.8146 |

Decision: **retain deterministic quote boundaries as the current measured public-gold leader**. BookNLP's small recall gain does not offset its precision loss.

### Speaker attribution

Speaker quality was isolated from BookNLP's rejected clustering by mapping BookNLP's attributed speaker mention span to LitBank gold identity. The deterministic floor was supplied oracle LitBank identity only to isolate attribution quality.

Measured result:

| Metric | BookNLP-small | Deterministic + oracle identity |
| --- | ---: | ---: |
| matched-known accuracy | **0.7830** | 0.3265 |
| resolved-speaker accuracy | **0.8057** | 0.5278 |
| end-to-end speaker recall | **0.6765** | 0.2793 |
| unresolved rate | **0.0282** | 0.3815 |
| cross-character contamination | **0.1889** | 0.2921 |

BookNLP speaker mention -> gold identity mapping coverage: `0.9419`.

Decision: BookNLP is a **strong restricted speaker challenger**, but `18.89%` cross-character contamination is too high for direct canonical use.

Issue #213 / PR #215 tests the benchmark-driven combined policy:

- deterministic quote spans stay authoritative;
- BookNLP speaker evidence must attach to an exact deterministic quote span;
- attributed speaker spans must resolve through S.A.G.A. identity;
- BookNLP cluster IDs never become canonical identity;
- agreement may resolve;
- provider may fill when deterministic attribution is unresolved;
- deterministic/provider disagreement becomes unresolved instead of forcing a winner.

**No speaker method is production-adopted.**

### Event triggers / participants

PR #204 established provider-neutral event-trigger/participant evaluation and the dependency-free lexical Tier-0 floor. PR #212 added direct public BookNLP trigger scoring.

| Candidate | Precision | Recall | F1 |
| --- | ---: | ---: | ---: |
| BookNLP-small | **0.8003** | **0.7591** | **0.7791** |
| lexical Tier-0 | 0.4914 | 0.0585 | 0.1045 |

BookNLP gains about `+0.6746` absolute trigger F1.

This result does **not** score S.A.G.A.-style participant grounding. It also does not qualify negation, modality, realis, state transition, causality, chronology or canonical-event acceptance.

Issue #214 tracks BookNLP-triggered dependency-aware participant grounding. **No production event method is adopted.**

## BookNLP public component repeatability / resources

Two independent 100-document GitHub-hosted CPU runs on exact benchmark implementation head `f013f23f11d2883e8ef1f2e70f9e181e8556df08` produced the exact same semantic report fingerprint:

`e0ec94d8d1f678f98057a29117d365926a3253a4a6d5e6e0f7c96e36cab3bef9`

Run 1:

- wall clock `452.68 s`;
- peak RSS `1123.8 MiB`;
- model artifacts `160,398,571 bytes`;
- `100 / 100` documents completed, zero failures.

Run 2:

- wall clock `293.66 s`;
- peak RSS `1157.2 MiB`;
- model artifacts `160,398,571 bytes`;
- `100 / 100` documents completed, zero failures.

Both heavyweight attempts passed typecheck and `111 / 111` analysis-worker tests.

Runtime varies by hosted runner; identical semantic fingerprints establish repeatable scored output for these two runs.

BookNLP model-weight licensing remains **unverified** and therefore blocks production adoption regardless of quality.

## Phase 3B local literary-NLP execution boundary

PR #207 / merge `c1dfa9f9e57545a7a3565b21e779f2514abacd04` established the generic local execution/validation boundary:

- `LocalLiteraryEvidenceProvider` interface;
- versioned `saga-local-literary-subprocess-v1` health/analyze/error protocol;
- `shell: false` process execution;
- bounded stdin/stdout/stderr/time;
- terminal/retryable provider error classification;
- exact provider/configuration/input fingerprint checks;
- exact Unicode source-span validation and structural-locator containment;
- duplicate/malformed/partial evidence rejection;
- sanitized inherited environment;
- model-light CI only.

PR #210 / merge `9dfdd7e0c1234c021c9b2d2e5526a27b3d89bfe3` instantiated the BookNLP-specific adapter/process/runner behind that boundary and reused the existing BookNLP TSV normalizer.

The production-style runner preflights required BookNLP model files before initialization because pinned BookNLP otherwise contains direct missing-model download behavior. Normal CI does not run/download the real model.

Important distinction: PR #212's 100-document real-model benchmark used the dedicated benchmark harness, not the generic subprocess provider end-to-end. Therefore the following remains open:

- real BookNLP health/analyze through `saga-local-literary-subprocess-v1` with exact preinstalled artifacts/caches;
- one-shot provider startup/runtime measurement through that boundary;
- optional persistent loopback comparison if startup cost justifies it.

Subprocess remains an experimental transport baseline, not a permanent winner.

## Private source availability blocker

The user-owned primary-suite EPUB binaries remain unavailable to the current execution environment. File Library contained historical notes/scripts and old paths, not the book binaries; Remote Desktop Commander previously returned no connected devices. Historical paths remain under `B:/Documents/PyCharm/graduationProject/uploads/...`.

Do not replace the private suite with public-domain novels. Continue source-neutral infrastructure only where it advances the architecture without pretending to satisfy the product gate.

## Historical full-analysis breadth reference

The old graduation prototype processed the complete *The Cruel Prince* and reported 111,351 words, 35 chapters, 135 scenes, 53 unique characters, 55 locations, 24 key causal events, average tension 5.49/10 and reported climax chapter 16.

These are **coverage/reference observations, not gold truth**.

## Immediate continuation order

1. Finish PR #215's combined deterministic-quote + gated BookNLP-speaker public benchmark; report whether contamination falls materially while retaining most of BookNLP's recall gain.
2. Implement and measure BookNLP-triggered dependency-aware participant grounding under #214, keeping S.A.G.A. identity/entity resolution authoritative.
3. Run the real BookNLP provider through the generic subprocess boundary with exact preinstalled artifacts/caches; measure health/startup/analyze cost and compare loopback only if justified.
4. When private EPUB access returns, generate scene/dialogue/event annotation workspaces for Harry Potter, The Cruel Prince, Caraval and ACOFAS and score all surviving candidates.
5. Adopt no identity, scene, speaker or event default before private-suite evidence, repeatability, resource cost, failure-mode review and production-compatible licensing.
6. Preserve negative experiments and exact source/model/config/resource fingerprints.
7. Do not use Modal for textual analysis, add paid AI dependencies, or deploy Vercel without fresh explicit owner approval.

## References

- Phase 3 tracker: issue #185
- BookNLP provider adapter: PR #210
- public component benchmark: PR #212
- combined speaker challenger: issue #213 / PR #215
- event grounding follow-up: issue #214
- scene protocol: `docs/experiments/SCENE_SEGMENTATION_BENCHMARK.md`
- dialogue protocol: `docs/experiments/DIALOGUE_SPEAKER_BENCHMARK.md`
- event protocol: `docs/experiments/EVENT_CANDIDATE_BENCHMARK.md`
- BookNLP component result: `docs/experiments/BOOKNLP_COMPONENT_BENCHMARK.md`
- local provider protocol: `docs/v2/LOCAL_LITERARY_PROVIDER_PROTOCOL.md`
- component scorecard: `docs/validation/PHASE_V2_3_COMPONENT_SCORECARD.md`
