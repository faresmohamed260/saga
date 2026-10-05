# S.A.G.A. v3 Reboot Baseline

Status: **FROZEN PRE-REBOOT BASELINE**

Baseline commit: `e9d24d54d351f9bf7c1cfa582a01db819efdb2fe`

Frozen branch: `archive/v2-analysis-baseline-2026-10-05`

Preparation branch: `v3/reboot-preparation`

## Purpose

This document defines the immutable comparison point for the v3 narrative-compiler reboot. v3 work must not redefine v2 after the fact. Any claimed improvement must be measured against this baseline or an explicitly versioned successor.

## Preserved baseline measurements

### Character identity — BookNLP-small

- canonical precision: `0.4613`
- canonical recall: `0.6030`
- incorrect merge: `0.1934`
- fragmentation: `0.4607`
- linked-mention precision: `0.2158`
- linked-mention recall: `0.1161`
- cluster purity: `0.8667`

Decision at baseline: rejected for primary character identity.

### Dialogue / quote boundaries

S.A.G.A. deterministic detector:

- precision: `0.8570`
- recall: `0.8555`
- F1: `0.8563`

Decision at baseline: retain as measured public-gold leader.

### Speaker attribution

Combined v2 challenger:

- matched-known accuracy: `0.7007`
- resolved-speaker accuracy: `0.8040`
- end-to-end recall: `0.5994`
- unresolved rate: `0.1285`
- cross-character contamination: `0.1709`

Raw BookNLP remains stronger on recall; combined v2 reduces contamination.

### Event triggers — BookNLP-small

- precision: `0.8003`
- recall: `0.7591`
- F1: `0.7791`

Decision at baseline: strongest measured public trigger challenger; not canonical-event adoption.

### Event participant grounding

Across `7,445` BookNLP triggers:

- any grounded participant: `3,881` (`52.13%`)
- actor present: `3,406` (`45.75%`)
- patient present: `822` (`11.04%`)
- actor-opportunity grounding yield: `83.75%`
- direct patient-candidate grounding yield: `33.20%`

### Typed non-character event participants

BookNLP clean typed direct-role candidates: `146 / 6,701` (`2.18%`).

GLiNER Small v2.1: `47 / 6,701` (`0.70%`).

Decision at baseline: reject pinned GLiNER Small v2.1 configuration for that slot.

### Narrative-order / temporal evidence

- event candidates: `7,445`
- same-sentence temporal cue on event: `1,856 / 7,445` (`24.93%`)
- resolved story-time relations: `0`

Decision at baseline: preserve deterministic source order; story-world chronology remains unresolved.

### Runtime reference

BookNLP 100-document CPU benchmark:

- repeatable semantic fingerprint
- wall clock: `452.68 s` / `293.66 s`
- peak RSS: `1123.8 MiB` / `1157.2 MiB`
- model artifacts: `160,398,571 bytes`

Persistent stdio reduced repeated analysis latency while preserving exact semantic equality.

## Baseline engineering stack

`services/analysis-worker/package.json` at the frozen commit:

- TypeScript `7.0.2`
- tsx `4.23.13`
- Node types `26.2.0`
- Supabase JS `2.112.4`
- AWS S3 client `3.1116.0`
- fast-xml-parser `5.11.1`
- fflate `0.8.3`

The analysis worker already contains dedicated benchmark commands for LitBank, whole-book, primary-fiction regression, scenes, dialogue, events, relationships, timeline and character state. These remain the starting evaluation surface for v3.

## Baseline adoption blockers

The following remained unresolved at freeze time:

- private modern-fiction product-generalization suite unavailable to the current execution environment;
- scene quality not production-qualified;
- event-participant correctness lacks suitable gold;
- event qualifier factuality lacks suitable gold;
- persistent relationship state is not qualified;
- state-transition correctness/persistence is not qualified;
- story-time chronology and flashback handling are not qualified;
- no production speaker/event/relationship/state/timeline method is adopted.

## Reboot rule

No v2 component is removed because a newer model exists. It is removed only when v3 demonstrates a better product-level tradeoff on the same evidence and resource measurements.
