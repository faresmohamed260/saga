# Phase 3 Component Benchmark Scorecard

Status: **ACTIVE — PUBLIC/SECONDARY EVIDENCE ONLY UNLESS NOTED**

This scorecard exists so later sessions can see the strongest current measured evidence for each narrative-analysis component without reconstructing it from experiment logs.

It is not a production-adoption ledger. The private modern-fiction suite remains the product promotion gate.

## Character identity

### BookNLP-small

Pinned LitBank, 100 documents, two repeatable runs.

- canonical precision: `0.4613`
- canonical recall: `0.6030`
- incorrect merge: `0.1934`
- fragmentation: `0.4607`
- linked-mention precision: `0.2158`
- linked-mention recall: `0.1161`
- cluster purity: `0.8667`

Decision: **rejected for primary character identity**.

### S.A.G.A. deterministic attachment-first resolver

Primary-fiction regression assertions exist and historical 5-document LitBank subset measurements remain useful diagnostic evidence, but the private full-book product gate is still blocked by source availability.

Decision: **current deterministic policy foundation, not yet production-qualified by the Phase-3 private suite**.

## Scene segmentation

Measured public/private-quality comparison is not yet available because the primary-suite scene annotations remain blocked by source availability.

Available infrastructure:

- exact boundary metric;
- relaxed ±1 paragraph metric;
- optimal one-to-one tolerant matching;
- structural floor;
- lexical floor;
- annotation workspace/finalization checks.

Decision: **no scene method adopted**.

## Dialogue / quote detection

Pinned LitBank, 100 documents, repeatable BookNLP result.

| Candidate | Precision | Recall | F1 |
| --- | ---: | ---: | ---: |
| S.A.G.A. deterministic quote detector | **0.8570** | 0.8555 | **0.8563** |
| BookNLP-small | 0.7706 | **0.8640** | 0.8146 |

Progress:

- deterministic detector leads BookNLP by `+0.0416` absolute F1;
- BookNLP adds only about `+0.0085` recall while losing about `-0.0864` precision.

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

BookNLP attributed-speaker mention -> LitBank gold identity mapping coverage: `0.9419`.

### Current combined challenger

Merged PR #221 preserves S.A.G.A.'s deterministic quote boundaries and maps BookNLP attributed-speaker evidence only through exact already-resolved S.A.G.A. identity spans. Provider cluster IDs are never canonical.

Its V2 conflict policy lets BookNLP win a deterministic disagreement only when the deterministic candidate came from a post-quote speech tag; pre-quote conflicts remain unresolved.

| Metric | Combined V2 | Rejected V1 | Raw BookNLP |
| --- | ---: | ---: | ---: |
| matched-known accuracy | **0.7007** | 0.5662 | 0.7830 |
| resolved-speaker accuracy | **0.8040** | 0.7946 | 0.8057 |
| end-to-end recall | **0.5994** | 0.4844 | 0.6765 |
| unresolved rate | 0.1285 | 0.2874 | **0.0282** |
| cross-character contamination | 0.1709 | **0.1464** | 0.1889 |

Progress versus rejected V1:

- matched-known accuracy: `+0.1345`;
- end-to-end recall: `+0.1150`;
- unresolved rate: `-0.1589`;
- contamination: `+0.0245`, but still `-0.0180` absolute below raw BookNLP.

V2 retains about `80.6%` of BookNLP's incremental end-to-end recall gain over the deterministic floor, versus about `51.6%` for V1.

Decision: **combined V2 is the current public speaker challenger, not a production default**. Private modern-fiction qualification and BookNLP model-weight licensing remain required.

## Event triggers

Pinned LitBank, 100 documents.

| Candidate | Precision | Recall | F1 |
| --- | ---: | ---: | ---: |
| BookNLP-small | **0.8003** | **0.7591** | **0.7791** |
| lexical Tier-0 | 0.4914 | 0.0585 | 0.1045 |

