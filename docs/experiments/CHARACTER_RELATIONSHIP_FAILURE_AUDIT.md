# Character Relationship Failure-Mode Audit

Status: **PUBLIC STRUCTURAL AUDIT COMPLETE — KEEP STRICT RELATIONSHIP POLICY**

Tracks issue #239 under parent Phase-3 tracker #185. This audit follows the explicit character relationship observation/source-order ledger foundation merged by PR #238.

## Purpose

Explain the two measured drop-off points in the first relationship evidence policy **without changing extraction policy**:

1. `148 / 196` pinned relationship-predicate hits do not satisfy the strict binary dependency shape;
2. `25 / 48` strict binary candidates do not ground to two distinct canonical characters.

This is structural/failure-mode evidence only. LitBank does not provide S.A.G.A.-style interpersonal relationship/state gold, so no relationship precision, recall, accuracy, persistence, reciprocity or narrative-time claim is made.

## Reproducibility

Exact measured source head:

`b738cb4296af2c9811d5cf18aac9aa8d44c9fe66`

Dedicated workflow:

- run: `34783109777`;
- job: `103793595218`;
- LitBank commit: `3e50db0ffc033d7ccbb94f4d88f6b99210328ed8`;
- attempted/completed/failed: **`100 / 100 / 0`**;
- typecheck: **pass**;
- model-light worker tests: **`195 / 195` pass**, up from `188 / 188` before the audit classifier;
- new model inference: **none**;
- preserved BookNLP source run: `34727310506`;
- preserved native BookNLP artifact SHA-256: `006875873bd58ec53cc976a46d000313107228f4d4dbf6c5dc450cf9b7ba4f6a`;
- audit report fingerprint: `7e04a17d1cb5b9e0d48bc98d8a634b36e3e11ecbf5e81f9f3c54a90ec9ee69a1`;
- audit artifact ID: `10325579385`;
- audit artifact digest: `sha256:5be3f8c48b931acbc3967c7261b0f17f318a840307ffa89d6be6a99774fccc5d`;
- raw source text/surfaces emitted in aggregate report: **none**.

The `+7` test-count increase is regression/classifier coverage only. It is not a relationship-quality improvement.

## Baseline preservation

The audit hard-failed on denominator drift and preserved the relationship-foundation result exactly:

| Stage | Count | Rate |
| --- | ---: | ---: |
| pinned predicate-token hits | **196** | — |
| strict supported binary syntax | **48** | **24.49%** of hits |
| two-distinct-character observations | **23** | **47.92%** of supported syntax / **11.73%** of hits |
| unsupported syntax | **148** | **75.51%** of hits |
| grounding failures after supported syntax | **25** | **52.08%** of supported syntax |

No extraction rule, identity rule, predicate list, qualifier rule, persistence rule or story-time interpretation changed during this audit.

## Syntax-shape failure audit

All `196` predicate hits classify exactly once:

| Syntax category | Count | Share of all hits | Share of 148 unsupported |
| --- | ---: | ---: | ---: |
| accepted active shape | **48** | **24.49%** | — |
| accepted passive shape | **0** | `0%` | — |
| no direct relationship-role shape | **86** | **43.88%** | **58.11%** |
| active subject only | **36** | **18.37%** | **24.32%** |
| active object only | **18** | **9.18%** | **12.16%** |
| passive subject only | **5** | **2.55%** | **3.38%** |
| passive agent only | **1** | **0.51%** | **0.68%** |
| multiple active subjects | **1** | **0.51%** | **0.68%** |
| multiple active objects | **1** | **0.51%** | **0.68%** |
| passive agent missing `pobj` | `0` | `0%` | `0%` |
| passive agent multiple `pobj` | `0` | `0%` | `0%` |
| multiple passive subjects | `0` | `0%` | `0%` |
| multiple passive agents | `0` | `0%` | `0%` |
| mixed active/passive roles | `0` | `0%` | `0%` |
| other unsupported shape | `0` | `0%` | `0%` |

### Interpretation

The syntax drop-off is not dominated by one narrow parser edge that can safely be enabled. The mass is broad:

- `86 / 148` unsupported hits have **no direct subject/object relationship-role shape at all**;
- `54 / 148` have only one side of the active binary relation (`36` subject-only + `18` object-only);
- only **two** unsupported hits are active-role multiplicity cases;
- partial passive evidence is only **six** hits (`5` passive-subject-only + `1` passive-agent-only), while **zero** predicates satisfy the strict passive `nsubjpass + agent -> pobj` shape.

This does not justify conjunction inheritance, generic dependency traversal or broad passive recovery. Those changes would be semantic hypotheses, not repairs to an identified narrow implementation defect.

## Syntax result by predicate

