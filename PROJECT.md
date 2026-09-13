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

Merged `main` at the start of the active life-state branch is:

`afa0ef72f981fd0e84b4a08cd78c968aecf42839`

That is PR #242, which merged deterministic narrative-order + unscoped temporal-cue evidence while preserving story-time chronology as unresolved.

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
- PR #240 — relationship failure-mode audit; strict relationship policy retained;
- PR #242 — narrative-order + unscoped temporal-cue evidence foundation; no story-time edges.

Current unmerged measured work:

- issue #243;
- branch `v2/phase-3a-character-life-state-evidence`;
- exact measured life-state scorer head `c29876a7cea3426996e4215d16a28faf1b302378`;
- dedicated run `34786059397`, job `103801639102`;
- report fingerprint `18aa7e3876ce79e1a3fb8f2d2a444ba8891da01b0de801403490c9aa5819630e`;
- documentation continues on top of the measured head without changing state-candidate policy.

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

Raw BookNLP with oracle LitBank identity: matched-known `0.7830`, resolved `0.8057`, end-to-end recall `0.6765`, unresolved `0.0282`, contamination `0.1889`.

Merged combined V2: matched-known `0.7007`, resolved `0.8040`, end-to-end recall `0.5994`, unresolved `0.1285`, contamination `0.1709`, while preserving deterministic quote F1 `0.8563`.

Decision: **combined V2 is the current public speaker challenger, not a production default**.

### Event triggers

- BookNLP trigger P/R/F1: `0.8003 / 0.7591 / 0.7791`;
- lexical Tier-0 P/R/F1: `0.4914 / 0.0585 / 0.1045`.

BookNLP remains the strongest measured public trigger challenger, without production adoption.

### Event participant grounding

Across `7,445` trigger predictions:

- any grounded participant `52.13%`;
- actor-opportunity grounding `83.75%`;
- direct patient-candidate grounding `33.20%`.

The patient audit found **zero true linked-character grounding misses** among `2,546` direct patient candidates and zero structural-locator mismatch. Low patient yield is dominated by broad direct-object semantics, not a measured identity-attachment defect.

Decision: keep direct grounding strict; these are coverage/failure-mode diagnostics, not participant correctness metrics.

### Typed non-character event participants

BookNLP: `146 / 6,701` (`2.18%`) clean typed direct-role candidates and `142 / 5,085` (`2.79%`) event gain.

GLiNER PR #232: `47 / 6,701` (`0.70%`) and `44 / 5,085` (`0.87%`) respectively.

Decision: **retain the provider-neutral contract; reject the pinned GLiNER configuration for this slot.**

### Event semantic qualifiers

On `7,445` triggers, strict qualifier evidence captured `53` explicit cues: negated `3`, modalized `45`, conditional `5`, irrealis `50`. The structural audit found only `11` associated uncaptured one-hop cues; most alternatives were much farther graph relationships.

Decision: **keep the strict qualifier contract and `undetermined` default unchanged**.

### Character relationship evidence

PR #238 foundation:

- pinned predicate hits `196`;
- exact supported binary syntax `48` (`24.49%`);
- grounded distinct-character observations `23` (`47.92%` of supported syntax; `11.73%` of hits).

PR #240 failure audit preserved `196 / 48 / 23`, with `195 / 195` tests. Unsupported syntax is dominated by no/one-sided direct roles; `19 / 25` grounding failures are object-no-linked-character; locator mismatch `0`.

Decision: **keep strict explicit relationship observations; do not derive persistent relationship state; stop public coverage tuning without semantic gold.**

Detailed records:

- `docs/experiments/CHARACTER_RELATIONSHIP_STATE_EVIDENCE.md`
- `docs/experiments/CHARACTER_RELATIONSHIP_FAILURE_AUDIT.md`

### Narrative order / temporal-cue evidence

PR #242 model-light floor: **`202 / 202` tests**, up from `195 / 195` by seven contract tests only.

Corrected 100-document diagnostic:

- event candidates preserved `7,445`;
- trigger P/R/F1 preserved `0.8003 / 0.7591 / 0.7791`;
- temporal cue tokens `871`;
- events with >=1 same-sentence cue `1,856 / 7,445` (`24.93%`);
- event-bearing sentences with a cue `734 / 3,686` (`19.91%`);
- multi-event sentences `1,888`;
- story-time resolved statuses / relations / narrative-order violations `0 / 0 / 0`.

Decision: **keep deterministic narrative order plus unscoped temporal-cue evidence; do not infer story-world chronology yet.**

Detailed record: `docs/experiments/NARRATIVE_TIMELINE_EVIDENCE.md`.

