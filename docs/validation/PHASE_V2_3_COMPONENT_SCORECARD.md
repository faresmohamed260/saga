# Phase 3 Component Benchmark Scorecard

Status: **ACTIVE — PUBLIC/SECONDARY EVIDENCE ONLY UNLESS NOTED**

This is the compact measured ledger for Phase-3 narrative-analysis components. It is **not** a production-adoption ledger. The private modern-fiction suite remains the product promotion gate.

## Character identity

### BookNLP-small

Pinned LitBank, 100 documents, repeatable:

- canonical precision `0.4613`;
- canonical recall `0.6030`;
- incorrect merge `0.1934`;
- fragmentation `0.4607`;
- linked-mention precision `0.2158`;
- linked-mention recall `0.1161`;
- cluster purity `0.8667`.

Decision: **rejected for primary character identity**.

### S.A.G.A. deterministic attachment-first resolver

Primary-fiction regression assertions exist, but the private whole-book product gate is blocked by source availability.

Decision: **current deterministic policy foundation, not yet production-qualified by the Phase-3 private suite**.

## Scene segmentation

Exact and ±1-paragraph metrics, one-to-one tolerant matching, structural/lexical floors and fail-closed annotation finalization are merged.

Decision: **no scene method adopted**. Primary-suite scene annotations remain unavailable.

## Dialogue / quote detection

Pinned LitBank, 100 documents.

| Candidate | Precision | Recall | F1 |
| --- | ---: | ---: | ---: |
| S.A.G.A. deterministic quote detector | **0.8570** | 0.8555 | **0.8563** |
| BookNLP-small | 0.7706 | **0.8640** | 0.8146 |

Deterministic quote detection leads BookNLP by `+0.0416` absolute F1.

Decision: **retain deterministic quote boundaries as the current measured public-gold leader**.

## Speaker attribution

Pinned LitBank, 100 documents, oracle LitBank identity used only to isolate attribution quality.

| Metric | BookNLP-small | Deterministic floor | Combined V2 |
| --- | ---: | ---: | ---: |
| matched-known accuracy | **0.7830** | 0.3265 | 0.7007 |
| resolved-speaker accuracy | **0.8057** | 0.5278 | 0.8040 |
| end-to-end recall | **0.6765** | 0.2793 | 0.5994 |
| unresolved rate | **0.0282** | 0.3815 | 0.1285 |
| cross-character contamination | 0.1889 | 0.2921 | **0.1709** |

Combined V2 preserves deterministic quote F1 `0.8563` and retains about `80.6%` of BookNLP's incremental end-to-end recall gain while keeping contamination `0.0180` below raw BookNLP.

Decision: **combined V2 is the current public speaker challenger, not a production default**.

## Event triggers

Pinned LitBank, 100 documents.

| Candidate | Precision | Recall | F1 |
| --- | ---: | ---: | ---: |
| BookNLP-small | **0.8003** | **0.7591** | **0.7791** |
| lexical Tier-0 | 0.4914 | 0.0585 | 0.1045 |

BookNLP gains about `+0.6746` absolute trigger F1.

Decision: **BookNLP is the strongest measured public trigger challenger**. This does not adopt canonical events or qualify factuality/causality.

## Event participant grounding

Merged strict direct dependency policy:

- `nsubj` -> actor;
- `dobj` -> patient;
- `nsubjpass` -> patient;
- `agent -> pobj` -> actor;
- exact linked S.A.G.A. identity / structural-locator grounding;
- no dative, conjunction inheritance or provider-cluster canonicals.

Across `7,445` BookNLP triggers:

- any grounded participant `3,881` (`52.13%`);
- events with actor `3,406` (`45.75%`);
- events with patient `822` (`11.04%`);
- actor-opportunity grounding yield **`83.75%`**;
- direct patient-candidate grounding yield **`33.20%`**;
- trigger P/R/F1 unchanged `0.8003 / 0.7591 / 0.7791`.

Patient-candidate audit across `2,546` direct candidates:

- grounded character `824` (`32.36%`);
- same character already grounded through another mention `4`;
- **true linked-character not grounded `0`**;
- ambiguous linked character `17`;
- **structural-locator mismatch `0`**;
- **gold-linked person missing from identity `0`**;
- no identity/entity evidence `1,503` (`59.03%`).

Decision: **keep strict character grounding unchanged**. Low patient yield is dominated by broad `dobj` semantics, not a measured identity-attachment bug. These are coverage/failure-mode diagnostics, not participant accuracy.

Detailed records:

- `docs/experiments/BOOKNLP_EVENT_DEPENDENCY_GROUNDING.md`
- `docs/experiments/BOOKNLP_EVENT_PATIENT_AUDIT.md`

## Typed non-character event participants

BookNLP direct-role diagnostic:

- clean typed non-character candidates **`146 / 6,701` (`2.18%`)**;
- events gaining typed evidence **`142 / 5,085` (`2.79%`)**.

