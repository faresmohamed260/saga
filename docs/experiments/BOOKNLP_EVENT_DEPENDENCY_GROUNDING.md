# BookNLP Event Dependency Grounding Challenger

Status: **PUBLIC COVERAGE CHALLENGER MEASURED — PARTICIPANT QUALITY NOT YET SCORED**

This experiment evaluates whether BookNLP-small literary event triggers plus provider-neutral dependency evidence can support deterministic S.A.G.A. actor/patient attachment without allowing BookNLP coreference clusters to become canonical identities.

Pinned LitBank remains secondary public/gold evidence. Its event layer supplies trigger labels but does not supply S.A.G.A.-style actor/patient gold, so this experiment measures trigger quality and grounding coverage/yield only. It does **not** establish participant precision, recall, or accuracy and cannot promote an event method into production.

## Policy under test

For each source-anchored BookNLP event trigger:

- direct `nsubj` child -> actor candidate;
- direct `dobj` child -> patient candidate;
- direct `nsubjpass` child -> patient candidate;
- `agent -> pobj` chain -> actor candidate;
- syntax candidates attach only through one already-linked S.A.G.A. identity whose source span covers the syntax token;
- ambiguous identity coverage remains unresolved;
- structural source locator must agree;
- `dative` is deliberately excluded from the first policy;
- conjunction inheritance is deliberately excluded from the first policy;
- BookNLP provider/coreference cluster IDs are never canonical participant identity.

The trigger itself remains provider evidence rather than an accepted canonical narrative event.

## Corpus and reused inference

- repository: `dbamman/litbank`
- commit: `3e50db0ffc033d7ccbb94f4d88f6b99210328ed8`
- license: CC BY 4.0
- documents attempted/completed/failed: `100 / 100 / 0`
- preserved BookNLP source run: `34727310506`
- source head: `f77af8bcab488fd1069e9c6e8ed4970842c78692`
- native artifact: `saga-phase3-booknlp-native-output-f77af8bcab488fd1069e9c6e8ed4970842c78692`
- native artifact SHA-256: `006875873bd58ec53cc976a46d000313107228f4d4dbf6c5dc450cf9b7ba4f6a`

The grounding scorers reused those exact native outputs. No BookNLP model inference was rerun for policy or benchmark-fixture changes.

## First diagnostic: measured fixture failure

The first 100-document diagnostic completed successfully at the workflow level but produced zero grounded participants across all `7,445` event triggers despite substantial syntax opportunities:

- actor-opportunity events: `4,067`;
- patient-opportunity events: `2,476`;
- grounded participants: `0`;
- trigger P/R/F1 remained `0.8003 / 0.7591 / 0.7791`;
- report fingerprint: `8c5adb349913ae54a65d3002209d7930833b66640a92f33d0557c301486e24f6`.

This result is preserved as a failed diagnostic rather than discarded.

### Root cause

The strict production grounding rule requires identity evidence and syntax evidence to share the same structural locator. That rule behaved correctly.

The benchmark-only LitBank oracle identity fixture used `litbank:<document>` while normalized provider syntax uses S.A.G.A.'s canonical `${stable_key}:${source_locator}` form, which is `litbank:<document>:litbank:<document>` for the single LitBank document section. The locator mismatch therefore caused every otherwise-valid attachment to fail closed.

The production grounding policy was **not** weakened. A benchmark-only alignment helper now converts the oracle fixture to the same canonical single-section locator and re-fingerprints the oracle result; it also fails closed if an oracle mention lies outside the section.

## Corrected diagnostic

Exact scorer head:

`9f1c34d1a9410a0dbb8458fce4a9bfaf598ff9b1`

Workflow run:

`34757830417`

Corrected report fingerprint:

`d2392c11869bf42d92d244af3cc58b4b39d360257726f8c6dc27587ff08f2ba0`

Artifact:

- ID: `10318150573`
- name: `saga-phase3-event-dependency-v2-score`
- ZIP digest: `sha256:60a70145c2bca70029ef147b99b29163b78a70187f24d6598e8134396da0ff60`

### Trigger quality

The dependency-grounding layer preserves the existing BookNLP trigger result exactly:

| Metric | BookNLP dependency challenger | Lexical Tier-0 floor |
| --- | ---: | ---: |
| precision | **0.8003** | 0.4914 |
| recall | **0.7591** | 0.0585 |
| F1 | **0.7791** | 0.1045 |

BookNLP therefore retains about `+0.6746` absolute F1 over the lexical trigger floor. The grounding policy neither improves nor regresses trigger detection because it operates after source-anchored trigger generation.

### Grounding coverage

Across `7,445` BookNLP trigger predictions:

| Coverage diagnostic | Count | Rate |
| --- | ---: | ---: |
| event with any grounded participant | 3,881 | 52.13% |
| event with actor | 3,406 | 45.75% |
| event with patient | 822 | 11.04% |
| event with both actor and patient | 347 | 4.66% |
| actor assignments | 3,432 | — |
| patient assignments | 824 | — |

Syntax opportunities and identity-grounding yield:

- actor-opportunity events: `4,067`;
- actor candidate tokens: `4,155`;
- actor opportunity grounding yield: **83.75%**;
- patient-opportunity events: `2,476`;
- patient candidate tokens: `2,546`;
- patient opportunity grounding yield: **33.20%**.

The actor path therefore attaches through oracle identity at high coverage under the strict direct-dependency policy. Patient coverage is much lower and is the next diagnostic target.

These percentages are **coverage/yield**, not correctness scores. LitBank's event TSV cannot tell us whether an attached actor/patient is semantically correct.

## Tests and qualification

Corrected code passed:

- TypeScript typecheck;
- `132 / 132` analysis-worker tests;
- all `100 / 100` LitBank documents with `0` scorer failures.

The new tests cover active subject/object grounding, passive patient/by-agent grounding, multi-token identity spans, ambiguous identity rejection, deliberate dative exclusion, missing-syntax/fingerprint fail-closed behavior, canonical benchmark locator alignment, and out-of-section oracle rejection.

## Current decision

The direct dependency policy is the **current public participant-grounding challenger infrastructure** because it:

- preserves BookNLP's measured trigger advantage;
- keeps canonical identity ownership inside S.A.G.A.;
- proves substantial strict identity-grounded participant coverage;
- fails closed on ambiguous or structurally inconsistent evidence;
- requires no additional model inference for attachment.

It is **not** a production event/participant default. Participant precision/recall remains unmeasured, BookNLP model-weight licensing remains unverified, and the private modern-fiction suite is still the product promotion gate.

## Next experiment

Audit the ungrounded patient opportunities before changing policy. Categorize at minimum:

- syntax candidate has no covering S.A.G.A./oracle identity mention;
- candidate is a non-character entity/object;
- candidate is a pronoun/nominal whose identity evidence is unresolved;
- candidate is structurally ambiguous;
- dependency structure requires a bounded relation not yet enabled, such as dative or conjunction inheritance;
- multiple candidates/roles would make attachment unsafe.

Only measured categories should justify expanding the policy. Do not enable `dative`, conjunction inheritance, or provider clusters merely to raise coverage.
