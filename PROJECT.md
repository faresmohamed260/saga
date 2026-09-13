# S.A.G.A. Project

S.A.G.A. is being rebuilt as a web-first storytelling-intelligence platform. The active architecture is S.A.G.A. v2; pre-v2 runtime material is historical/reference only unless a current v2 decision explicitly re-adopts an idea behind a v2-owned contract.

This file is the short source-of-truth handoff. For detailed Phase-3 state and measured evidence, read:

- `docs/phases/PHASE_V2_3_LOCAL_FIRST_NARRATIVE_ANALYSIS.md`
- `docs/phases/PHASE_V2_3_PRIMARY_EVALUATION_CORPUS.md`
- `docs/v2/ANALYSIS_ARCHITECTURE_2026.md`
- `docs/v2/LOCAL_LITERARY_PROVIDER_PROTOCOL.md`
- `docs/validation/PHASE_V2_3A_CURRENT_STATE_2026-09-12.md`
- `docs/validation/PHASE_V2_3_COMPONENT_SCORECARD.md`
- the relevant records under `docs/experiments/`

GitHub is authoritative. Chat history is secondary context only.

## Current Status

**Phase 1 — Closed-Demo Main Site, Accounts & Invitations: COMPLETE.**

**Phase 2 — Story Intake & Character Identity Foundation: REPOSITORY FOUNDATION COMPLETE; ORIGINAL HOSTED-PROVIDER PATH SUPERSEDED.**

**Phase 3 — Local-First Narrative Analysis Rebaseline: ACTIVE.**

Durable decisions D-026 through D-030 require local-first, subscription-free text analysis; Modal media-only; a cost-aware evidence cascade; measurement-driven provider adoption; and local workers using the existing Supabase/B2 control plane. D-031 partitions Modal accounts by project. D-032 selects persistent local stdio as the preferred **BookNLP transport** for repeated analysis; it does not adopt BookNLP as a production provider.

## Current Authoritative Checkpoint

Merged `main` at the start of the active relationship failure-audit branch is:

`8dca05e4f4289d9452e8278554ef719b5c6a30f8`

That is PR #238, which merged the first explicit character relationship-observation + immutable source-order ledger foundation after exact-head merge gates passed.

Latest merged Phase-3 checkpoints include:

- PR #221 — combined deterministic-quote + gated BookNLP speaker V2;
- PR #222 — dependency-aware event character grounding;
- PR #223 — direct patient-candidate failure-mode audit;
- PR #225 — real BookNLP proof through the generic one-shot subprocess boundary;
- PR #227 — persistent loaded BookNLP stdio runtime;
- PR #230 — provider-neutral typed non-character event-participant evidence and BookNLP diagnostic;
- PR #232 — GLiNER typed-entity challenger benchmark, rejected for the current direct-role slot;
- PR #234 — source-grounded event semantic qualifier evidence;
- PR #236 — qualifier structural coverage audit; broad graph propagation rejected;
- PR #238 — explicit character relationship observations + source-order evidence ledger.

Current unmerged measured work:

- issue #239;
- branch `v2/phase-3a-character-relationship-failure-audit`;
- exact measured audit head `b738cb4296af2c9811d5cf18aac9aa8d44c9fe66`;
- dedicated run `34783109777`, job `103793595218`;
- documentation continues on top of the measured head without changing relationship extraction policy.

## Product Goal

S.A.G.A. is not a book summarizer. Its analysis runtime should reverse-engineer a novel or series into an evidence-linked narrative model covering source/chapter/scene structure, canonical identities and mentions, dialogue/speakers, entities/locations/factions, atomic events and participants, relationships/state, chronology/flashbacks, causality, arcs/tension/themes, and later canon-aware retrieval/visualization/media/generation.

Keep three layers distinct:

1. **source layer** — immutable text/structure and exact evidence spans;
2. **resolved layer** — identities, references, speakers and confidence-gated interpretation;
3. **derived intelligence layer** — events, relationships, state, timeline, causality and higher narrative models.

Do not rewrite source text when later evidence changes interpretation.

## Locked Analysis Strategy

