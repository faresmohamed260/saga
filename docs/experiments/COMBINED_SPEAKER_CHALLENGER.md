# Combined Deterministic-Quote + BookNLP Speaker Challenger

Status: **V2 IS THE CURRENT PUBLIC COMBINED CHALLENGER — PRIVATE PRODUCT GATE PENDING**

This experiment preserves S.A.G.A.'s stronger deterministic quote boundaries while using BookNLP attributed-speaker evidence only through exact source spans and already-resolved S.A.G.A. identity evidence.

It does **not** make BookNLP coreference clusters canonical, does not adopt a production speaker default, and does not replace the private modern-fiction qualification gate.

## Public component floors

The repeatable 100-document pinned LitBank component benchmark established:

| Component | Matched-known accuracy | Resolved accuracy | End-to-end recall | Contamination | Unresolved rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| Deterministic + oracle identity | `0.3265` | `0.5278` | `0.2793` | `0.2921` | `0.3815` |
| BookNLP speaker attribution | `0.7830` | `0.8057` | `0.6765` | `0.1889` | `0.0282` |

Quote detection remains deterministic-led:

- deterministic quote P/R/F1: `0.8570 / 0.8555 / 0.8563`;
- BookNLP quote P/R/F1: `0.7706 / 0.8640 / 0.8146`.

## V1 — conservative disagreement rejection

The first fusion policy required exact deterministic/BookNLP quote-span agreement and exact S.A.G.A.-resolved speaker spans, then applied:

- deterministic + provider agree -> resolve;
- provider only while deterministic is unresolved -> provider fallback;
- deterministic only -> deterministic;
- deterministic/provider disagreement -> unresolved.

Measured result:

| Metric | V1 |
| --- | ---: |
| Matched-known speaker accuracy | `0.5662` |
| Resolved-speaker accuracy | `0.7946` |
| End-to-end speaker recall | `0.4844` |
| Cross-character contamination | `0.1464` |
| Unresolved rate | `0.2874` |
| Quote F1 | `0.8563` |

V1 materially reduced contamination but discarded too much correct BookNLP evidence. It retained only about `51.6%` of BookNLP's incremental end-to-end recall gain over the deterministic floor and is preserved as a **measured rejection**.

## Conflict audit

A second 100-document run on exact head `f77af8bcab488fd1069e9c6e8ed4970842c78692` preserved native BookNLP outputs and audited V1 conflicts against gold.

Operational result:

- `100 / 100` documents completed;
- `0` failures;
- typecheck passed;
- `117 / 117` worker tests passed;
- wall clock `333.55 s`;
- peak RSS `1118.7 MiB`;
- model artifacts `160,398,571 bytes`;
- report fingerprint `82722e81f8f85c89e0e714b66478f39c2507c9a34997e44f562384beb51a8109`.

Among `415` known-speaker deterministic/BookNLP conflicts:

- BookNLP correct / deterministic wrong: `328` (`79.0%`);
- deterministic correct / BookNLP wrong: `52` (`12.5%`);
- both wrong: `35` (`8.4%`).

The broad structural split was more useful than individual speech verbs:

- post-quote deterministic speech-tag conflicts: BookNLP correct `203 / 240` (`84.6%`);
- pre-quote deterministic speech-tag conflicts: BookNLP correct `125 / 175` (`71.4%`).

This motivated a direction-based policy rather than per-verb rules.

## V2 — provider wins only on post-quote conflict

V2 keeps every V1 evidence boundary and changes only conflict handling:

- when deterministic and BookNLP speakers disagree **and** the deterministic decision came from a post-quote speech tag (`speech_verb_linked_mention:after:*`), choose the exact-span BookNLP/S.A.G.A.-resolved speaker;
- pre-quote conflicts remain unresolved;
- BookNLP cluster IDs remain ignored;
- provider quote and speaker spans must still match exact source evidence;
- malformed or fingerprint-mismatched evidence still fails closed.

The old `unresolved` conflict policy remains selectable in code so V1 stays reproducible.

### Scorer-only qualification

V2 was scored on exact implementation/workflow head `ddec1fa490abf38d37c5cd6e16c1c487e5ec7f79` without rerunning BookNLP inference. The scorer reused the preserved native artifact from workflow run `34727310506`:

- source artifact: `saga-phase3-booknlp-native-output-f77af8bcab488fd1069e9c6e8ed4970842c78692`;
- source artifact SHA-256: `006875873bd58ec53cc976a46d000313107228f4d4dbf6c5dc450cf9b7ba4f6a`;
- `100 / 100` documents completed;
- `0` failures;
- typecheck passed;
- `124 / 124` tests passed;
- scorer step completed in about `31 s`;
- semantic report fingerprint: `67201e5e5dbda7de6a63daf37838c698d0629013ab7f69bfa3d253647220ce06`.

Measured V2 result:

| Metric | V1 | V2 | BookNLP | Deterministic |
| --- | ---: | ---: | ---: | ---: |
| Quote F1 | `0.8563` | `0.8563` | `0.8146` | `0.8563` |
| Matched-known accuracy | `0.5662` | `0.7007` | `0.7830` | `0.3265` |
| Resolved-speaker accuracy | `0.7946` | `0.8040` | `0.8057` | `0.5278` |
| End-to-end recall | `0.4844` | `0.5994` | `0.6765` | `0.2793` |
| Contamination | `0.1464` | `0.1709` | `0.1889` | `0.2921` |
| Unresolved rate | `0.2874` | `0.1285` | `0.0282` | `0.3815` |

V2 versus V1:

- matched-known accuracy: `+0.1345`;
- resolved-speaker accuracy: `+0.0094`;
- end-to-end recall: `+0.1150`;
- unresolved rate: `-0.1589`;
- contamination: `+0.0245`.

V2 versus raw BookNLP:

- matched-known accuracy: `-0.0823`;
- resolved-speaker accuracy: `-0.0017`;
- end-to-end recall: `-0.0771`;
- contamination: `-0.0180` absolute, about `9.5%` relative lower;
- unresolved rate: `+0.1003`.

V2 retains about `80.6%` of BookNLP's incremental end-to-end recall gain over the deterministic floor while keeping deterministic quote boundaries and lowering public cross-character contamination below raw BookNLP.

Fusion counts across all deterministic quote predictions were:

- agreement: `483`;
- provider fallback: `706`;
- deterministic only: `57`;
- provider-selected post-quote conflict: `260`;
- unresolved conflict: `182`;
- other unresolved: `74`.

## Decision

V2 replaces V1 as the **current public combined speaker challenger** because it recovers substantial recall while retaining a measurable contamination reduction versus raw BookNLP. V1 remains retained as the conservative measured rejection and regression reference.

This is **not production adoption**. LitBank is secondary evidence and BookNLP speaker modeling is LitBank-derived. Production promotion still requires:

1. private modern-fiction dialogue/speaker annotations and whole-book qualification;
2. repeatability/reliability review on the product workload;
3. production-compatible model-weight licensing;
4. no regression of S.A.G.A.'s exact source/identity provenance boundaries.
