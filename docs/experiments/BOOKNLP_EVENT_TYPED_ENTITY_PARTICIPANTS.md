# BookNLP Typed Non-Character Event Participant Diagnostic

Status: **PUBLIC COVERAGE DIAGNOSTIC COMPLETE — BOOKNLP TYPED WORLD-ENTITY COVERAGE IS SPARSE**

This experiment measures whether existing BookNLP-small typed entity evidence materially enriches S.A.G.A.'s direct dependency event arguments after already-grounded canonical characters are excluded.

It deliberately does **not** put non-character entities into `saga-event-prediction-v1`'s character-specific `characterKey` field. The output is a separate provider-neutral evidence layer that preserves source spans, dependency role/path, provider entity evidence ID and coarse entity category without inventing a canonical world-entity ID.

LitBank supplies event-trigger gold but not S.A.G.A.-style non-character actor/patient gold. Therefore the non-character results below are **coverage/evidence diagnostics, not participant precision, recall or accuracy**.

## Policy under test

For each source-anchored BookNLP event trigger:

- direct `nsubj` -> actor candidate;
- `agent -> pobj` -> actor candidate;
- direct `dobj` -> patient candidate;
- direct `nsubjpass` -> patient candidate;
- an already-grounded canonical character participant wins and the token is excluded from non-character evidence;
- only one clean, source-covering, exact-structural-locator non-person provider entity may become typed participant evidence;
- multiple clean overlapping non-person entities remain ambiguous;
- malformed-boundary or structurally mismatched entity evidence is rejected explicitly;
- provider `person` and `unknown` categories never become non-character participant evidence;
- provider cluster IDs are never canonical;
- dative and conjunction inheritance remain disabled.

Accepted provider non-person categories in this first layer are:

- `location`;
- `facility`;
- `geopolitical`;
- `organization`;
- `vehicle`.

This is an evidence contract only. It is not a canonical world-entity model or a durable product schema migration.

## Reused corpus and inference

- LitBank repository: `dbamman/litbank`
- pinned commit: `3e50db0ffc033d7ccbb94f4d88f6b99210328ed8`
- license: CC BY 4.0
- documents attempted/completed/failed: `100 / 100 / 0`
- preserved BookNLP source run: `34727310506`
- source head: `f77af8bcab488fd1069e9c6e8ed4970842c78692`
- native artifact: `saga-phase3-booknlp-native-output-f77af8bcab488fd1069e9c6e8ed4970842c78692`
- native artifact SHA-256: `006875873bd58ec53cc976a46d000313107228f4d4dbf6c5dc450cf9b7ba4f6a`
- inference reused: yes; no BookNLP model inference was rerun

Exact scorer/workflow head:

`0c424ddc8ba77c2215bc79e80c76e68d96a5e539`

Workflow evidence:

- run: `34764638728`
- job: `103743318069`
- report fingerprint: `bcd749129620eab5ac9f4271520e3727587a8b0f768ee4860870bdac90561b30`
- artifact ID: `10319749542`
- artifact ZIP digest: `sha256:d228a6329ec4a8a41c421876750df1febde227bb3143b4ba45d17e4d92a57637`
- typecheck: pass
- analysis-worker tests: **`153 / 153` pass**, up from the previous `145 / 145` floor

The eight new model-light tests cover clean actor/patient evidence, passive agents, canonical-character precedence, ambiguity, malformed and mislocated evidence, person/unknown exclusion, and fail-closed fingerprint/syntax behavior.

## Trigger regression check

The new evidence layer operates after event-trigger generation. The scorer nevertheless recomputed the pinned 100-document trigger benchmark so any regression would be visible.

| Metric | This diagnostic | Existing public BookNLP floor |
| --- | ---: | ---: |
| precision | `0.8002686` -> **0.8003** | 0.8003 |
| recall | `0.7590776` -> **0.7591** | 0.7591 |
| F1 | `0.7791291` -> **0.7791** | 0.7791 |

Counts remain:

- true positive triggers: `5,958`;
- false positive triggers: `1,487`;
- false negative triggers: `1,891`;
- predicted triggers: `7,445`;
- gold triggers: `7,849`;
- duplicate predictions: `0`.

The apparent `+0.000029` difference from the stored four-decimal `0.7791` value is rounding only. **Trigger quality is unchanged.**

## Typed non-character coverage

Across all direct dependency actor/patient candidates:

- candidate tokens: **`6,701`**;
- candidate events: **`5,085`**;
- actor candidate tokens/events: `4,155 / 4,067`;
- patient candidate tokens/events: `2,546 / 2,476`;
- clean typed non-character evidence items: **`146`**;
- candidate-token typed coverage: **`2.18%`**;
- events gaining at least one typed non-character evidence item: **`142`**;
- candidate-event gain rate: **`2.79%`**.

### Candidate status breakdown

| Status | Count | Share |
| --- | ---: | ---: |
| already grounded canonical character | 4,265 | 63.65% |
| clean typed non-character | **146** | **2.18%** |
| ambiguous typed non-character | 4 | 0.06% |
| malformed non-character | 0 | 0.00% |
| structural-locator mismatch | 0 | 0.00% |
| provider person only | 140 | 2.09% |
| provider unknown only | 0 | 0.00% |
| no provider entity evidence | **2,146** | **32.03%** |

The strict structural policy did not create a measurable loss here: malformed and locator-mismatch counts are both zero. The dominant remaining gap is simply absence of usable typed provider entity evidence.

### Typed evidence by category

| Category | Count |
| --- | ---: |
| facility | **90** |
| vehicle | 32 |
| location | 17 |
| geopolitical | 6 |
| organization | 1 |

The distribution is narrow and dominated by facilities/vehicles rather than broad world-entity coverage.

### Typed evidence by role

Patient evidence totals `116`:

- facility `77`;
- vehicle `24`;
- location `10`;
- geopolitical `5`.

Actor evidence totals `30`:

- facility `13`;
- vehicle `8`;
- location `7`;
- geopolitical `1`;
- organization `1`.

No `agent -> pobj` typed non-character evidence was emitted in this pinned corpus; all actor evidence came through direct `nsubj`.

## Comparison with the patient-only audit

The previous patient audit saw only `15 / 2,546` (`0.59%`) candidates in its stricter **provider-only non-person after gold/identity classification** bucket.

This experiment asks a different question: after canonical character precedence, how often can clean BookNLP non-person entity evidence directly enrich any actor/patient syntax candidate? It finds `146 / 6,701` (`2.18%`) across both roles.

The larger absolute count is useful evidence, but the coverage is still small. It does not justify treating BookNLP's current typed entities as S.A.G.A.'s world-entity participant solution.

## Decision

Keep the new typed non-character participant representation as a **separate source-grounded evidence layer** because it adds real information without corrupting the character participant contract.

Do **not**:

- promote these provider entities to canonical world entities;
- insert them into `characterKey`;
- weaken identity attachment;
- enable dative or conjunction inheritance merely to increase the percentage;
- claim non-character participant correctness from this diagnostic.

BookNLP's measured typed coverage is too sparse to solve the broader world-entity participant problem. The next typed-entity challenger should therefore be a provider designed for configurable entity typing, starting with the Phase-3-planned **GLiNER small** path, while preserving the same source/role/evidence contract for fair comparison.

No production adoption decision changes:

- BookNLP remains the strongest measured public event-trigger challenger at `0.7791` F1;
- direct character dependency grounding remains the current participant-grounding infrastructure;
- typed non-character BookNLP evidence is retained as sparse optional evidence only;
- participant correctness remains unmeasured on suitable gold;
- private modern-fiction qualification and production-compatible model licensing remain mandatory.