```text
apps/web
  -> Supabase durable analysis jobs
      -> local S.A.G.A. analysis worker
          -> B2 source bytes
          -> deterministic orchestration / evidence bookkeeping
          -> local literary-NLP provider(s)
          -> optional localhost llama.cpp structured reasoning
          -> structured evidence/results back to Supabase
```

For every stage prefer:

```text
Tier 0 deterministic structure/rules
  -> Tier 1 lightweight local NLP
  -> Tier 2 specialized local model for unresolved ambiguity
  -> Tier 3 small local generative reasoning over bounded evidence packets only
```

Provider/model output is evidence. Deterministic S.A.G.A. policy owns canonical IDs, merge/admission decisions, accepted/uncertain/rejected state, provenance and persistence.

## Primary Evaluation Policy

Primary product qualification corpus:

- *Harry Potter and the Philosopher's Stone*;
- *The Cruel Prince*;
- *Caraval*;
- ACOTAR series, with *A Court of Frost and Starlight* as the historical regression anchor.

LitBank is **secondary public/gold regression evidence** for reproducible metrics and component isolation. It cannot by itself promote a provider or evidence policy into production. BookNLP's speaker/event models use LitBank-derived annotations, making private modern-fiction qualification especially important.

Copyrighted novel text/EPUB bytes remain private and outside Git. The private EPUB binaries are currently unavailable to the execution environment; do not substitute public-domain books for the product gate.

## Phase 3 Measured Component State

### Character identity

BookNLP-small is **rejected for primary identity**. Repeatable 100-document LitBank evidence includes canonical precision `0.4613`, recall `0.6030`, incorrect merge `0.1934`, fragmentation `0.4607`, linked-mention precision `0.2158`, linked-mention recall `0.1161`, and cluster purity `0.8667`.

The deterministic attachment-first resolver remains the policy foundation, but private-suite production qualification is blocked by source availability.

### Scenes

Scene annotation/evaluation infrastructure and structural/lexical floors are merged. **No scene method is adopted.** Primary-suite annotations remain unavailable.

### Quote detection

- deterministic quote P/R/F1: `0.8570 / 0.8555 / 0.8563`;
- BookNLP quote P/R/F1: `0.7706 / 0.8640 / 0.8146`.

Decision: **retain deterministic quote boundaries as the current measured public-gold leader**.

### Speaker attribution

Raw BookNLP component evidence with oracle LitBank identity:

- matched-known accuracy `0.7830`;
- resolved-speaker accuracy `0.8057`;
- end-to-end recall `0.6765`;
- unresolved rate `0.0282`;
- contamination `0.1889`.

Merged combined V2 challenger:

- matched-known accuracy `0.7007`;
- resolved-speaker accuracy `0.8040`;
- end-to-end recall `0.5994`;
- contamination `0.1709`;
- unresolved rate `0.1285`;
- deterministic quote F1 preserved at `0.8563`.

Decision: **combined V2 is the current public speaker challenger, not a production default**.

### Event triggers

- BookNLP trigger P/R/F1: `0.8003 / 0.7591 / 0.7791`;
- lexical Tier-0 P/R/F1: `0.4914 / 0.0585 / 0.1045`.

BookNLP improves trigger F1 by about `+0.6746` absolute and remains the strongest measured public trigger challenger.

### Event participant grounding

The conservative dependency policy uses direct `nsubj` / `agent->pobj` actors and direct `dobj` / `nsubjpass` patients, grounded only through already-linked S.A.G.A. identity spans with matching structural locators. Dative, conjunction inheritance and provider cluster IDs remain excluded.

Across `7,445` trigger predictions:

- any grounded participant: `52.13%`;
- actor-opportunity grounding yield: `83.75%`;
- direct syntactic patient-candidate grounding yield: `33.20%`.

The patient audit found **zero true linked-character grounding misses** among `2,546` direct syntactic patient candidates. Low patient yield is dominated by broad direct-object semantics, not a measured identity-attachment defect.

These are coverage/failure-mode diagnostics, not participant correctness metrics.

### Typed non-character event participants

BookNLP public diagnostic on the fixed direct-role denominator:

- clean typed non-character candidates: `146 / 6,701` (`2.18%`);
- candidate events gaining typed evidence: `142 / 5,085` (`2.79%`).