Progress:

- event-trigger F1 gain: about `+0.6746` absolute;
- precision gain: about `+0.3088` absolute;
- recall gain: about `+0.7006` absolute.

Decision: **BookNLP is the strongest measured trigger challenger**. This does not qualify negation, modality, realis, causal structure or canonical event acceptance.

## Event participant grounding

Issue #214's merged direct dependency policy uses:

- `nsubj` -> actor;
- `dobj` -> patient;
- `nsubjpass` -> patient;
- `agent -> pobj` -> actor;
- exact already-resolved S.A.G.A. identity span/structural-locator grounding;
- no dative expansion;
- no conjunction inheritance;
- no provider cluster IDs as canonical identity.

A first 100-document diagnostic initially produced zero grounded participants because the **benchmark-only LitBank oracle identity locator** did not use the provider's canonical `${stable_key}:${source_locator}` representation. That failed report is preserved with fingerprint:

`8c5adb349913ae54a65d3002209d7930833b66640a92f33d0557c301486e24f6`

The production grounding rule was not weakened. After benchmark-only locator alignment, the corrected scorer on the exact same preserved BookNLP inference measured:

- triggers: `7,445`;
- events with any grounded participant: `3,881` (`52.13%`);
- events with actor: `3,406` (`45.75%`);
- events with patient: `822` (`11.04%`);
- events with actor + patient: `347` (`4.66%`);
- actor assignments: `3,432`;
- patient assignments: `824`;
- actor-opportunity events: `4,067`;
- direct-object/passive-subject patient-candidate events: `2,476`;
- actor opportunity grounding yield: **`83.75%`**;
- direct patient-candidate grounding yield: **`33.20%`**.

Corrected trigger P/R/F1 remained exactly `0.8003 / 0.7591 / 0.7791`.

Corrected report fingerprint:

`d2392c11869bf42d92d244af3cc58b4b39d360257726f8c6dc27587ff08f2ba0`

### Patient-candidate failure-mode audit

A scorer-only 100-document audit reused the exact preserved BookNLP output and completed with `100 / 100` documents, `0` failures, passing typecheck and **`139 / 139`** analysis-worker tests.

Across `2,546` direct syntactic patient candidates in `2,476` events:

- grounded character: `824` (`32.36%`);
- same character already grounded through another mention: `4` (`0.16%`);
- **true linked-character not grounded: `0`**;
- ambiguous linked character: `17` (`0.67%`);
- **structural-locator mismatch: `0`**;
- **gold-linked person missing from identity: `0`**;
- unresolved person gold: `8` (`0.31%`);
- non-person gold: `142` (`5.58%`);
- provider non-person only: `15` (`0.59%`);
- provider person only: `33` (`1.30%`);
- no identity/entity evidence: `1,503` (`59.03%`).

The relation mix explains the low aggregate candidate yield:

- `dobj`: `2,304 / 2,546` candidates (`90.49%`), with `686` grounded characters (`29.77%`);
- `nsubjpass`: `242 / 2,546` (`9.51%`), with `138` grounded characters (`57.02%`).

Among the `1,503` candidates with no identity/entity evidence:

- `NOUN`: `1,216` (`80.90%`);
- `PRON`: `226` (`15.04%`);
- `PROPN`: only `7` (`0.47%`).

Audit report fingerprint:

`c8f36fb6a0af333c70c038e7dbe42ef94d78c3d1daf5b41fae24d6e4d412a571`

Artifact digest:

`sha256:930dfb6844be99dad6fbdf4c8fd37382eadce56d3c232946bea978c8a727fc81`

Important: these are **coverage/failure-mode diagnostics, not participant precision/recall/accuracy**. LitBank's event layer does not provide S.A.G.A.-style actor/patient gold.

Progress/decision:

- the audit found **no measured deterministic linked-character attachment bug** among direct patient candidates;
- the low aggregate candidate yield is dominated by broad `dobj` semantics, not failed canonical identity attachment;
- do **not** enable dative, conjunction inheritance or provider clusters merely to inflate coverage;
- call this denominator **direct syntactic patient candidates/opportunities**, not an expectation that every object is a character patient.

### Typed non-character participant evidence

Issue #229 adds a separate evidence layer for direct actor/patient arguments that are **not already grounded to a canonical character**. The layer does not place non-character entities into the character-specific `characterKey` contract and does not create canonical world-entity IDs.

A scorer-only 100-document diagnostic reused the same preserved BookNLP inference and completed `100 / 100` documents with `0` failures, passing typecheck and **`153 / 153`** worker tests, up from the previous `145 / 145` model-light floor.

Across `6,701` direct actor/patient candidate tokens in `5,085` candidate events:

- already grounded canonical character: `4,265` (`63.65%`);
- clean typed non-character evidence: **`146` (`2.18%`)**;
- ambiguous typed non-character: `4` (`0.06%`);
- malformed typed non-character: `0`;
- structural-locator mismatch: `0`;
- provider person only: `140` (`2.09%`);
- no provider entity evidence: **`2,146` (`32.03%`)**;
- events gaining at least one typed non-character evidence item: **`142 / 5,085` (`2.79%`)**.

Typed evidence is narrow:

- facility `90`;
- vehicle `32`;
- location `17`;
- geopolitical `6`;
- organization `1`.

The trigger benchmark is unchanged at `0.8003 / 0.7591 / 0.7791`; the scorer's full-precision F1 is `0.7791290702`, so the tiny difference from the stored four-decimal `0.7791` is rounding only.

Report fingerprint:

`bcd749129620eab5ac9f4271520e3727587a8b0f768ee4860870bdac90561b30`

Artifact digest:

`sha256:d228a6329ec4a8a41c421876750df1febde227bb3143b4ba45d17e4d92a57637`

Interpretation: BookNLP's typed non-character evidence is source-grounded and structurally clean, but **too sparse to serve as S.A.G.A.'s world-entity participant solution**. Preserve the evidence layer and keep character grounding unchanged.

These are coverage diagnostics only; LitBank does not supply non-character participant correctness gold.

### GLiNER typed-entity challenger

Issue #231 tested a separate GLiNER-only typed-span source through the same role/source contract on exact head `25e51fe6ea88d18e4d9dfd9c32b2db75f2d34ba3`.

The dedicated full-corpus workflow completed `100 / 100` documents with `0` failures, typecheck pass, and **`160 / 160`** model-light tests, up from the pre-GLiNER `153 / 153` floor. The test increase is contract/regression coverage only; it is not a model-quality gain.

Pinned challenger:

- GLiNER code commit: `cf9e5f7d9fb99158b592132a9ec7cbfabb43a9a0`;
- package: `gliner==0.2.29`;
- model: `urchade/gliner_small-v2.1`;
- model revision: `f23104c107e3c57f5c7aa36d53a9667c67b4b866`;
- code/model license: `Apache-2.0`;
- threshold: `0.5`;
- labels: person, location, facility, geopolitical entity, organization, vehicle.

On the exact same `6,701` candidate tokens / `5,085` candidate events:

| Metric | GLiNER | BookNLP typed-entity baseline |
| --- | ---: | ---: |
| clean typed non-character candidates | `47` (**0.70%**) | `146` (**2.18%**) |
| events gaining typed evidence | `44` (**0.87%**) | `142` (**2.79%**) |
| relative candidate coverage | **0.322x** | `1.000x` |
| relative event gain | **0.310x** | `1.000x` |

GLiNER loses `-1.48` percentage points of candidate coverage and `-1.93` percentage points of event-level gain versus BookNLP on this narrow direct-role diagnostic.

The `47` GLiNER participant evidence items are:

- location `18`;
- vehicle `18`;
- organization `7`;
- facility `4`;
- geopolitical `0`.

