# Phase 3 Component Benchmark Scorecard

Status: **ACTIVE — PUBLIC/SECONDARY EVIDENCE ONLY UNLESS NOTED**

This is the compact measured ledger for Phase-3 narrative-analysis components. It is **not** a production-adoption ledger. The private modern-fiction suite remains the product promotion gate.

## Character identity

### BookNLP-small

Pinned LitBank, 100 documents, repeatable.

- canonical precision: `0.4613`
- canonical recall: `0.6030`
- incorrect merge: `0.1934`
- fragmentation: `0.4607`
- linked-mention precision: `0.2158`
- linked-mention recall: `0.1161`
- cluster purity: `0.8667`

Decision: **rejected for primary character identity**.

### S.A.G.A. deterministic attachment-first resolver

Primary-fiction regression assertions exist, but the private whole-book product gate is blocked by source availability.

Decision: **current deterministic policy foundation, not yet production-qualified by the Phase-3 private suite**.

## Scene segmentation

Available infrastructure includes exact and ±1-paragraph boundary metrics, one-to-one tolerant matching, structural/lexical floors and fail-closed annotation finalization.

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

### Component floors

| Metric | BookNLP-small | Deterministic floor |
| --- | ---: | ---: |
| matched-known accuracy | **0.7830** | 0.3265 |
| resolved-speaker accuracy | **0.8057** | 0.5278 |
| end-to-end recall | **0.6765** | 0.2793 |
| unresolved rate | **0.0282** | 0.3815 |
| cross-character contamination | **0.1889** | 0.2921 |

### Current combined challenger — PR #221

| Metric | Combined V2 | Rejected V1 | Raw BookNLP |
| --- | ---: | ---: | ---: |
| matched-known accuracy | **0.7007** | 0.5662 | 0.7830 |
| resolved-speaker accuracy | **0.8040** | 0.7946 | 0.8057 |
| end-to-end recall | **0.5994** | 0.4844 | 0.6765 |
| unresolved rate | 0.1285 | 0.2874 | **0.0282** |
| cross-character contamination | 0.1709 | **0.1464** | 0.1889 |

V2 retains about `80.6%` of BookNLP's incremental end-to-end recall gain over the deterministic floor while keeping contamination `0.0180` absolute below raw BookNLP.

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

Merged direct dependency character policy:

- `nsubj` -> actor;
- `dobj` -> patient;
- `nsubjpass` -> patient;
- `agent -> pobj` -> actor;
- exact linked S.A.G.A. identity / structural-locator grounding;
- no dative, conjunction inheritance or provider-cluster canonicals.

Corrected 100-document public diagnostic across `7,445` BookNLP triggers:

- any grounded participant: `3,881` (`52.13%`);
- events with actor: `3,406` (`45.75%`);
- events with patient: `822` (`11.04%`);
- actor-opportunity grounding yield: **`83.75%`**;
- direct patient-candidate grounding yield: **`33.20%`**;
- trigger P/R/F1 unchanged at `0.8003 / 0.7591 / 0.7791`.

Corrected report fingerprint:

`d2392c11869bf42d92d244af3cc58b4b39d360257726f8c6dc27587ff08f2ba0`

### Patient-candidate audit

Across `2,546` direct syntactic patient candidates:

- grounded character: `824` (`32.36%`);
- same character already grounded through another mention: `4`;
- **true linked-character not grounded: `0`**;
- ambiguous linked character: `17`;
- **structural-locator mismatch: `0`**;
- **gold-linked person missing from identity: `0`**;
- no identity/entity evidence: `1,503` (`59.03%`).

The no-evidence bucket is `80.90% NOUN`, `15.04% PRON`, and only `0.47% PROPN`.

Decision: **keep strict character grounding unchanged**. Low patient yield is dominated by broad `dobj` semantics, not a measured identity-attachment bug. These remain coverage/failure-mode diagnostics, not participant accuracy.

Detailed records:

- `docs/experiments/BOOKNLP_EVENT_DEPENDENCY_GROUNDING.md`
- `docs/experiments/BOOKNLP_EVENT_PATIENT_AUDIT.md`

## Typed non-character event participants

### BookNLP public evidence — PR #230

Across `6,701` direct actor/patient candidates in `5,085` candidate events:

- already grounded canonical character: `4,265` (`63.65%`);
- clean typed non-character evidence: **`146` (`2.18%`)**;
- events gaining typed evidence: **`142 / 5,085` (`2.79%`)**;
- no provider entity evidence: `2,146` (`32.03%`).

Typed evidence: facility `90`, vehicle `32`, location `17`, geopolitical `6`, organization `1`.

### GLiNER Small v2.1 challenger — PR #232

Same denominator:

| Metric | GLiNER | BookNLP typed baseline |
| --- | ---: | ---: |
| clean typed non-character candidates | `47` (**0.70%**) | `146` (**2.18%**) |
| events gaining typed evidence | `44` (**0.87%**) | `142` (**2.79%**) |
| relative candidate coverage | **0.322x** | `1.000x` |
| relative event gain | **0.310x** | `1.000x` |

GLiNER resources: `381.955 s`, peak RSS `1,581.84 MiB`, model artifacts `610,657,698 bytes`, no GPU.

Decision: **reject GLiNER at this pinned configuration for the direct-role typed-participant slot**. Keep the provider-neutral contract; do not weaken role/locator policy to inflate coverage.

Detailed records:

- `docs/experiments/BOOKNLP_EVENT_TYPED_ENTITY_PARTICIPANTS.md`
- `docs/experiments/GLINER_TYPED_ENTITY_EVENT_PARTICIPANTS.md`

## Event semantic qualifier evidence

PR #234 added source-grounded qualifier evidence over validated triggers/syntax.

100-document public diagnostic:

- tests: `168 / 168`;
- trigger count: `7,445`;
- trigger P/R/F1 unchanged at `0.8003 / 0.7591 / 0.7791`;
- any explicit cue: `53` (`0.71%`);
- negated: `3`;
- modalized: `45`;
- conditional: `5`;
- irrealis-cued: `50`;
- unmarked/undetermined: `7,392`.

Report fingerprint:

`051c172829a3864d4c9e295a6672d7fd31f6a9f5f7d5f6ba01109899a16ef803`

### Qualifier structural coverage audit — PR #236

- tests: `177 / 177`;
- unique candidate cue tokens: `4,261`;
- cues in event-bearing sentences: `1,528`;
- strict captures: `53 / 1,528` (`3.47%`);
- deeper descendants: `961` (`62.89%`);
- other connected same-sentence: `354` (`23.17%`);
- siblings/shared head: `149` (`9.75%`);
- direct-child nonqualifying: `9`;
- parent/ancestor: `2`.

Only `11 / 1,528` associated cues are uncaptured one-hop cases. Negation similarly has only `3 / 566` strict captures while `334` are deeper descendants.

Decision: **keep the strict qualifier contract and `undetermined` default unchanged**. Do not widen from generic graph proximity without semantic-scope correctness evidence.

Detailed records:

- `docs/experiments/BOOKNLP_EVENT_SEMANTIC_QUALIFIERS.md`
- `docs/experiments/BOOKNLP_EVENT_SEMANTIC_QUALIFIER_AUDIT.md`

## Character relationship / source-order state evidence

PR #238 merged an explicit relationship-observation contract and immutable source-order evidence ledger. Persistent relationship state and narrative-time interpretation remain separate future layers.

Pinned predicates:

`love`, `hate`, `trust`, `distrust`, `marry`, `divorce`, `befriend`, `betray`.

Supported shapes:

- active: exactly one direct `nsubj` + exactly one direct `dobj`;
- passive: exactly one direct `nsubjpass` + exactly one direct `agent -> pobj`.