GLiNER PR #232 on the same denominator:

- clean typed non-character candidates: `47 / 6,701` (`0.70%`);
- candidate events gaining typed evidence: `44 / 5,085` (`0.87%`);
- relative coverage vs BookNLP: `0.322x` candidate / `0.310x` event.

Decision: **retain the provider-neutral evidence contract, reject GLiNER at this pinned configuration for the current direct-role slot, and do not weaken role/locator policy to inflate coverage.**

### Event semantic qualifiers

PR #234 added a source-grounded qualifier evidence layer. On the fixed `7,445` trigger population:

- any explicit cue: `53` (`0.71%`);
- negated: `3`;
- modalized: `45`;
- conditional: `5`;
- irrealis-cued: `50`;
- unmarked/undetermined: `7,392`.

PR #236 audited `4,261` known cue tokens. `1,528` occur in event-bearing sentences, but only `53` match the strict policy. Most uncaptured cues are farther graph relationships: `961` deeper descendants, `354` other connected same-sentence relationships and `149` siblings/shared-head. Only `11` associated cues are uncaptured one-hop cases.

Decision: **keep the strict qualifier contract and `undetermined` default unchanged.** Do not widen scope from generic graph proximity without semantic-scope correctness evidence.

Detailed records:

- `docs/experiments/BOOKNLP_EVENT_SEMANTIC_QUALIFIERS.md`
- `docs/experiments/BOOKNLP_EVENT_SEMANTIC_QUALIFIER_AUDIT.md`

### Character relationship / source-order state evidence

PR #238 merged the first explicit relationship-observation contract. Relationship evidence remains separate from persistent state and later narrative-time interpretation.

Pinned first-policy predicates:

`love`, `hate`, `trust`, `distrust`, `marry`, `divorce`, `befriend`, `betray`.

Only exact active `nsubj + dobj` or passive `nsubjpass + agent->pobj` shapes are eligible, and both roles must ground to exactly one canonical character. No reciprocal inference, conjunction inheritance, co-occurrence inference, event-co-participation inference, persistence or story-time claim is made. Direct negation/modal/conditional cues remain attached.

Foundation model-light qualification:

- typecheck pass;
- **`188 / 188` tests pass**, up from `177 / 177` before this contract;
- +11 is test/contract coverage only, not semantic quality.

Foundation 100-document public diagnostic:

- attempted/completed/failed: `100 / 100 / 0`;
- pinned predicate hits: `196`;
- exact supported binary syntax: `48` (`24.49%`);
- two-character grounded observations: `23` (`47.92%` of supported syntax; `11.73%` of all hits);
- active/passive observations: `23 / 0`;
- unique directed pairs / pair+predicate groups: `20 / 20`;
- repeated-support groups: `1` (`5.00%`), with `4` observations;
- qualified observations: `6 / 23` (`26.09%`);
- negated/modalized/conditional: `4 / 3 / 0`.

Foundation report fingerprint:

`66b228428713aa6b0b59b0e36f3e50e759f533eed243e015e77c9e69e1061c78`

Issue #239 then audited the exact drop-off without changing policy. Exact measured head `b738cb4296af2c9811d5cf18aac9aa8d44c9fe66` completed `100 / 100` LitBank documents with `0` failures, typecheck pass, and **`195 / 195` tests pass**, up from `188 / 188` solely because of seven audit tests. No new model inference ran.

The audit preserved **`196 / 48 / 23`** exactly.

Syntax failures among the `148` unsupported hits:

- no direct role shape: `86` (`58.11%` of unsupported);
- active subject only: `36` (`24.32%`);
- active object only: `18` (`12.16%`);
- passive subject only: `5`;
- passive agent only: `1`;
- multiple active subjects / objects: `1 / 1`;
- exact accepted passive shapes: `0`;
- mixed active/passive, locator-style parser defects and other unsupported classes: `0`.

Grounding failures among the `25` supported candidates that do not become observations:

- object has no linked character: **`19` (`76%`)**;
- self relation: `2`;
- subject ambiguous: `2`;
- subject has no linked character: `1`;
- object ambiguous: `1`;
- all structural-locator mismatch categories: **`0`**.

