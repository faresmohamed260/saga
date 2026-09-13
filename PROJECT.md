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

Merged `main` at the start of the active timeline-evidence branch is:

`0546284e00fabd614af06c0e5910cd4634b0a93b`

That is PR #240, which merged the relationship failure-mode audit and closed the public relationship coverage-tuning loop without broadening extraction policy.

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
- PR #238 — explicit character relationship observations + immutable source-order ledger;
- PR #240 — relationship failure-mode audit; strict relationship policy retained.

Current unmerged measured work:

- issue #241;
- branch `v2/phase-3a-narrative-timeline-evidence`;
- exact corrected scorer head `602120e8423719672a4e66da9b28ce02744bf598`;
- dedicated run `34784052351`, job `103796185890`;
- report fingerprint `a6590f9942f3df79cc1f122c6b97dce641495ce82e8dcbdc8bb04c8f9d217d6b`;
- documentation continues on top of the measured head without changing timeline policy.

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

Across `7,445` trigger predictions, strict direct dependency grounding yields:

- any grounded participant: `52.13%`;
- actor-opportunity grounding: `83.75%`;
- direct syntactic patient-candidate grounding: `33.20%`.

The patient audit found **zero true linked-character grounding misses** among `2,546` direct patient candidates. Low patient yield is dominated by broad direct-object semantics, not a measured identity-attachment defect.

Decision: keep direct grounding strict; these are coverage/failure-mode diagnostics, not participant correctness metrics.

### Typed non-character event participants

BookNLP public diagnostic on the fixed direct-role denominator:

- clean typed non-character candidates: `146 / 6,701` (`2.18%`);
- candidate events gaining typed evidence: `142 / 5,085` (`2.79%`).

GLiNER PR #232 on the same denominator produced only `47 / 6,701` (`0.70%`) clean candidates and `44 / 5,085` (`0.87%`) event gain.

Decision: **retain the provider-neutral evidence contract; reject the pinned GLiNER configuration for this slot.**

### Event semantic qualifiers

PR #234 added strict source-grounded qualifier evidence. On `7,445` triggers:

- any explicit cue: `53` (`0.71%`);
- negated: `3`;
- modalized: `45`;
- conditional: `5`;
- irrealis-cued: `50`.

PR #236 audited wider graph proximity and found most uncaptured cues much farther away; only `11` associated cues were uncaptured one-hop cases.

Decision: **keep the strict qualifier contract and `undetermined` default unchanged.**

### Character relationship / source-order evidence

PR #238 introduced exact explicit relationship observations for pinned predicates `love`, `hate`, `trust`, `distrust`, `marry`, `divorce`, `befriend`, `betray`, with exact active/passive binary syntax and canonical-character grounding.

Foundation 100-document diagnostic:

- predicate hits: `196`;
- supported binary syntax: `48` (`24.49%`);
- grounded distinct-character observations: `23` (`47.92%` of supported syntax; `11.73%` of hits).

PR #240 audited the drop-off with **`195 / 195` tests** and preserved `196 / 48 / 23` exactly. Among `148` unsupported hits, `86` have no direct role shape, `36` active-subject-only, `18` active-object-only. Among `25` grounding failures, `19` are object-no-linked-character and all structural-locator mismatch classes are `0`.

Decision: **keep the strict relationship observation policy unchanged and stop public coverage tuning without semantic relationship gold.** No persistent relationship state or production relationship default is adopted.

Detailed records:

- `docs/experiments/CHARACTER_RELATIONSHIP_STATE_EVIDENCE.md`
- `docs/experiments/CHARACTER_RELATIONSHIP_FAILURE_AUDIT.md`

### Narrative order / temporal-cue evidence

Issue #241 adds the first provider-neutral timeline evidence contract. It deliberately separates deterministic narrative/source order from story-world chronology.

Contract/test qualification:

- typecheck pass;
- **`202 / 202` tests pass**, up from `195 / 195` before this contract;
- +7 is test/contract coverage only, not chronology-quality improvement.

Corrected 100-document diagnostic on head `602120e8423719672a4e66da9b28ce02744bf598`:

- attempted/completed/failed: `100 / 100 / 0`;
- no new model inference; preserved BookNLP output reused;
- event candidates preserved: **`7,445`**;
- trigger P/R/F1 preserved: **`0.8003 / 0.7591 / 0.7791`**;
- temporal cue tokens in event-bearing sentences: **`871`**;
- events with >=1 same-sentence cue: **`1,856 / 7,445` (`24.93%`)**;
- event-bearing sentences with >=1 cue: **`734 / 3,686` (`19.91%`)**;
- multi-event sentences: `1,888`;
- cue-to-event attachments: `2,272`;
- resolved story-time statuses: **`0`**;
- emitted story-time relations: **`0`**;
- narrative-order violations: **`0`**.

Cue families are relative/sequence `613`, deictic `147`, interval/boundary `87`, relative-distance `21`, simultaneity `3`. Most common lemmas are `then 249`, `before 158`, `now 139`, `after 135`.

Report fingerprint:

`a6590f9942f3df79cc1f122c6b97dce641495ce82e8dcbdc8bb04c8f9d217d6b`

Artifact ID `10325862289`, digest `sha256:0c6a36edd5241eb451593dfc4f4cef7af5aa04e6267678081c4c3a5fe92a3fc8`.

Decision: **keep deterministic narrative order plus unscoped temporal-cue evidence, but do not infer story-world chronology yet.** Same-sentence cue presence is evidence availability, not semantic scope or temporal-relation accuracy. The `1,888` multi-event sentences make naïve cue-to-edge conversion especially unsafe. No production timeline default is adopted.

Detailed record: `docs/experiments/NARRATIVE_TIMELINE_EVIDENCE.md`.

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

1. Finish issue #241 documentation and exact-head integration gates; merge only if all required suites are green.
2. Keep the v1 timeline boundary strict: narrative/source order is deterministic; temporal cues are unscoped evidence; story-time relations remain unresolved.
3. Do not add before/after/simultaneous/flashback edges from cue presence alone. Require suitable temporal-relation gold/private annotations or another bounded measurable hypothesis first.
4. After #241, revisit an **explicit state-delta evidence foundation** only if it can be source-grounded without silently claiming persistence or story-time validity. Otherwise build annotation/evaluation infrastructure for temporal relations before new chronology inference.
5. Keep new public/source-neutral work diagnostic unless suitable gold supports correctness claims.
6. When private EPUB access returns, create/score primary-suite scene/dialogue/event/relationship/state/timeline annotations for Harry Potter, The Cruel Prince, Caraval and ACOFAS and use those results for product decisions.
7. Adopt no identity, scene, speaker, event, relationship/state or chronology default without primary-suite evidence, repeatability, resource/failure review and production-compatible licensing.
8. Continue causality, tension/arcs/themes only after state/timeline evidence contracts are stable, then specify the Event / State / Timeline Narrative Graph.

## Working Convention

Every substantial session starts from `AGENTS.md`, this file, `docs/README.md`, `docs/DECISIONS.md`, the Phase-3 contracts, analysis/provider architecture docs, the current-state validation record, component scorecard, and relevant experiment docs.

Do not use Modal for textual analysis. S.A.G.A. Modal account ownership remains `modal-03` through `modal-41`. Do not add paid textual-analysis APIs or deploy Vercel without fresh explicit owner approval.
