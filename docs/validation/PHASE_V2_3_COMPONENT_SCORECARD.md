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
- **gold-linked person missing from oracle identity: `0`**;
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

Decision: **direct dependency grounding remains the current public participant-grounding challenger infrastructure, but no participant method is production-adopted**. Next event work should add genuinely new semantic capability—non-character entity participants, negation/modality/realis—or wait for suitable private actor/patient gold rather than broadening attachment rules without evidence.

Detailed records:

- `docs/experiments/BOOKNLP_EVENT_DEPENDENCY_GROUNDING.md`
- `docs/experiments/BOOKNLP_EVENT_PATIENT_AUDIT.md`

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

Second exact-head heavyweight run (`34759959737`):

- `health()` wall clock: `2.847 s`;
- one-shot generic `analyze()` wall clock: `8.930 s`;
- whole proof process-tree wall clock: `12.678 s`;
- peak aggregate process-tree RSS: `1040.5 MiB`;
- typecheck: pass;
- tests: `139 / 139` pass;
- artifact ID: `10318109017`;
- artifact digest: `sha256:dbb49b34a31e0a711052c72cc19b8bce6d628114dde96d1897b9daf9791fd8a2`.

A first independent boundary run also produced the same semantic evidence fingerprint/counts with `health()` `2.578 s`, `analyze()` `6.314 s` and `1037.2 MiB` peak process-tree RSS.

### Full offline runtime footprint

The historical `160,398,571 byte` figure is still correct for BookNLP's three task-model files. The measured complete prepared offline footprint is larger:

- BookNLP task weights: `160,398,571 bytes` (~`153.0 MiB`);
- transformer cache: `284,705,427 bytes` (~`271.5 MiB`);
- spaCy model: `15,242,123 bytes` (~`14.5 MiB`);
- total prepared artifacts: `460,346,121 bytes` (~`439.0 MiB`).

Whole cache-directory hashes varied across preparations because cache metadata/bookkeeping is mutable. They are not stable model identities. Pinned model IDs/revisions, package versions and immutable artifact/file digests remain the provenance anchors.

### Warm loaded-runtime comparison

One loaded BookNLP instance on the same document measured:

- initialization: `1.229 s`;
- warm processing: `4.505 s`, then `4.140 s`;
- repeated output stable: `true`;
- peak resident memory: `732.0 MiB`.

On the same workflow run, one-shot generic `analyze()` was about `2.16x` the second warm process pass.

Decision: **generic subprocess semantic transport is validated; one-shot process/model recreation overhead is material enough to justify a persistent loaded Python runtime challenger**. This is a runtime-architecture experiment decision only. It does not improve or promote BookNLP model quality.

Detailed record: `docs/experiments/BOOKNLP_SUBPROCESS_RUNTIME_PROOF.md`.

## Adoption blockers that still apply

- private modern-fiction EPUBs are unavailable to the current execution environment;
- BookNLP model-weight license remains unverified;
- BookNLP speaker/event models use LitBank-derived literary annotations, so LitBank is not an independent product-generalization test;
- no production speaker/event method is adopted;
- event participant accuracy remains unmeasured on suitable gold;
- scene quality remains unmeasured on the primary suite;
- the persistent loaded Python runtime still needs a measured challenger implementation before transport selection can change.
