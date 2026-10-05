# S.A.G.A. Project Status

S.A.G.A. is being rebuilt as a web-first narrative-intelligence platform. The active architecture is **S.A.G.A. v2**. Pre-v2 runtime material is historical/reference-only unless a current v2 decision explicitly re-adopts an idea behind a v2-owned contract.

This file is the **current project handoff**. It owns high-level phase and capability status. It intentionally avoids duplicating volatile branch heads, run IDs, and commit checkpoints unless they are needed to explain an active decision; Git history remains definitive for merge state.

For detailed architecture, evaluation, and evidence, use the documentation index in [`docs/README.md`](docs/README.md).

## Current status

- **Phase 1 — Closed-demo main site, accounts, and invitations: COMPLETE.**
- **Phase 2 — Story intake and character-identity foundation: REPOSITORY FOUNDATION COMPLETE; ORIGINAL HOSTED TEXT-PROVIDER DIRECTION SUPERSEDED.**
- **Phase 3 — Local-first narrative-analysis rebaseline: ACTIVE.**

The complete v2 product is **not operational end to end yet**. The application/control-plane foundation and multiple narrative-evidence contracts are implemented, but additional analysis qualification and later narrative-intelligence layers remain incomplete.

## Current architecture direction

The locked required text-analysis path is local-first and subscription-free:

```text
apps/web
  -> Supabase durable analysis jobs
      -> local S.A.G.A. analysis worker
          -> B2 private source bytes
          -> deterministic orchestration / evidence bookkeeping
          -> local literary-NLP provider(s)
          -> optional bounded local structured reasoning
          -> structured evidence/results back to Supabase
```

For each analysis stage, prefer:

```text
Tier 0 deterministic structure/rules
  -> Tier 1 lightweight local NLP
  -> Tier 2 specialized local model for unresolved ambiguity
  -> Tier 3 bounded local generative reasoning over evidence packets
```

Provider/model output is **evidence**, not product truth. Deterministic S.A.G.A. policy owns canonical IDs, merge/admission decisions, accepted/uncertain/rejected state, provenance, and persistence.

## Latest merged Phase 3 milestone

PR **#244 — Phase 3A: add character life-state candidate evidence** is merged.

It added the first provider-neutral character state-change **candidate** contract while preserving the existing safety boundary:

- `die` -> exactly one grounded character actor;
- `kill` -> exactly one grounded character patient;
- emitted observation is only an unverified `life_status -> dead` candidate;
- qualifiers and source/narrative position remain evidence;
- story time remains unresolved;
- persistent/current state applications remain structurally empty.

Qualification for that milestone preserved the event baseline and passed the model-light contract suite at **210 / 210 tests**. The public diagnostic emitted 16 narrow life-state candidates from 7,445 event candidates; no state-correctness or production-adoption claim was made from that coverage result.

Detailed record: [`docs/experiments/CHARACTER_LIFE_STATE_EVIDENCE.md`](docs/experiments/CHARACTER_LIFE_STATE_EVIDENCE.md).

## Product goal

S.A.G.A. is not a book summarizer. Its analysis runtime should reverse-engineer a novel or series into an evidence-linked narrative model covering:

- source / book / chapter / scene structure;
- canonical character identities and mentions;
- dialogue and speakers;
- entities, locations, and factions;
- atomic events and participants;
- relationships and character-state evidence;
- narrative order, temporal cues, and eventually story-world chronology;
- later causality, arcs, tension, themes, retrieval, visualization, media, and grounded generation.

Keep three layers distinct:

1. **Source layer** — immutable text/structure and exact evidence spans.
2. **Resolved layer** — identities, references, speakers, and confidence-gated interpretation.
3. **Derived intelligence layer** — events, relationships, state, timeline, causality, and higher narrative models.

Later evidence may change interpretation; it must not rewrite source text.

## Current measured component state

### Character identity

BookNLP-small remains **rejected for primary identity**. Repeatable 100-document LitBank evidence includes:

- canonical precision `0.4613`;
- canonical recall `0.6030`;
- incorrect merge `0.1934`;
- fragmentation `0.4607`;
- linked-mention precision `0.2158`;
- linked-mention recall `0.1161`;
- cluster purity `0.8667`.

The precision-first deterministic attachment/resolution policy remains the foundation. Protected modern-fiction qualification remains part of the product gate.

### Scenes

Scene annotation/evaluation infrastructure exists, but **no scene method is production-adopted**. Primary-suite annotations remain a qualification dependency.

### Quote detection

Public LitBank comparison:

- deterministic quote P/R/F1: `0.8570 / 0.8555 / 0.8563`;
- BookNLP quote P/R/F1: `0.7706 / 0.8640 / 0.8146`.

Decision: **retain deterministic quote boundaries as the current measured leader among S.A.G.A.'s evaluated public candidates**.

### Speaker attribution

Raw BookNLP with oracle LitBank identity measured:

- matched-known `0.7830`;
- resolved `0.8057`;
- end-to-end recall `0.6765`;
- unresolved `0.0282`;
- contamination `0.1889`.