Both roles must ground through exactly one linked canonical identity with exact structural-locator agreement. Self-relations, reciprocal inference, conjunction inheritance, co-occurrence inference and shared-event inference are excluded. Direct negation/modal/conditional cues remain attached.

### Foundation qualification

- typecheck pass;
- **`188 / 188` tests pass**, up from `177 / 177` before the contract;
- +11 tests are regression/contract coverage, not relationship-quality improvement.

### Foundation 100-document coverage diagnostic

Exact measured scorer head `bab1b898ba8aeb23fff5d9be1820b368910ee82d`; run `34782059516`, job `103790751005`.

- documents: `100 / 100`, `0` failures;
- no new model inference; preserved BookNLP syntax reused.

| Stage | Count | Yield |
| --- | ---: | ---: |
| pinned predicate-token hits | **196** | — |
| exact supported binary syntax | **48** | **24.49%** of hits |
| two-character grounded observations | **23** | **47.92%** of supported syntax |
| observations vs all predicate hits | **23** | **11.73%** |

Candidate hits: `love 95`, `marry 54`, `trust 20`, `hate 20`, `distrust 5`, `betray 2`, `divorce 0`, `befriend 0`.

Grounded observations: `love 16`, `marry 5`, `trust 2`; all others `0`.

Source-order support: `23` observations, `20` unique directed pairs, `20` pair+predicate groups, `1 / 20` repeated-support group with `4` observations.

Qualification: `6 / 23` observations carry explicit cues; negated `4`, modalized `3`, conditional `0`.

Report fingerprint:

`66b228428713aa6b0b59b0e36f3e50e759f533eed243e015e77c9e69e1061c78`

Artifact ID `10325625680`, digest `sha256:efce6db6204928799b2e8b8feefa03d45632a54491252cdf11ba8fdddbd3e73b`.

### Relationship failure-mode audit — issue #239

Exact measured head:

`b738cb4296af2c9811d5cf18aac9aa8d44c9fe66`

Dedicated run `34783109777`, job `103793595218`:

- documents: **`100 / 100`**, `0` failures;
- typecheck pass;
- **`195 / 195` tests pass**, up from `188 / 188` solely because of seven audit classifier tests;
- new model inference: **none**;
- baseline preserved exactly: **`196 predicate hits / 48 supported syntax / 23 observations`**.

#### Syntax drop-off

The `148` unsupported predicate hits are:

| Category | Count | Share of unsupported |
| --- | ---: | ---: |
| no direct role shape | **86** | **58.11%** |
| active subject only | **36** | **24.32%** |
| active object only | **18** | **12.16%** |
| passive subject only | `5` | `3.38%` |
| passive agent only | `1` | `0.68%` |
| multiple active subjects | `1` | `0.68%` |
| multiple active objects | `1` | `0.68%` |
| exact accepted passive shape | `0` | — |
| mixed / other unsupported | `0` | `0%` |

The drop-off is therefore broad absent/one-sided syntax rather than one narrow multiplicity, passive or conjunction defect.

#### Canonical-character grounding drop-off

The `25` supported syntax candidates that do not become distinct-character observations are:

| Category | Count | Share of failures |
| --- | ---: | ---: |
| object has no linked character | **19** | **76%** |
| self relation | `2` | `8%` |
| subject ambiguous | `2` | `8%` |
| subject has no linked character | `1` | `4%` |
| object ambiguous | `1` | `4%` |
| structural-locator mismatch, any side | **0** | `0%` |

Subjects are grounded in `45 / 48`; objects in `28 / 48`. The `20` no-character role positions split `PRON 10 / NOUN 10`; fine POS is `NN 9`, `PRP 5`, `WP 3`, `NNS 2`, `DT 1`.

Predicate-specific supported -> grounded counts:

- `love`: `29 -> 16`, with `12` object-no-character;
- `marry`: `9 -> 5`;
- `hate`: `6 -> 0`, **all 6 object-no-character**;
- `trust`: `3 -> 2`, one self relation;
- `betray`: `1 -> 0`, object-no-character.

