# Narrative-order and temporal-cue evidence foundation

Status: **PUBLIC DIAGNOSTIC COMPLETE — NARRATIVE ORDER ONLY; STORY TIME UNRESOLVED**

Tracking issue: #241

This experiment adds the first provider-neutral S.A.G.A. timeline evidence layer over existing source-grounded event candidates. It deliberately separates deterministic narrative/source order from later story-world chronology.

## Contract

For each validated event candidate, the v1 contract:

- binds the event to the exact provider trigger and syntax token;
- preserves structural locator, paragraph/sentence/token coordinates and source offsets;
- assigns a deterministic `narrativeSequenceIndex` from normalized source position;
- captures pinned temporal cue tokens from the same sentence as source-grounded **unscoped evidence**;
- leaves `storyTimeStatus` as `unresolved`;
- emits no before/after/simultaneous/flashback relation;
- fingerprints configuration, normalized input and semantic output;
- fails closed on missing syntax, malformed dependency heads, input/fingerprint drift, missing trigger binding, duplicate IDs or semantic tampering.

Same-sentence cue association means only that a cue is available in the event's local evidence packet. It does **not** mean that the cue scopes that event.

## Pinned cue families

- relative / sequence: `before`, `after`, `then`, `later`, `earlier`, `previously`, `subsequently`, `eventually`, `soon`;
- simultaneity: `meanwhile`, `simultaneously`;
- deictic: `now`, `today`, `yesterday`, `tomorrow`;
- interval / boundary: `during`, `since`, `until`;
- relative distance: `ago`.

The first slice does not normalize dates or durations and does not invoke HeidelTime or a generative model.

## Model-light qualification

Exact contract/test head before the corpus scorer: `b85c7eb43374ec06fa9da345211b5a0978ce1195`.

- typecheck: **pass**;
- worker tests: **`202 / 202`**, up from `195 / 195` before the timeline contract;
- the +7 tests are regression/contract coverage only, not chronology-quality improvement.

Synthetic coverage includes deterministic ordering under shuffled provider input, same-sentence cue capture, cross-sentence isolation, multiple events sharing unscoped cues, lexicon exclusion, missing syntax/input/trigger failure and malformed-head/result-tampering failure.

## Corrected 100-document public diagnostic

Exact corrected scorer head:

`602120e8423719672a4e66da9b28ce02744bf598`

Dedicated workflow:

- run `34784052351`;
- job `103796185890`;
- LitBank attempted/completed/failed: **`100 / 100 / 0`**;
- typecheck: **pass**;
- worker tests: **`202 / 202`**;
- new model inference: **none**;
- preserved BookNLP native output reused from run `34727310506`, artifact digest `sha256:006875873bd58ec53cc976a46d000313107228f4d4dbf6c5dc450cf9b7ba4f6a`.

The first scorer run on `b19692d12ad71d667eb0a8030c39c9e925db385f` was superseded before interpretation because a scorer-only `Map` accounting bug zeroed sentence-level cue counts. The contract itself was unchanged. The metrics below come only from corrected head `602120e8...`.

### Event baseline preservation

- event candidates: **`7,445`**;
- trigger TP / FP / FN: `5,958 / 1,487 / 1,891`;
- trigger precision / recall / F1: **`0.8002686 / 0.7590776 / 0.7791291`**, rounded **`0.8003 / 0.7591 / 0.7791`**;
- duplicate predictions: `0`.

Timeline organization therefore changes neither event count nor trigger quality.

### Temporal cue availability

- unique temporal cue tokens in event-bearing sentences: **`871`**;
- events with >=1 same-sentence cue: **`1,856 / 7,445` (`24.93%`)**;
- events without cue evidence: `5,589` (`75.07%`);
- events with multiple cues: `338`;
- total cue-to-event attachments: `2,272` (`0.3052` attachments per event);
- maximum cues attached to one event: `5`;
- event-bearing sentences: `3,686`;
- event-bearing sentences with >=1 cue: **`734 / 3,686` (`19.91%`)**;
- multi-event sentences: `1,888`;
- multi-cue sentences: `117`;
- multi-event sentences with cue evidence: `483`.

### Cue families

| Family | Tokens |
| --- | ---: |
| relative / sequence | **613** |
| deictic | **147** |
| interval / boundary | **87** |
| relative distance | **21** |
| simultaneity | **3** |

Most frequent cue lemmas are `then 249`, `before 158`, `now 139`, `after 135`, `soon 47`, `since 40`, `until 28`, `ago 21`, `later 21`, `during 19`, and `yesterday 6`. Rare observed cues include `previously 2`, `meanwhile 2`, `today 2`, `simultaneously 1`, `eventually 1`.

### Invariants

- resolved story-time statuses: **`0`**;
- emitted story-time relations: **`0`**;
- narrative-order violations: **`0`**.

These are the central safety result: the first timeline layer adds useful evidence availability without converting cue presence into chronology claims.

## Reproducibility

Report fingerprint:

`a6590f9942f3df79cc1f122c6b97dce641495ce82e8dcbdc8bb04c8f9d217d6b`

Aggregate artifact:

- ID `10325862289`;
- name `saga-phase3-narrative-timeline-evidence-602120e8423719672a4e66da9b28ce02744bf598`;
- digest `sha256:0c6a36edd5241eb451593dfc4f4cef7af5aa04e6267678081c4c3a5fe92a3fc8`;
- no raw source prose/surfaces are emitted by the aggregate diagnostic.

## Interpretation

The public corpus shows that a small explicit cue lexicon supplies nearby temporal evidence for roughly one quarter of BookNLP event candidates. That is enough to justify a reusable timeline evidence contract, but nowhere near enough to infer a complete story chronology, and same-sentence presence does not prove semantic scope.

The high number of multi-event sentences (`1,888`) is especially important: blindly translating a sentence-level `before`, `after`, or `then` token into an edge would create ambiguous or contaminated relations. The v1 decision to preserve cues as unscoped evidence is therefore retained.

## Decision

**Keep the narrative-order + unscoped temporal-cue evidence foundation. Do not infer story-world chronology yet.**

No production timeline default is adopted. LitBank supplies event-trigger gold but not S.A.G.A.-style temporal-relation / flashback / story-time gold, so the cue measurements are availability diagnostics rather than chronology accuracy.

Before story-time edges are added, require suitable temporal-relation gold/private annotations or another bounded hypothesis with measurable contradiction/contamination behavior. Do not force a total chronology when only partial order is supported.

## Constraints preserved

- no paid AI API or hosted textual inference;
- no Modal textual analysis;
- no new model inference for the public diagnostic;
- normal CI remains model-light;
- no copyrighted modern-fiction prose in Git/artifacts;
- no state persistence;
- no story-time / flashback inference;
- no deployment;
- no production-adoption change.
