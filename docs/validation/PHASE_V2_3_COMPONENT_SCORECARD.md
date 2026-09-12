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

| Metric | BookNLP-small | Deterministic floor |
| --- | ---: | ---: |
| matched-known accuracy | **0.7830** | 0.3265 |
| resolved-speaker accuracy | **0.8057** | 0.5278 |
| end-to-end recall | **0.6765** | 0.2793 |
| unresolved rate | **0.0282** | 0.3815 |
| cross-character contamination | **0.1889** | 0.2921 |

BookNLP attributed-speaker mention -> LitBank gold identity mapping coverage: `0.9419`.

Progress:

- matched-known accuracy gain: about `+0.4565` absolute;
- end-to-end recall gain: about `+0.3972` absolute;
- contamination reduction: about `-0.1032` absolute;
- unresolved reduction: about `-0.3533` absolute.

Decision: **BookNLP is the strongest measured speaker challenger, but `18.89%` contamination is too high for direct adoption**. Combined deterministic-quote + BookNLP-speaker confidence gating is tracked in #213.

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

Decision: **BookNLP is the strongest measured trigger challenger**. This does not qualify participant grounding, negation, modality, realis, causal structure or canonical event acceptance.

Dependency-aware participant grounding is tracked in #214.

## BookNLP component repeatability / resources

Exact benchmark implementation head:

`f013f23f11d2883e8ef1f2e70f9e181e8556df08`

Two independent CPU runs produced identical semantic report fingerprint:

`e0ec94d8d1f678f98057a29117d365926a3253a4a6d5e6e0f7c96e36cab3bef9`

- run 1 wall clock: `452.68 s`
- run 2 wall clock: `293.66 s`
- run 1 peak RSS: `1123.8 MiB`
- run 2 peak RSS: `1157.2 MiB`
- model artifacts: `160,398,571 bytes`
- each run: `100 / 100` documents completed, `0` failed
- heavyweight validation: `111 / 111` tests passed on both attempts

The semantic result is repeatable across these two runs; runtime is host-dependent.

## Adoption blockers that still apply

- private modern-fiction EPUBs are unavailable to the current execution environment;
- BookNLP model-weight license remains unverified;
- BookNLP speaker/event models use LitBank-derived literary annotations, so LitBank is not an independent product-generalization test;
- no production speaker/event method is adopted;
- event participant grounding remains unmeasured on suitable gold;
- scene quality remains unmeasured on the primary suite;
- real BookNLP execution through the new generic subprocess boundary still needs a measured end-to-end run separate from the direct benchmark harness.