Audit report fingerprint:

`7e04a17d1cb5b9e0d48bc98d8a634b36e3e11ecbf5e81f9f3c54a90ec9ee69a1`

Audit artifact ID `10325579385`, digest `sha256:5be3f8c48b931acbc3967c7261b0f17f318a840307ffa89d6be6a99774fccc5d`.

Decision: **keep the strict relationship observation policy unchanged**. The audit found no high-volume, low-risk omission: most syntax misses have no direct or only one-sided relationship-role structure, and most grounding misses are object-side arguments with no linked canonical character. Exact locator matching caused zero failures. Do not widen the predicate lexicon, dependency traversal, conjunction inheritance, co-occurrence/shared-event inference or identity rules to inflate coverage. Do not derive persistent state from repeated source-order observations.

LitBank has no S.A.G.A.-style relationship/state gold; foundation and audit numbers are coverage/failure-mode diagnostics, not semantic accuracy.

No production relationship/state default is adopted.

Detailed records:

- `docs/experiments/CHARACTER_RELATIONSHIP_STATE_EVIDENCE.md`
- `docs/experiments/CHARACTER_RELATIONSHIP_FAILURE_AUDIT.md`

## BookNLP component repeatability / resources

Two independent 100-document CPU runs produced the exact same semantic report fingerprint:

`e0ec94d8d1f678f98057a29117d365926a3253a4a6d5e6e0f7c96e36cab3bef9`

- run 1 wall clock: `452.68 s`
- run 2 wall clock: `293.66 s`
- run 1 peak RSS: `1123.8 MiB`
- run 2 peak RSS: `1157.2 MiB`
- BookNLP task-model artifacts: `160,398,571 bytes`
- each run: `100 / 100` documents, `0` failures

The speaker/event/relationship policy scorers reuse preserved native BookNLP output rather than repeating heavyweight inference for deterministic policy changes.

## Phase 3B BookNLP runtime boundary

One-shot generic subprocess proof on pinned LitBank document `1023_bleak_house_brat` produced exact semantic equality with preserved direct BookNLP evidence:

- fingerprint `8be0f789a80ecf47c0b902b51e0492c17ef016023c3e215df6a4d57ff3e27add`;
- counts `230 / 230 / 5 / 20 / 2,319` identity mentions/entities/quotes/events/syntax;
- analyze `6.314 s` and `8.930 s` on two runs;
- peak process-tree RSS about `1.04 GiB`.

Persistent loaded stdio, exact implementation head `2fa30b185cb037180f3e7762f2166067096e08c5`:

- attempt 1 median analyze `4.627 s`, peak RSS `1007.1 MiB`;
- attempt 2 median analyze `2.853 s`, peak RSS `1028.7 MiB`;
- all six analyses exactly reproduce the one-shot fingerprint/counts;
- `145 / 145` tests pass;
- malformed-request recovery, offline load and controlled shutdown pass.

Decision: **persistent local stdio is preferred for repeated BookNLP analysis; one-shot remains the correctness/reference path.** The gain is latency/model reuse, not material memory reduction. This transport choice changes no provider-quality/adoption decision.

Detailed records:

- `docs/experiments/BOOKNLP_SUBPROCESS_RUNTIME_PROOF.md`
- `docs/experiments/BOOKNLP_PERSISTENT_RUNTIME_PROOF.md`

## Adoption blockers still in force

- private modern-fiction EPUBs are unavailable to the current execution environment;
- BookNLP model-weight license remains unverified;
- BookNLP speaker/event models use LitBank-derived annotations, so LitBank is not an independent product-generalization test;
- scene quality remains unmeasured on the primary suite;
- event participant correctness remains unmeasured on suitable gold;
- event qualifier correctness/factuality remains unmeasured on suitable gold;
- relationship/state correctness, persistence and narrative-time validity remain unmeasured on suitable gold;
- no production speaker/event/relationship-state method is adopted.