Combined V2 measured:

- matched-known `0.7007`;
- resolved `0.8040`;
- end-to-end recall `0.5994`;
- unresolved `0.1285`;
- contamination `0.1709`;
- deterministic quote F1 preserved at `0.8563`.

Decision: **combined V2 remains an evaluated public challenger, not a production default**.

### Event triggers

- BookNLP trigger P/R/F1: `0.8003 / 0.7591 / 0.7791`;
- lexical Tier-0 P/R/F1: `0.4914 / 0.0585 / 0.1045`.

BookNLP remains the strongest measured public trigger challenger without automatic production adoption.

### Event participants

Across `7,445` trigger predictions:

- any grounded participant: `52.13%`;
- actor-opportunity grounding: `83.75%`;
- direct patient-candidate grounding: `33.20%`.

The direct-patient audit found zero measured true linked-character grounding misses among `2,546` direct patient candidates and zero structural-locator mismatch. These are failure-mode/coverage diagnostics, **not participant correctness metrics**.

### Event semantic qualifiers

Strict qualifier evidence remains conservative. On the pinned public trigger set it captured explicit negation/modality/conditional/irrealis cues without treating missing cues as affirmative truth.

Decision: keep the strict qualifier contract and `undetermined` default.

### Character relationships

The current contract preserves explicit, source-grounded relationship observations only. It does **not** derive persistent relationship state from sparse public evidence.

Decision: keep the strict observation policy and avoid broad graph propagation without semantic gold.

### Narrative order and temporal cues

The current foundation preserves deterministic narrative/source order and unscoped temporal-cue evidence.

Decision: **do not infer story-world chronology yet**. Temporal cues are evidence; story-time relations remain unresolved until suitable evaluation can measure them.

### Character life-state candidates

Merged PR #244 adds the first deliberately narrow state-change candidate contract.

Decision: **keep candidate evidence; do not assert, apply, or persist current character life state**.

## Primary evaluation policy

Primary product qualification targets protected modern-fiction material representing the intended workload, including multi-book series. Copyrighted novel text/EPUB bytes remain private and outside Git.

LitBank is **secondary public/gold regression evidence** for reproducibility, component isolation, and public comparisons. It cannot by itself promote a provider or evidence policy into production—especially where provider models were trained on LitBank-derived annotations.

Public benchmark claims in the README and docs therefore describe **S.A.G.A.'s measured candidate comparisons**, not broad state-of-the-art claims.

## Current non-capabilities

The following are intentionally not represented as shipped:

- complete end-to-end v2 product operation;
- production-adopted scene segmentation;
- story-world chronology / flashback resolution;
- persistent/current character state from candidate evidence;
- persistent relationship state from sparse observations;
- causal/motivational graph inference;
- completed arc/tension/theme models;
- final canon-aware retrieval and grounded-generation layers.

## Development and qualification rules

- Required textual analysis must not depend on a paid AI API/subscription.
- Modal is reserved for governed image/media generation, not required text analysis.
- Normal CI remains deterministic and model-light.
- Heavyweight/provider experiments run through dedicated qualification paths.
- Provider output remains evidence behind S.A.G.A.-owned validation and state policy.
- Full-book resource accounting is part of provider selection.
- Private copyrighted fiction must not leak into Git, logs, or public artifacts.
- Experimental components are not silently promoted to defaults.
- Documentation must distinguish implemented, evaluated, active, planned, and historical state.

## Read next

Use these sources by purpose:

1. [`AGENTS.md`](AGENTS.md) — repository/AI development instructions.
2. [`docs/README.md`](docs/README.md) — documentation map.
3. [`docs/DECISIONS.md`](docs/DECISIONS.md) — durable architectural and product decisions.
4. [`docs/phases/PHASE_V2_3_LOCAL_FIRST_NARRATIVE_ANALYSIS.md`](docs/phases/PHASE_V2_3_LOCAL_FIRST_NARRATIVE_ANALYSIS.md) — active Phase 3 contract.
5. [`docs/phases/PHASE_V2_3_PRIMARY_EVALUATION_CORPUS.md`](docs/phases/PHASE_V2_3_PRIMARY_EVALUATION_CORPUS.md) — evaluation policy.
6. [`docs/v2/ANALYSIS_ARCHITECTURE_2026.md`](docs/v2/ANALYSIS_ARCHITECTURE_2026.md) — analysis architecture.
7. [`docs/v2/LOCAL_LITERARY_PROVIDER_PROTOCOL.md`](docs/v2/LOCAL_LITERARY_PROVIDER_PROTOCOL.md) — local provider boundary.
8. [`docs/validation/PHASE_V2_3_COMPONENT_SCORECARD.md`](docs/validation/PHASE_V2_3_COMPONENT_SCORECARD.md) — detailed measured component state.
9. [`docs/experiments/`](docs/experiments/) — reproducible experiment records.

Git history is authoritative for exact merge/commit state. This handoff owns the high-level project state and should be updated when that state changes materially.