| Predicate | Hits | Accepted active | Subject only | Object only | No direct roles | Other notable |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `love` | `95` | **29** | `12` | `5` | **49** | — |
| `marry` | `54` | **9** | `14` | `9` | `16` | 1 multi-subject, 1 multi-object, 4 passive-subject-only |
| `trust` | `20` | **3** | `5` | `3` | `8` | 1 passive-subject-only |
| `hate` | `20` | **6** | `4` | `1` | `8` | 1 passive-agent-only |
| `distrust` | `5` | `0` | `0` | `0` | **5** | — |
| `betray` | `2` | **1** | `1` | `0` | `0` | — |
| `divorce` | `0` | `0` | `0` | `0` | `0` | — |
| `befriend` | `0` | `0` | `0` | `0` | `0` | — |

The public corpus therefore gives no evidence that every pinned lexical predicate maps cleanly onto the same direct transitive dependency pattern.

## Canonical-character grounding audit

All `48` strict supported syntax candidates classify exactly once:

| Grounding category | Count | Share of supported syntax | Share of 25 failures |
| --- | ---: | ---: | ---: |
| grounded distinct characters | **23** | **47.92%** | — |
| object has no linked character | **19** | **39.58%** | **76%** |
| self relation | `2` | `4.17%` | `8%` |
| subject identity ambiguous | `2` | `4.17%` | `8%` |
| subject has no linked character | `1` | `2.08%` | `4%` |
| object identity ambiguous | `1` | `2.08%` | `4%` |
| both roles lack linked characters | `0` | `0%` | `0%` |
| both ambiguous | `0` | `0%` | `0%` |
| subject locator mismatch | **0** | `0%` | `0%` |
| object locator mismatch | **0** | `0%` | `0%` |
| both locator mismatch | **0** | `0%` | `0%` |
| mixed role failures | `0` | `0%` | `0%` |

Role-level status:

- subjects: `45` grounded, `1` no linked character, `2` ambiguous, **`0` locator mismatch**;
- objects: `28` grounded, `19` no linked character, `1` ambiguous, **`0` locator mismatch**.

### Interpretation

The second drop-off is strongly asymmetric. Subject identity grounding is already clean in `45 / 48` supported cases, while **19 / 25 grounding failures are object-side arguments with no linked canonical character**.

There is no measured structural-locator defect in this population. Weakening exact locator matching would therefore solve **zero measured failures** while weakening a provenance guard.

The two self-relations should remain excluded from an inter-character relationship ledger. Ambiguity affects only three candidates and is not the dominant bottleneck.

## Missing-character argument POS profile

There are `20` no-linked-character argument positions (`19` objects + `1` subject):

| Coarse POS | Count |
| --- | ---: |
| `PRON` | `10` |
| `NOUN` | `10` |

Fine POS:

- `NN`: `9`;
- `PRP`: `5`;
- `WP`: `3`;
- `NNS`: `2`;
- `DT`: `1`.

This distribution does not support a simple claim that character identity attachment is broadly broken. Half of the missing arguments are ordinary noun-class tokens; the remainder are pronoun/determiner/wh-pronoun forms whose relationship semantics cannot be established from POS alone.

## Grounding result by predicate

| Predicate | Supported syntax | Grounded | Failure pattern |
| --- | ---: | ---: | --- |
| `love` | `29` | **16** | `12` object-no-character; `1` subject ambiguous |
| `marry` | `9` | **5** | `1` self; `1` subject-no-character; `1` subject ambiguous; `1` object ambiguous |
| `hate` | `6` | **0** | **all 6 object-no-character** |
| `trust` | `3` | **2** | `1` self |
| `betray` | `1` | **0** | `1` object-no-character |

The `hate` result is especially useful: its zero grounded observations are **not** because the syntax filter rejects every occurrence—six exact active shapes exist—but every object lacks a linked canonical character under the benchmark oracle identity. That is a semantic/argument-population limitation, not evidence for relaxing locator or multiplicity rules.

## Decision

**Keep the strict relationship observation policy unchanged.**

The audit does not identify a high-volume, low-risk structural omission:

- most syntax misses have no direct binary role shape or only one role;
- conjunction/multiplicity cases are tiny;
- exact passive candidates are absent;
- grounding failures are mostly non-linked objects, not locator drift;
- strict locator matching causes zero measured failures;
- identity ambiguity is rare;
- LitBank lacks relationship/state gold, so broader graph traversal cannot be evaluated for semantic contamination.

Do **not** expand the predicate lexicon, inherit conjunction arguments, infer relationships from co-occurrence/dialogue/shared events, weaken canonical identity or locator rules, or accumulate repeated observations into persistent state merely to raise coverage.

No production relationship/state default is adopted.

## Next direction

This audit closes the useful public structural loop for the first explicit relationship observation layer. Further coverage tuning on LitBank would risk optimizing a denominator without correctness gold.

The next source-neutral capability should be a **new narrative contract**, preferably an explicit state-delta evidence foundation or chronology/timeline representation that remains source-anchored and does not pretend relationship persistence or story-time ordering is already solved. If suitable relationship correctness annotations or the private modern-fiction suite become available, relationship expansion can resume against real semantic evidence.