### Character life-state candidate evidence

Issue #243 adds the first explicit state-change **candidate** contract without persistent/current state mutation.

Pinned policy:

- `die` -> uniquely grounded character actor;
- `kill` -> uniquely grounded character patient;
- candidate dimension/value `life_status -> dead`;
- qualifier evidence and deterministic narrative position preserved;
- story time stays unresolved;
- `stateApplications` is structurally empty.

Model-light qualification:

- typecheck pass;
- **`210 / 210` tests pass**, up from `202 / 202` before this contract;
- +8 tests are regression/contract coverage only, not state-quality improvement.

100-document public diagnostic on exact scorer head `c29876a7cea3426996e4215d16a28faf1b302378`:

- attempted/completed/failed `100 / 100 / 0`;
- no new model inference; preserved BookNLP output reused;
- event population and trigger P/R/F1 unchanged at `7,445` and `0.8003 / 0.7591 / 0.7791`;
- `die` / `kill` opportunities **`25` (`0.34%`)**: `die 21`, `kill 4`;
- unique required grounded targets / emitted candidates **`16 / 25` (`64.00%`)**;
- missing required targets `9`; multiple targets `0`; missing mention evidence `0`;
- candidates: `die 13`, `kill 3`, only **`16 / 7,445` (`0.21%`)** of all event candidates;
- candidates with strict qualifier cue `0`; all 16 qualifier states remain undetermined;
- unique/repeated target characters `15 / 1`; max two candidates for one character within a document;
- non-unresolved story-time statuses / persistent state applications / source-order violations **`0 / 0 / 0`**.

Report fingerprint `18aa7e3876ce79e1a3fb8f2d2a444ba8891da01b0de801403490c9aa5819630e`.

Artifact ID `10327100174`, digest `sha256:dc05dc44607284b57b24b4ba938c8055830d244c93b6b5da9995e21495ee0e5a`.

Decision: **keep the narrow candidate evidence contract, but do not assert, apply or persist character life state.** `undetermined` qualifier evidence is not affirmative realis. The public opportunity set is sparse and LitBank has no state-transition/persistence/story-time gold. Do not widen the predicate set merely to increase coverage.

Detailed record: `docs/experiments/CHARACTER_LIFE_STATE_EVIDENCE.md`.

### BookNLP runtime transport

Persistent BookNLP stdio repeated-analysis medians are `4.627 s` and `2.853 s` versus one-shot references `6.314 s` and `8.930 s`, at roughly `1 GiB` peak process-tree RSS, with exact semantic equality. BookNLP model-weight license remains **unverified**.

Decision: **persistent local stdio is preferred for repeated BookNLP execution; one-shot remains the correctness/reference path.** This changes transport, not model quality or production adoption.

## Current Execution Order

1. Finish issue #243 documentation and exact-head integration gates; merge only if all required suites are green.
2. Keep the life-state layer candidate-only: no `alive` predecessor, no current/persistent `dead` state, no resurrection/contradiction reducer and no story-time validity claim.
3. Do not broaden state predicates or dimensions merely to increase public coverage. Any new state dimension requires its own bounded evidence policy and evaluation plan.
4. Before persistent state or story-time edges, add suitable annotation/evaluation infrastructure and use private modern-fiction evidence when source access returns.
5. The next source-neutral derived-intelligence slice should avoid another coverage-tuning loop. Prefer a bounded causality-candidate/evidence contract or evaluation infrastructure that reuses event participants, qualifiers, narrative order and temporal cues without asserting causal truth.
6. Keep public/source-neutral derived-intelligence work diagnostic unless suitable gold supports correctness claims.
7. When private EPUB access returns, create/score primary-suite scene/dialogue/event/relationship/state/timeline annotations for Harry Potter, The Cruel Prince, Caraval and ACOFAS and use those results for product decisions.
8. Adopt no identity, scene, speaker, event, relationship/state, timeline or causal default without primary-suite evidence, repeatability, resource/failure review and production-compatible licensing.
9. After state/timeline/causality evidence contracts are stable, continue tension/arcs/themes and specify the Event / State / Timeline Narrative Graph from measured reality.

## Working Convention

Every substantial session starts from `AGENTS.md`, this file, `docs/README.md`, `docs/DECISIONS.md`, the Phase-3 contracts, analysis/provider architecture docs, the current-state validation record, component scorecard, and relevant experiment docs.

Do not use Modal for textual analysis. S.A.G.A. Modal account ownership remains `modal-03` through `modal-41`. Do not add paid textual-analysis APIs or deploy Vercel without fresh explicit owner approval.