GLiNER Small v2.1 on the same denominator:

- clean typed candidates `47 / 6,701` (`0.70%`);
- events gaining typed evidence `44 / 5,085` (`0.87%`);
- relative candidate/event coverage `0.322x / 0.310x` vs BookNLP.

GLiNER resources: `381.955 s`, peak RSS `1,581.84 MiB`, model artifacts `610,657,698 bytes`, no GPU.

Decision: **reject the pinned GLiNER configuration for the direct-role typed-participant slot**. Keep the provider-neutral contract and do not weaken role/locator policy to inflate coverage.

Detailed records:

- `docs/experiments/BOOKNLP_EVENT_TYPED_ENTITY_PARTICIPANTS.md`
- `docs/experiments/GLINER_TYPED_ENTITY_EVENT_PARTICIPANTS.md`

## Event semantic qualifier evidence

Strict qualifier layer on `7,445` triggers:

- any explicit cue `53` (`0.71%`);
- negated `3`;
- modalized `45`;
- conditional `5`;
- irrealis-cued `50`;
- unmarked/undetermined `7,392`.

Qualifier structural audit:

- tests `177 / 177`;
- candidate cue tokens `4,261`;
- cues in event-bearing sentences `1,528`;
- strict captures `53 / 1,528` (`3.47%`);
- deeper descendants `961`;
- other connected same-sentence `354`;
- siblings/shared head `149`;
- only `11` associated cues are uncaptured one-hop cases.

Decision: **keep the strict qualifier contract and `undetermined` default unchanged**. Do not widen from generic graph proximity without semantic-scope correctness evidence.

Detailed records:

- `docs/experiments/BOOKNLP_EVENT_SEMANTIC_QUALIFIERS.md`
- `docs/experiments/BOOKNLP_EVENT_SEMANTIC_QUALIFIER_AUDIT.md`

## Character relationship / source-order evidence

PR #238 merged explicit relationship observations + an immutable source-order ledger. Persistent relationship state and narrative-time interpretation remain separate future layers.

Pinned predicates: `love`, `hate`, `trust`, `distrust`, `marry`, `divorce`, `befriend`, `betray`.

Supported shapes:

- active: exactly one direct `nsubj` + exactly one direct `dobj`;
- passive: exactly one direct `nsubjpass` + exactly one direct `agent -> pobj`.

Both roles must ground through exactly one linked canonical identity with exact structural-locator agreement. Self-relations, reciprocity, conjunction inheritance, co-occurrence and shared-event inference are excluded.

### Foundation

- typecheck pass;
- **`188 / 188` tests pass**, up from `177 / 177` because of +11 contract tests;
- public denominator `196` predicate hits -> `48` supported binary syntax -> `23` two-character observations;
- observation yield `47.92%` of supported syntax / `11.73%` of hits;
- active/passive observations `23 / 0`;
- unique directed pairs / pair+predicate groups `20 / 20`;
- repeated-support groups `1 / 20`, with `4` observations;
- qualified observations `6 / 23`; negated/modalized/conditional `4 / 3 / 0`.

Report fingerprint `66b228428713aa6b0b59b0e36f3e50e759f533eed243e015e77c9e69e1061c78`.

### Relationship failure-mode audit — PR #240

Exact measured head `b738cb4296af2c9811d5cf18aac9aa8d44c9fe66`:

- `100 / 100` documents, `0` failures;
- typecheck pass;
- **`195 / 195` tests pass**, +7 audit tests;
- no new model inference;
- denominator preserved exactly **`196 / 48 / 23`**.

Unsupported syntax among `148` misses:

- no direct role shape `86` (`58.11%`);
- active subject only `36` (`24.32%`);
- active object only `18` (`12.16%`);
- passive subject only `5`;
- passive agent only `1`;
- multiple active subjects/objects `1 / 1`;
- exact accepted passive shapes `0`.

Grounding failures among `25` supported candidates:

- object has no linked character **`19` (`76%`)**;
- self relation `2`;
- subject ambiguous `2`;
- subject no linked character `1`;
- object ambiguous `1`;
- all structural-locator mismatch classes **`0`**.

Audit fingerprint `7e04a17d1cb5b9e0d48bc98d8a634b36e3e11ecbf5e81f9f3c54a90ec9ee69a1`; artifact ID `10325579385`, digest `sha256:5be3f8c48b931acbc3967c7261b0f17f318a840307ffa89d6be6a99774fccc5d`.

Decision: **keep the strict relationship observation policy unchanged**. No high-volume, low-risk omission was found. Do not widen predicates, dependency traversal, conjunction inheritance, co-occurrence/shared-event inference or identity rules merely to increase coverage. Do not derive persistent state from repeated source-order observations.

LitBank has no S.A.G.A.-style relationship/state gold, so these are coverage/failure-mode diagnostics, not semantic accuracy.

Detailed records:

- `docs/experiments/CHARACTER_RELATIONSHIP_STATE_EVIDENCE.md`
- `docs/experiments/CHARACTER_RELATIONSHIP_FAILURE_AUDIT.md`