Role grounding is asymmetric: subjects are grounded in `45 / 48`, objects in `28 / 48`. The `20` no-character argument positions split `PRON 10 / NOUN 10`; fine POS is `NN 9`, `PRP 5`, `WP 3`, `NNS 2`, `DT 1`.

Predicate-specific supported/grounded counts:

- `love`: `29 -> 16`, with `12` object-no-character;
- `marry`: `9 -> 5`;
- `hate`: `6 -> 0`, **all six object-no-character**;
- `trust`: `3 -> 2`, one self relation;
- `betray`: `1 -> 0`, object-no-character.

Audit report fingerprint:

`7e04a17d1cb5b9e0d48bc98d8a634b36e3e11ecbf5e81f9f3c54a90ec9ee69a1`

Audit artifact:

- ID `10325579385`;
- digest `sha256:5be3f8c48b931acbc3967c7261b0f17f318a840307ffa89d6be6a99774fccc5d`.

Decision: **keep the explicit observation + immutable source-order ledger and strict first-pass extraction policy unchanged.** The audit found no high-volume low-risk omission: syntax misses are mostly absent/one-sided direct structure, and grounding misses are mostly object-side non-character/unlinked arguments. Strict structural-locator matching causes zero measured failures. Do not widen predicates, dependency traversal, conjunction inheritance, co-occurrence/shared-event inference or identity rules merely to inflate coverage. No persistent relationship state and no production relationship default are adopted.

Detailed records:

- `docs/experiments/CHARACTER_RELATIONSHIP_STATE_EVIDENCE.md`
- `docs/experiments/CHARACTER_RELATIONSHIP_FAILURE_AUDIT.md`

### BookNLP runtime transport

The generic one-shot boundary is validated with exact semantic equality to preserved direct BookNLP evidence.

Persistent BookNLP stdio measurements:

- independent-run median analyze latency: `4.627 s` and `2.853 s`;
- one-shot analyze references: `6.314 s` and `8.930 s`;
- peak process-tree RSS remains about `1 GiB`;
- all six persistent analyses exactly reproduced the one-shot semantic fingerprint and counts;
- BookNLP model-weight license remains **unverified**.

Decision: **persistent local stdio is preferred for repeated BookNLP execution; one-shot remains the correctness/reference path.** This changes transport, not model quality or production adoption.

## Current Execution Order

1. Finish issue #239 documentation and exact-head integration gates; merge the audit only if all required suites are green. Do not change relationship extraction policy in this slice.
2. After #239, **stop the public relationship coverage-tuning loop** unless suitable semantic relationship gold becomes available. The structural audit found no broad safe omission.
3. Move to a genuinely new source-neutral narrative capability. Prefer a bounded **explicit state-delta evidence foundation** before chronology/timeline: represent source-anchored state-change observations separately from persistent world state and story-time interpretation.
4. If state-delta evidence cannot be defined safely from current evidence without semantic overclaiming, move instead to a provider-neutral chronology/timeline representation contract that stores source order, explicit temporal cues and unresolved ordering without inventing story-time chronology.
5. Keep new public/source-neutral work diagnostic unless suitable gold supports correctness claims.
6. When private EPUB access returns, create/score primary-suite scene/dialogue/event/relationship/state annotations for Harry Potter, The Cruel Prince, Caraval and ACOFAS and use those results for product decisions.
7. Adopt no identity, scene, speaker, event, relationship/state or chronology default without primary-suite evidence, repeatability, resource/failure review and production-compatible licensing.
8. Continue causality, tension/arcs/themes only after state/timeline evidence contracts are stable, then specify the Event / State / Timeline Narrative Graph from those evidence layers.

## Working Convention

Every substantial session starts from `AGENTS.md`, this file, `docs/README.md`, `docs/DECISIONS.md`, the Phase-3 contracts, analysis/provider architecture docs, the current-state validation record, component scorecard, and relevant experiment docs.

Do not use Modal for textual analysis. S.A.G.A. Modal account ownership remains `modal-03` through `modal-41`. Do not add paid textual-analysis APIs or deploy Vercel without fresh explicit owner approval.
