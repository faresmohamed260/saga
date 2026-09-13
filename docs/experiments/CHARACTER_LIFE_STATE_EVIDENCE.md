# Character life-state change candidate evidence

Status: **PUBLIC DIAGNOSTIC COMPLETE — CANDIDATE EVIDENCE ONLY; NO PERSISTENT STATE**

Tracking issue: #243

This experiment adds the first provider-neutral S.A.G.A. **character state-change candidate** contract. The first slice is deliberately narrow and records only explicit life-status change candidates from already validated event evidence.

It does **not** create current character state, assert that a character is dead, establish story-time validity, or perform state reduction.

## First contract

Pinned predicates and target roles:

- `die` -> exactly one grounded `actor`;
- `kill` -> exactly one grounded `patient`.

When that role is uniquely grounded to a canonical character, S.A.G.A. may emit an **unverified** candidate observation:

`life_status -> dead`

The observation retains:

- source S.A.G.A. event ID;
- provider trigger evidence ID;
- target canonical character and target mention evidence;
- exact source offsets and structural locator;
- deterministic narrative sequence index;
- `storyTimeStatus: unresolved`;
- strict event polarity/modality/realis evidence and qualifier cue IDs;
- candidate status `unverified_state_change_candidate`;
- application status `not_applied_candidate_only`.

The v1 result structurally requires `stateApplications` to remain empty.

## Explicit non-claims

A `die` or `kill` candidate is **not** automatically an actual death. The source may be figurative, quoted, negated, modal, hypothetical, conditional, attempted, interrupted, recalled, dreamt, or otherwise non-actual.

The first contract therefore does not:

- infer an `alive` predecessor;
- mutate a persistent/current `dead` state;
- establish valid-from/valid-to story time;
- infer resurrection;
- resolve contradictions;
- broaden to injury, location, possession, knowledge, affiliation or other state dimensions.

## Composition

The contract composes only already validated evidence:

1. BookNLP event/syntax evidence normalized through the provider-neutral literary evidence layer;
2. S.A.G.A. dependency-grounded event participants;
3. strict event semantic qualifier evidence;
4. deterministic narrative timeline entries.

Normalized-input, event-result, qualifier-result and timeline-result fingerprints are bound and validated. Event spans must bind exactly one provider trigger. Timeline and qualifier evidence must bind that same trigger. Drift fails closed.

## Model-light qualification

Before corpus scoring:

- typecheck: **pass**;
- worker tests: **`210 / 210`**, up from `202 / 202` before this contract;
- +8 tests are contract/regression coverage only, not state-quality improvement.

Synthetic coverage includes:

- `die` targeting the grounded actor;
- `kill` targeting the grounded patient;
- missing/multiple required targets remaining unobserved;
- negation/modality retained without state application;
- non-pinned predicates excluded;
- source-order determinism under shuffled evidence;
- fingerprint/timeline-binding failure;
- semantic tampering and any persistent state application rejected.

## 100-document public diagnostic

Exact scorer head:

`c29876a7cea3426996e4215d16a28faf1b302378`

Dedicated workflow:

- run `34786059397`;
- job `103801639102`;
- LitBank attempted/completed/failed: **`100 / 100 / 0`**;
- typecheck: **pass**;
- worker tests: **`210 / 210`**;
- new model inference: **none**;
- preserved BookNLP native output reused from run `34727310506`, digest `sha256:006875873bd58ec53cc976a46d000313107228f4d4dbf6c5dc450cf9b7ba4f6a`.

### Event baseline preserved

- event candidates: **`7,445`**;
- trigger TP / FP / FN: `5,958 / 1,487 / 1,891`;
- trigger precision / recall / F1: **`0.8002686 / 0.7590776 / 0.7791291`**, rounded **`0.8003 / 0.7591 / 0.7791`**;
- duplicate predictions: `0`.

The state-candidate layer changes neither event count nor trigger quality.

### Opportunity and grounding funnel

Across `7,445` event candidates:

- `die` / `kill` trigger opportunities: **`25` (`0.34%`)**;
  - `die`: `21`;
  - `kill`: `4`;
- unique required canonical-character target: **`16 / 25` (`64.00%`)**;
- missing required target: **`9 / 25` (`36.00%`)**;
- multiple required targets: `0`;
- uniquely grounded target missing mention evidence: `0`;
- emitted life-state candidates: **`16`**;
  - `die`: `13`;
  - `kill`: `3`.

So the resulting candidate population is only **`16 / 7,445` (`0.21%`)** of the event population.

### Qualifier evidence

Among the `16` emitted candidates:

- candidates with any strict qualifier cue: **`0`**;
- negated: `0`;
- modalized: `0`;
- irrealis-cued: `0`;
- all qualifier fields undetermined: **`16`**.

This must **not** be interpreted as 16 confirmed deaths. The qualifier contract's `undetermined` state means no accepted direct cue was captured; it is not affirmative realis evidence.

### Repeated target observations

Within per-document canonical-character scope:

- unique target characters: `15`;
- target characters with repeated candidates: `1`;
- repeated-candidate excess: `1`;
- maximum candidates for one character within one document: `2`.

Repeated source-order evidence is preserved as repeated candidate observations. It does not imply persistence, corroboration, contradiction, resurrection, or story-time sequence.

### Safety invariants

- non-`unresolved` story-time statuses: **`0`**;
- persistent/current state applications: **`0`**;
- source-order violations: **`0`**.

## Reproducibility

Report fingerprint:

`18aa7e3876ce79e1a3fb8f2d2a444ba8891da01b0de801403490c9aa5819630e`

Aggregate artifact:

- ID `10327100174`;
- name `saga-phase3-character-life-state-evidence-c29876a7cea3426996e4215d16a28faf1b302378`;
- digest `sha256:dc05dc44607284b57b24b4ba938c8055830d244c93b6b5da9995e21495ee0e5a`;
- aggregate artifact size `8,885` bytes;
- no raw source prose/surfaces emitted.

## Interpretation

The bounded composition works and remains provenance-complete, but the public opportunity set is extremely small. Only `25` of `7,445` event candidates match the two pinned predicates, and only `16` become uniquely grounded candidate observations.

That is enough to justify retaining a reusable **candidate evidence contract**, because it proves S.A.G.A. can compose event, canonical participant, qualifier and narrative-order evidence without mutating state. It is not enough to justify a general state model, a broader predicate lexicon, or any persistent reducer.

The absence of strict qualifier cues on the 16 candidates makes persistence especially unsafe: no public evidence here establishes that these candidates are actual, durable story-world deaths.

## Decision

**Keep the narrow character life-state candidate evidence contract. Do not apply or persist character life state.**

No production state default is adopted. LitBank supplies event-trigger and character-coreference annotations, not S.A.G.A.-style state-transition truth, persistence, contradiction, resurrection or story-time validity gold.

Do not broaden the state predicate set merely to raise coverage. Any later state dimension must have its own bounded source-grounded policy and evaluation plan.

A persistent state reducer remains blocked until suitable state-transition/private annotations and story-time evidence can measure semantic correctness, contradictions and temporal validity.

## Constraints preserved

- no paid AI API / hosted textual inference;
- no Modal textual analysis;
- no new model inference in this diagnostic;
- normal CI remains model-light;
- no copyrighted modern-fiction prose in Git/artifacts;
- no current/persistent state mutation;
- no story-time validity claim;
- no chronology/flashback inference;
- no deployment;
- no production-adoption change.