## Narrative order / temporal-cue evidence

Issue #241 introduces a provider-neutral timeline evidence layer while explicitly separating deterministic narrative/source order from story-world chronology.

### Model-light qualification

- typecheck pass;
- **`202 / 202` tests pass**, up from `195 / 195` before the timeline contract;
- +7 tests are contract/regression coverage only, not chronology-quality improvement.

### Corrected 100-document diagnostic

Exact corrected scorer head `602120e8423719672a4e66da9b28ce02744bf598`; run `34784052351`, job `103796185890`:

- documents **`100 / 100`**, `0` failures;
- no new model inference; preserved BookNLP output reused;
- event candidates preserved **`7,445`**;
- trigger P/R/F1 preserved **`0.8003 / 0.7591 / 0.7791`**;
- temporal cue tokens in event-bearing sentences **`871`**;
- events with >=1 same-sentence cue **`1,856 / 7,445` (`24.93%`)**;
- events with multiple cues `338`;
- cue-to-event attachments `2,272`;
- event-bearing sentences `3,686`;
- event-bearing sentences with >=1 cue **`734 / 3,686` (`19.91%`)**;
- multi-event sentences `1,888`;
- multi-cue sentences `117`;
- multi-event + cue sentences `483`;
- resolved story-time statuses **`0`**;
- emitted story-time relations **`0`**;
- narrative-order violations **`0`**.

Cue families:

| Family | Count |
| --- | ---: |
| relative / sequence | **613** |
| deictic | **147** |
| interval / boundary | **87** |
| relative distance | **21** |
| simultaneity | **3** |

Most common cue lemmas: `then 249`, `before 158`, `now 139`, `after 135`, `soon 47`, `since 40`, `until 28`, `ago 21`, `later 21`, `during 19`.

Report fingerprint `a6590f9942f3df79cc1f122c6b97dce641495ce82e8dcbdc8bb04c8f9d217d6b`.

Artifact ID `10325862289`, digest `sha256:0c6a36edd5241eb451593dfc4f4cef7af5aa04e6267678081c4c3a5fe92a3fc8`.

Decision: **keep deterministic narrative order and unscoped same-sentence temporal-cue evidence; do not infer story-world chronology yet**. The cue statistics measure evidence availability, not semantic scope or chronology accuracy. `1,888` multi-event sentences make direct cue-to-edge conversion especially unsafe.

No production timeline default is adopted. Require suitable temporal-relation gold/private annotations or another bounded measurable hypothesis before story-time before/after/simultaneous/flashback edges.

Detailed record: `docs/experiments/NARRATIVE_TIMELINE_EVIDENCE.md`.

## BookNLP component repeatability / resources

Two independent 100-document CPU runs produced the same semantic report fingerprint `e0ec94d8d1f678f98057a29117d365926a3253a4a6d5e6e0f7c96e36cab3bef9`.

- wall clock `452.68 s` / `293.66 s`;
- peak RSS `1123.8 MiB` / `1157.2 MiB`;
- model artifacts `160,398,571 bytes`;
- each run `100 / 100` documents, `0` failures.

The speaker/event/relationship/timeline policy scorers reuse preserved native BookNLP output rather than repeat heavyweight inference for deterministic policy changes.

## Phase 3B BookNLP runtime boundary

One-shot generic subprocess proof on `1023_bleak_house_brat` exactly reproduced preserved direct BookNLP evidence:

- fingerprint `8be0f789a80ecf47c0b902b51e0492c17ef016023c3e215df6a4d57ff3e27add`;
- counts `230 / 230 / 5 / 20 / 2,319` identity mentions/entities/quotes/events/syntax;
- analyze `6.314 s` and `8.930 s`;
- peak process-tree RSS about `1.04 GiB`.

Persistent loaded stdio:

- median analyze `4.627 s` and `2.853 s` on independent attempts;
- peak RSS `1007.1 MiB` and `1028.7 MiB`;
- all six analyses exactly reproduce the one-shot fingerprint/counts;
- malformed-request recovery, offline load and controlled shutdown pass.

Decision: **persistent local stdio is preferred for repeated BookNLP analysis; one-shot remains the correctness/reference path**. This transport choice changes no provider-quality/adoption decision.

## Adoption blockers still in force

- private modern-fiction EPUBs are unavailable to the current execution environment;
- BookNLP model-weight license remains unverified;
- BookNLP speaker/event models use LitBank-derived annotations, so LitBank is not an independent product-generalization test;
- scene quality remains unmeasured on the primary suite;
- event participant correctness remains unmeasured on suitable gold;
- event qualifier correctness/factuality remains unmeasured on suitable gold;
- relationship/state correctness and persistence remain unmeasured on suitable gold;
- story-time/temporal-relation correctness and flashback identification remain unmeasured on suitable gold;
- no production speaker/event/relationship-state/timeline method is adopted.
