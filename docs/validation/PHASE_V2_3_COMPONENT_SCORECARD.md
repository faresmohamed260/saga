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

Foundation:

- **`188 / 188` tests**, +11 contract tests over the previous floor;
- `196` predicate hits -> `48` supported binary syntax -> `23` two-character observations;
- observation yield `47.92%` of supported syntax / `11.73%` of hits;
- active/passive observations `23 / 0`;
- unique directed pairs / pair+predicate groups `20 / 20`;
- one repeated-support group with `4` observations;
- qualified observations `6 / 23`; negated/modalized/conditional `4 / 3 / 0`.

PR #240 failure-mode audit:

- **`195 / 195` tests**, +7 audit tests;
- denominator preserved **`196 / 48 / 23`**;
- unsupported syntax: no direct role `86`, active subject only `36`, active object only `18`, passive subject only `5`, passive agent only `1`, multiplicity `2` total;
- grounding failures: object-no-character `19 / 25` (`76%`), self `2`, subject ambiguous `2`, subject-no-character `1`, object ambiguous `1`;
- structural-locator mismatch **`0`**.

Audit fingerprint `7e04a17d1cb5b9e0d48bc98d8a634b36e3e11ecbf5e81f9f3c54a90ec9ee69a1`; artifact ID `10325579385`.

Decision: **keep the strict relationship observation policy unchanged**. Do not derive persistent relationship state or widen coverage without semantic gold.

Detailed records:

- `docs/experiments/CHARACTER_RELATIONSHIP_STATE_EVIDENCE.md`
- `docs/experiments/CHARACTER_RELATIONSHIP_FAILURE_AUDIT.md`

## Narrative order / temporal-cue evidence

PR #242 establishes deterministic source order and unscoped temporal-cue evidence while keeping story-world chronology unresolved.

Model-light qualification:

- **`202 / 202` tests**, up from `195 / 195` by +7 timeline contract tests;
- +7 is regression/contract coverage only.

Corrected 100-document diagnostic, scorer head `602120e8423719672a4e66da9b28ce02744bf598`:

- `100 / 100` documents, `0` failures;
- no new inference;
- event candidates preserved `7,445`;
- trigger P/R/F1 preserved **`0.8003 / 0.7591 / 0.7791`**;
- temporal cue tokens `871`;
- events with >=1 same-sentence cue **`1,856 / 7,445` (`24.93%`)**;
- cue-to-event attachments `2,272`;
- event-bearing sentences with cue **`734 / 3,686` (`19.91%`)**;
- multi-event sentences `1,888`;
- resolved story-time statuses / relations / narrative-order violations **`0 / 0 / 0`**.

Cue families: relative/sequence `613`, deictic `147`, interval/boundary `87`, relative-distance `21`, simultaneity `3`.

Report fingerprint `a6590f9942f3df79cc1f122c6b97dce641495ce82e8dcbdc8bb04c8f9d217d6b`; artifact ID `10325862289`.

Decision: **keep deterministic narrative order and unscoped same-sentence temporal-cue evidence; do not infer story-world chronology yet**. Cue availability is not chronology accuracy.

Detailed record: `docs/experiments/NARRATIVE_TIMELINE_EVIDENCE.md`.

## Character life-state change candidate evidence

Issue #243 introduces the first provider-neutral state-change candidate contract while structurally forbidding persistent/current state application.

Pinned first policy:

- `die` -> exactly one grounded character `actor`;
- `kill` -> exactly one grounded character `patient`;
- emitted observation only: unverified `life_status -> dead` candidate;
- preserve strict qualifier evidence and deterministic narrative sequence;
- story-time status remains `unresolved`;
- `stateApplications` must remain empty.

### Model-light qualification

- typecheck pass;
- **`210 / 210` tests pass**, up from `202 / 202` before the state-candidate contract;
- +8 tests are contract/regression coverage only, **not** state-quality improvement.

### 100-document public diagnostic

Exact scorer head `c29876a7cea3426996e4215d16a28faf1b302378`; run `34786059397`, job `103801639102`:

- documents **`100 / 100`**, `0` failures;
- no new model inference; preserved BookNLP evidence reused;
- event candidates preserved **`7,445`**;
- trigger P/R/F1 preserved **`0.8003 / 0.7591 / 0.7791`**.

Candidate funnel:

| Stage | Count | Yield |
| --- | ---: | ---: |
| `die` / `kill` trigger opportunities | **25** | `0.34%` of all events |
| unique required grounded character target | **16** | **64.00%** of opportunities |
| emitted life-state candidates | **16** | `0.21%` of all events |

Opportunity split: `die 21`, `kill 4`.

Candidate split: `die 13`, `kill 3`.

Failures: missing required target `9`, multiple required targets `0`, target missing mention evidence `0`.

Qualifier state among `16` candidates:

- candidates with any strict qualifier cue **`0`**;
- negated / modalized / irrealis-cued `0 / 0 / 0`;
- all qualifier fields undetermined **`16`**.

`undetermined` is **not affirmative realis evidence** and these candidates are not confirmed deaths.

Repeated-source diagnostics within per-document canonical scope:

- unique target characters `15`;
- repeated target characters `1`;
- repeated candidate excess `1`;
- maximum candidates for one character `2`.

Safety invariants:

- non-unresolved story-time statuses **`0`**;
- persistent/current state applications **`0`**;
- source-order violations **`0`**.

Report fingerprint `18aa7e3876ce79e1a3fb8f2d2a444ba8891da01b0de801403490c9aa5819630e`.

Artifact ID `10327100174`, digest `sha256:dc05dc44607284b57b24b4ba938c8055830d244c93b6b5da9995e21495ee0e5a`.

Decision: **keep the narrow candidate evidence contract; do not assert, apply or persist character life state**. The public opportunity set is sparse and LitBank has no state-transition, persistence, contradiction, resurrection or story-time validity gold. Do not expand the predicate set merely to increase coverage.

Detailed record: `docs/experiments/CHARACTER_LIFE_STATE_EVIDENCE.md`.

## BookNLP component repeatability / resources

Two independent 100-document CPU runs produced the same semantic report fingerprint `e0ec94d8d1f678f98057a29117d365926a3253a4a6d5e6e0f7c96e36cab3bef9`.

- wall clock `452.68 s` / `293.66 s`;
- peak RSS `1123.8 MiB` / `1157.2 MiB`;
- model artifacts `160,398,571 bytes`;
- each run `100 / 100` documents, `0` failures.

Deterministic policy scorers reuse preserved native BookNLP output instead of repeating heavyweight inference.

## Phase 3B BookNLP runtime boundary

One-shot generic subprocess proof exactly reproduced preserved direct BookNLP evidence. Persistent loaded stdio then reduced repeated-analysis latency while preserving exact semantic equality:

- one-shot analyze `6.314 s` / `8.930 s`;
- persistent median analyze `4.627 s` / `2.853 s`;
- peak process-tree RSS remains about `1 GiB`;
- malformed-request recovery, offline load and controlled shutdown pass.

Decision: **persistent local stdio is preferred for repeated BookNLP analysis; one-shot remains the correctness/reference path**. This transport decision changes no quality/adoption decision.

## Adoption blockers still in force

- private modern-fiction EPUBs are unavailable to the current execution environment;
- BookNLP model-weight license remains unverified;
- BookNLP speaker/event models use LitBank-derived annotations, so LitBank is not an independent product-generalization test;
- scene quality remains unmeasured on the primary suite;
- event participant correctness remains unmeasured on suitable gold;
- event qualifier correctness/factuality remains unmeasured on suitable gold;
- relationship correctness/persistence remains unmeasured on suitable gold;
- state-transition correctness/persistence/contradiction handling remains unmeasured on suitable gold;
- story-time/temporal-relation correctness and flashback identification remain unmeasured on suitable gold;
- no production speaker/event/relationship/state/timeline method is adopted.