This weak role overlap is not evidence that GLiNER detects few entities overall. Across the corpus it emitted `4,514` person, `1,008` location, `187` organization, `126` vehicle, `89` facility, and `31` geopolitical detections before event-role intersection.

Runtime/resource evidence:

- GLiNER inference wall clock: `381.955 s`;
- process peak RSS: `1,581.84 MiB`;
- model artifacts: `610,657,698 bytes`;
- GPU/VRAM: none.

Trigger F1 remains `0.7791290702` (`0.7791` rounded), so there is no trigger regression.

Report fingerprint:

`322b3e51561acf51a68bd6567170d5928abe62f2aed79d3d68cd4158ede2bfdd`

Aggregate artifact:

- ID `10320402913`;
- digest `sha256:a20e650f02426bf99114e295cedaaea85cc660e756aac1209e11ff2b7da0ebfd`.

Decision: **do not adopt GLiNER as the current direct world-entity event-participant provider at this pinned configuration.** BookNLP remains the stronger measured public coverage source for this narrow role contract, but BookNLP model-weight licensing remains unverified and therefore still blocks production adoption. GLiNER's Apache-2.0 licensing removes a licensing blocker, not the quality/private-corpus gates.

Do not tune the threshold, broaden dependency roles, weaken structural matching, or silently map artifacts/objects/factions/creatures into current categories merely to improve this number. Any ontology expansion is a separate architecture and benchmark decision.

Overall participant decision: **direct dependency grounding remains the current public participant-grounding infrastructure; BookNLP typed evidence is retained as sparse optional public evidence; GLiNER is rejected for the current direct-role typed-participant slot; no production participant method is adopted.**

Detailed records:

- `docs/experiments/BOOKNLP_EVENT_DEPENDENCY_GROUNDING.md`
- `docs/experiments/BOOKNLP_EVENT_PATIENT_AUDIT.md`
- `docs/experiments/BOOKNLP_EVENT_TYPED_ENTITY_PARTICIPANTS.md`
- `docs/experiments/GLINER_TYPED_ENTITY_EVENT_PARTICIPANTS.md`

## BookNLP component repeatability / resources

Exact benchmark implementation head:

`f013f23f11d2883e8ef1f2e70f9e181e8556df08`

Two independent CPU runs produced identical semantic report fingerprint:

`e0ec94d8d1f678f98057a29117d365926a3253a4a6d5e6e0f7c96e36cab3bef9`

- run 1 wall clock: `452.68 s`
- run 2 wall clock: `293.66 s`
- run 1 peak RSS: `1123.8 MiB`
- run 2 peak RSS: `1157.2 MiB`
- BookNLP task-model artifacts: `160,398,571 bytes`
- each run: `100 / 100` documents completed, `0` failed
- heavyweight validation: `111 / 111` tests passed on both attempts

The semantic result is repeatable across these two runs; runtime is host-dependent.

The speaker V2, event-grounding and patient-audit policy scorers reuse the exact preserved native BookNLP output rather than repeating heavyweight inference for deterministic policy changes.

## Phase 3B real BookNLP runtime boundary

Issue #224 measured the real pinned BookNLP-small model through `saga-local-literary-subprocess-v1`, separate from the direct benchmark harness.

On pinned LitBank document `1023_bleak_house_brat` (`11,738` bytes / `2,319` syntax tokens):

- direct evidence fingerprint: `8be0f789a80ecf47c0b902b51e0492c17ef016023c3e215df6a4d57ff3e27add`;
- generic subprocess evidence fingerprint: the **same** value;
- semantic evidence equality: `true`;
- count equality: `true`;
- identity mentions/entities/quotes/events/syntax: `230 / 230 / 5 / 20 / 2,319`.

Measured one-shot runs:

- run A: `health()` `2.578 s`, `analyze()` `6.314 s`, peak process-tree RSS `1037.2 MiB`;
- run B (`34759959737`): `health()` `2.847 s`, `analyze()` `8.930 s`, peak process-tree RSS `1040.5 MiB`, typecheck pass, `139 / 139` tests pass.

The complete prepared offline footprint is about `439 MiB`. The stable BookNLP task-model portion is `160,398,571 bytes`; transformer/spaCy cache bookkeeping can vary slightly between preparations.

Decision from #224: **one-shot generic subprocess semantic transport is validated and remains the simple correctness/reference implementation**.

Detailed record: `docs/experiments/BOOKNLP_SUBPROCESS_RUNTIME_PROOF.md`.

### Persistent loaded BookNLP transport

Issue #226 measured a persistent local Python child using bounded stdio on exact head:

`2fa30b185cb037180f3e7762f2166067096e08c5`

Normal model-light qualification increased from `139 / 139` to **`145 / 145`** tests with six new persistence lifecycle/failure checks and no regression.

The heavyweight workflow run `34762397330` was executed twice on the exact same SHA.

Attempt 1:

- startup/health: `3.694 s`;
- analyze passes: `4.977 / 4.627 / 4.368 s`;
- median analyze: **`4.627 s`**;
- speedup vs one-shot `6.314 s`: `1.36x`;
- speedup vs one-shot `8.930 s`: `1.93x`;
- peak aggregate process-tree RSS: `1007.1 MiB`;
- artifact ID `10319696420`;
- artifact digest `sha256:4d064dd228fa6d1ec8b812de3e7b42db778aec3d76671911154da46c78badbc8`.

Attempt 2:

- startup/health: `3.134 s`;
- analyze passes: `3.039 / 2.745 / 2.853 s`;
- median analyze: **`2.853 s`**;
- speedup vs one-shot `6.314 s`: `2.21x`;
- speedup vs one-shot `8.930 s`: `3.13x`;
- peak aggregate process-tree RSS: `1028.7 MiB`;
- artifact ID `10319368057`;
- artifact digest `sha256:0e3462ed6a35ef758f1163f5cb78625df0086c40c37d9ab626ef37326e698456`.

Across both attempts:

- all **six** real persistent analyses reproduced exact evidence fingerprint `8be0f789a80ecf47c0b902b51e0492c17ef016023c3e215df6a4d57ff3e27add`;
- exact counts stayed `230 / 230 / 5 / 20 / 2,319`;
- semantic comparison fingerprint stayed `4da56c28895486da135deea7023d0f7709eea264945a0136fec8366f8dcb1a8a`;
- typecheck passed;
- `145 / 145` tests passed;
- malformed-request recovery passed;
- controlled shutdown passed;
- offline model loading passed.

Interpretation:

- repeated latency improves materially on both independent runners;
- startup/health itself is not faster than the one-shot health measurement;
- peak RSS is only slightly below one-shot and is **not** a material memory win;
- the durable benefit is avoiding repeated model/runtime recreation;
- whole cache size/hash is not a stable model identity because cache metadata is mutable.

Decision: **persistent local stdio is the preferred BookNLP runtime transport for repeated analysis**. Keep the one-shot subprocess as the correctness/reference path. Do not add a BookNLP HTTP sidecar merely for model persistence.

This transport choice changes **no model-quality/adoption result**.

Detailed record: `docs/experiments/BOOKNLP_PERSISTENT_RUNTIME_PROOF.md`.

## Adoption blockers that still apply

- private modern-fiction EPUBs are unavailable to the current execution environment;
- BookNLP model-weight license remains unverified;
- BookNLP speaker/event models use LitBank-derived literary annotations, so LitBank is not an independent product-generalization test;
- GLiNER's Apache-2.0 code/model licensing is compatible with further evaluation, but the current direct-role participant challenger lost the BookNLP public coverage baseline;
- no production speaker/event method is adopted;
- event participant accuracy remains unmeasured on suitable gold;
- scene quality remains unmeasured on the primary suite.
