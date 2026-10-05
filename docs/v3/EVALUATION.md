# S.A.G.A. v3 Evaluation and Gold Corpus Specification

Status: **DRAFT v0 — REBOOT GATE**

v3 adoption is benchmark-driven. No model or architecture is promoted because it is newer, larger, or stronger on an unrelated leaderboard.

## 1. Evaluation layers

S.A.G.A. evaluates at four levels:

1. **component quality** — isolated task accuracy;
2. **semantic safety** — unsupported/contaminating output behavior;
3. **whole-book behavior** — consistency, scale and runtime;
4. **product usefulness** — whether the compiled IR can answer story questions correctly with evidence.

## 2. Baseline

The frozen comparison branch is:

`archive/v2-analysis-baseline-2026-10-05`

Baseline commit:

`e9d24d54d351f9bf7c1cfa582a01db819efdb2fe`

Existing LitBank and component benchmarks remain valid v2 references.

## 3. Gold corpus v0

The reboot requires a compact, deep corpus rather than a huge shallow one.

### Public corpus

Use public/redistributable material for CI-safe regression where licenses permit.

Purposes:

- repeatable identity regression;
- quote/speaker tests;
- event mention tests;
- basic whole-document runtime.

### Private product corpus

Use legally owned/private modern fiction only in local qualification, never committed to the repository.

The suite should contain varied narrative styles:

- first-person;
- third-person;
- multi-POV;
- dialogue-heavy;
- action-heavy;
- nonlinear chronology;
- flashbacks/memories;
- alias/title-heavy fantasy;
- pronoun-heavy passages;
- dense world-building;
- repeated unnamed/partially named characters.

Recommended initial books/series should come from material already used by the owner for S.A.G.A. product testing, but the repository stores only fingerprints/annotation IDs, never copyrighted source text.

## 4. Deep annotation units

Select a small number of chapters/passages and annotate them comprehensively.

Each unit should include:

- structural source spans;
- entity mentions;
- canonical entity clusters;
- aliases vs descriptive references;
- pronoun/coreference links;
- quote boundaries;
- quote speakers;
- scene boundaries;
- event mentions;
- event coreference;
- event participants/roles;
- explicit attributes;
- relationship observations;
- state observations/deltas;
- temporal relations;
- causal relations where genuinely supportable.

A deeply annotated chapter is more valuable for architecture comparison than thousands of isolated single-task examples.

## 5. Annotation format

Gold annotations should use Narrative IR IDs/semantics rather than provider-specific schemas.

Each annotation includes:

- `document_fingerprint`
- `annotation_version`
- task/type
- exact normalized offsets or structural locator
- gold label/value
- canonical entity/event ID within annotation scope
- ambiguity status
- annotator notes where required

Private annotations may contain source excerpts locally but committed fixtures must not reproduce copyrighted text beyond safe minimal snippets.

## 6. Primary metrics

### Entity/identity

- mention detection P/R/F1;
- canonical precision/recall;
- incorrect merge rate;
- fragmentation;
- attachment precision/recall;
- cluster purity;
- unresolved rate;
- cross-document/series identity accuracy when available.

### Dialogue

- quote-boundary P/R/F1;
- matched-known speaker accuracy;
- end-to-end speaker recall;
- unresolved rate;
- cross-character contamination.

### Scene segmentation

- exact boundary P/R/F1;
- ±1 paragraph tolerant score;
- over-segmentation rate;
- under-segmentation rate.

### Events

- event-mention P/R/F1;
- event-coreference cluster score;
- participant-role P/R/F1;
- unsupported-event rate;
- duplicate-event rate;
- modality/realis error rate.

### Attributes/traits

- explicit attribute precision/recall;
- unsupported attribute rate;
- stable-trait precision;
- counterevidence handling.

### Relationships

- observation precision/recall;
- relationship-state precision;
- directionality errors;
- temporal-state errors;
- unsupported relationship rate.

### State

- state observation precision/recall;
- state-delta precision/recall;
- contradiction rate;
- persistence validity;
- resurrection/reversal handling where present.

### Time

- pairwise temporal relation F1;
- contradiction/cycle count;
- flashback classification accuracy;
- solved-coverage rate;
- false forced-order rate.

### Causality

- supported causal-edge precision;
- recall on annotated causal edges;
- temporal-only false positive rate;
- unresolved rate.

## 7. Safety metrics

These are first-class and can outweigh F1 improvements.

- unsupported canonical fact rate;
- evidence-span mismatch rate;
- cross-character contamination;
- wrong merge severity;
- contradiction introduction rate;
- provenance completeness;
- percentage of accepted facts with inspectable source support.

## 8. Product metric

Primary proposed product gate:

**Supported coverage at >= 97% precision**

Interpretation: how much useful narrative information can S.A.G.A. safely compile while maintaining at least 97% precision on accepted/supportable facts for the evaluated task/domain.

Candidate layers may run at lower precision to maximize recall; canonical promotion must satisfy the stricter threshold.

## 9. Performance metrics

Every benchmark captures:

- wall-clock time;
- tokens or source characters processed per second;
- peak process-tree RAM;
- peak VRAM;
- model artifact size;
- cold-start time;
- model load/unload time;
- GPU utilization where practical;
- stage cache hit rate;
- output artifact size;
- failures/retries.

## 10. Comparison matrix

Each v3 component benchmark must include:

| Field | Requirement |
|---|---|
| baseline | named v2/current candidate |
| challenger | exact model/version/config |
| dataset | fingerprinted fixture set |
| quality | task metrics |
| safety | unsupported/contamination metrics |
| resources | runtime/RAM/VRAM/artifact size |
| license | production eligibility |
| determinism | repeatability fingerprint where practical |
| decision | adopt / reject / research-only / unresolved |

## 11. Architecture-level shootout

The v3 prototype must be compared against v2 on the same selected documents.

Required outputs:

- identity graph;
- dialogue/speaker observations;
- scene boundaries;
- event mentions/events;
- participants;
- attributes/relationship observations;
- available state/time/causal evidence;
- end-to-end runtime/resources;
- unsupported canonical facts.

The comparison must distinguish component gains from downstream cascade effects.

## 12. Promotion gates

A v3 stage may replace its v2 counterpart only if:

1. evidence alignment is not worse;
2. unsupported/cross-entity contamination stays within the stage gate;
3. product-level precision improves or is statistically/operationally equivalent with a material resource win;
4. licensing permits the intended use;
5. whole-document behavior has been tested;
6. failure/unresolved semantics remain explicit;
7. output can be reproduced from versioned source/model/config fingerprints.

## 13. CI vs qualification

### Normal CI

- deterministic tests;
- tiny fixtures;
- schema/contract validation;
- artifact fingerprint tests;
- no mandatory large model downloads.

### Local/manual qualification

- full LitBank/public suite;
- private modern-fiction suite;
- GPU model benchmarks;
- whole-book resource measurements;
- v2/v3 architecture shootouts.

## 14. Benchmark command target

The reboot should converge on one top-level runner conceptually equivalent to:

```bash
saga benchmark --architecture v2 --suite public
saga benchmark --architecture v3 --suite public
saga benchmark --architecture v3 --suite private-modern-fiction
```

The exact CLI implementation is part of the first implementation milestone.
