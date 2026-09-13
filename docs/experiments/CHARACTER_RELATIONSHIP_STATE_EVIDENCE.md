# Phase 3A — Source-Grounded Character Relationship / State Evidence Foundation

Status: **PUBLIC COVERAGE FOUNDATION MEASURED — NOT A RELATIONSHIP CLASSIFIER OR PRODUCTION DEFAULT**

Issue: #237  
Draft PR: #238

## Purpose

This slice introduces the first provider-neutral relationship evidence contract over already-resolved S.A.G.A. character identities and validated dependency syntax.

It deliberately keeps three layers separate:

1. **relationship observation** — one explicit source-grounded predicate between two canonical character identities;
2. **source-order evidence history** — immutable observations ordered by their source position;
3. **relationship/world state** — later interpretation of persistence, transition, contradiction and story-time validity.

Only the first two are implemented here. The source-order ledger is evidence bookkeeping, not a claim that a relationship persists after a sentence.

## First deterministic policy

Pinned predicate lemmas:

- `love`
- `hate`
- `trust`
- `distrust`
- `marry`
- `divorce`
- `befriend`
- `betray`

Supported binary syntax:

- active: exactly one direct `nsubj` + exactly one direct `dobj`;
- passive: exactly one direct `nsubjpass` + exactly one direct `agent`, with exactly one `pobj` under that agent.

Both arguments must ground through exactly one already-linked S.A.G.A. identity mention and the identity/syntax structural locators must match exactly. Self-relations are rejected.

The policy does **not** infer:

- reciprocal edges;
- conjunction-inherited arguments;
- relationships from character co-occurrence;
- relationships from dialogue co-occurrence;
- relationships from shared event participation;
- persistence, valid-from/valid-to state or story-time order.

Surface semantic direction is preserved. Passive syntax such as a patient plus `by`-agent is normalized only to the explicit semantic agent → patient observation; no reverse edge is created.

## Qualification evidence

Direct source-grounded qualification remains attached to the observation:

- direct predicate/auxiliary negation;
- direct modal auxiliary from the pinned modal set;
- direct `if` / `unless` conditional marker.

A qualified observation remains an observation of what the source explicitly states. It is **not** converted into an unqualified durable state fact.

## Model-light qualification

The implementation first exposed a test-fixture-only TypeScript error under `exactOptionalPropertyTypes`: a missing syntax layer was represented as `syntaxTokens: undefined` instead of omitting the optional property. The fixture was corrected; the production relationship contract did not change.

Exact clean implementation baseline:

`9d13b9acd5f968b36aae23ed6ba83a62808a92df`

Analysis Worker CI:

- typecheck: **pass**;
- tests: **188 / 188 pass**;
- previous floor before this contract: **177 / 177**;
- delta: **+11 regression/contract tests**.

The test-count increase is integration/regression coverage only, not relationship-quality improvement.

Synthetic coverage includes active/passive direction, no reciprocal inference, qualifier retention, self/unresolved/ambiguous rejection, no conjunction inheritance, non-pinned predicate rejection, repeated source-order evidence, deterministic output, fail-closed fingerprint/syntax behavior and tamper detection.

## 100-document public coverage diagnostic

Exact measured scorer head:

`bab1b898ba8aeb23fff5d9be1820b368910ee82d`

Dedicated workflow:

- run: `34782059516`;
- job: `103790751005`;
- LitBank commit: `3e50db0ffc033d7ccbb94f4d88f6b99210328ed8`;
- attempted/completed/failed: **100 / 100 / 0**;
- typecheck: **pass**;
- model-light tests: **188 / 188 pass**;
- new model inference: **none**;
- preserved BookNLP syntax artifact source run: `34727310506`;
- preserved native artifact SHA-256: `006875873bd58ec53cc976a46d000313107228f4d4dbf6c5dc450cf9b7ba4f6a`.

The benchmark uses LitBank gold/coreference only as **oracle character identity** and aligns that benchmark-only identity to S.A.G.A.'s canonical single-section structural locator. Production identity resolution is not bypassed or weakened.

### Coverage funnel

Across the fixed 100-document public corpus:

| Stage | Count | Yield |
| --- | ---: | ---: |
| pinned predicate-token hits | **196** | — |
| exact supported binary syntax | **48** | **24.49%** of predicate hits |
| two-character grounded observations | **23** | **47.92%** of supported syntax |
| observations as share of all predicate hits | **23** | **11.73%** |

All 48 supported syntax candidates are active in this public run. No passive candidate satisfied the exact first-policy shape, so no passive relationship observation is present in this diagnostic.

### Predicate coverage

Candidate predicate-token counts:

| Predicate | Hits |
| --- | ---: |
| `love` | **95** |
| `marry` | **54** |
| `trust` | **20** |
| `hate` | **20** |
| `distrust` | **5** |
| `betray` | **2** |
| `divorce` | `0` |
| `befriend` | `0` |

Grounded relationship observations:

| Predicate | Observations |
| --- | ---: |
| `love` | **16** |
| `marry` | **5** |
| `trust` | **2** |
| all other pinned predicates | `0` |

This difference is expected under the strict contract: a predicate lemma hit is not enough. It must have the exact binary dependency shape and both roles must map unambiguously to canonical characters.

### Pair / support structure

- observations: **23**;
- unique directed character pairs: **20**;
- unique directed pair + predicate ledger groups: **20**;
- groups with repeated support: **1 / 20** (**5.00%**);
- that repeated group contains **4** observations;
- maximum support for one pair+predicate group: **4**;
- support histogram: `19` groups with one observation, `1` group with four observations.

The ledger preserves repeated evidence but does not declare that repeated support establishes persistent relationship state.

### Qualification prevalence

- qualified observations: **6 / 23** (**26.09%**);
- unqualified observations: **17 / 23** (**73.91%**);
- negated observations: **4 / 23** (**17.39%**);
- modalized observations: **3 / 23** (**13.04%**);
- conditional observations: **0**;
- qualifier cues: **7** total.

Because qualification can overlap, the negated/modalized counts do not sum to the number of qualified observations.

## Reproducibility evidence

Report fingerprint:

`66b228428713aa6b0b59b0e36f3e50e759f533eed243e015e77c9e69e1061c78`

Aggregate artifact:

- ID: `10325625680`;
- digest: `sha256:efce6db6204928799b2e8b8feefa03d45632a54491252cdf11ba8fdddbd3e73b`;
- size: `7,861` bytes;
- raw source text / relationship surfaces: **not emitted**.

A first workflow attempt at scorer head `9972e2ddf8c812b4445ac9a9c79c8e75f83583dc` failed before scoring because the diagnostic incorrectly looked for `*.tsv` in LitBank `coref/tsv`; the pinned corpus stores paired `*.ann` + `*.txt` files there. The scorer was corrected to follow the same file convention as S.A.G.A.'s already-successful LitBank oracle benchmark. The relationship extraction policy was unchanged.

## Interpretation / decision

**Keep the relationship observation + immutable source-order ledger foundation, but do not call this a general relationship extractor and do not derive persistent state from it.**

The first policy is intentionally sparse:

- only about one quarter of pinned predicate hits have the exact supported binary syntax;
- about half of those exact syntax candidates ground both roles to oracle characters;
- only three pinned predicates produce grounded observations in this public run;
- repeated evidence is rare;
- more than a quarter of observations carry explicit negation/modality qualification that would be lost by naive state accumulation.

The narrowness is acceptable for an **evidence foundation** because it avoids turning co-occurrence or broad interaction evidence into semantic relationship truth. It is not sufficient for product-level relationship coverage.

LitBank provides no S.A.G.A.-style interpersonal relationship/state gold. Therefore these numbers are **coverage/yield diagnostics only**, not precision, recall, accuracy, persistence quality or narrative-time correctness.

No production relationship/state default is adopted. Private modern-fiction annotations remain required before product promotion.

## Next measured work

Do not simply enlarge the verb list or dependency traversal to inflate coverage.

The next source-neutral relationship/state work should first explain the `148 / 196` predicate hits that do not satisfy the strict binary syntax and the `25 / 48` supported syntax candidates that do not ground to two canonical characters. That failure-mode audit can determine whether a coherent additional evidence class exists (for example explicit copular/kinship/affiliation constructions) before adding any rule.

State-delta reducers, contradiction resolution and narrative-time validity should remain separate until relationship observations have stronger measured support and suitable private annotations exist.
