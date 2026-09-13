# S.A.G.A. Project

S.A.G.A. is being rebuilt as a web-first storytelling-intelligence platform. The active architecture is S.A.G.A. v2; pre-v2 runtime material is historical/reference only unless a current v2 decision explicitly re-adopts an idea behind a v2-owned contract.

This file is the short source-of-truth handoff. For detailed Phase-3 state and measured component evidence, read:

- `docs/validation/PHASE_V2_3A_CURRENT_STATE_2026-09-12.md`
- `docs/validation/PHASE_V2_3_COMPONENT_SCORECARD.md`
- the relevant records under `docs/experiments/`

## Current Status

**Phase 1 — Closed-Demo Main Site, Accounts & Invitations: COMPLETE.**

**Phase 2 — Story Intake & Character Identity Foundation: REPOSITORY FOUNDATION COMPLETE; ORIGINAL HOSTED-PROVIDER PATH SUPERSEDED.**

**Phase 3 — Local-First Narrative Analysis Rebaseline: ACTIVE.**

Authoritative Phase-3 documents:

- `docs/phases/PHASE_V2_3_LOCAL_FIRST_NARRATIVE_ANALYSIS.md`
- `docs/phases/PHASE_V2_3_PRIMARY_EVALUATION_CORPUS.md`
- `docs/v2/ANALYSIS_ARCHITECTURE_2026.md`
- `docs/v2/LOCAL_LITERARY_PROVIDER_PROTOCOL.md`
- `docs/validation/PHASE_V2_3A_CURRENT_STATE_2026-09-12.md`
- `docs/validation/PHASE_V2_3_COMPONENT_SCORECARD.md`

Durable decisions D-026 through D-030 require local-first, subscription-free text analysis; Modal media-only; a cost-aware evidence cascade; measurement-driven provider adoption; and local workers using the existing Supabase/B2 control plane. D-031 partitions Modal accounts by project. D-032 selects persistent local stdio as the preferred **BookNLP** transport for repeated analysis; it does not adopt BookNLP as a production provider.

## Current Authoritative Checkpoint

Merged `main` at the start of the active qualifier-audit branch is:

`de289a9590e6e4449c942257030a57bc8d65d430`

That merge is PR #234, which added the first source-grounded event semantic qualifier evidence contract.

Latest merged Phase-3 checkpoints include:

- PR #221 — combined speaker V2 challenger;
- PR #222 — dependency-aware event character grounding;
- PR #223 — patient-candidate failure-mode audit;
- PR #225 — real BookNLP proof through the generic one-shot subprocess boundary;
- PR #227 — persistent loaded BookNLP stdio runtime;
- PR #230 — provider-neutral typed non-character event-participant evidence and BookNLP public coverage diagnostic;
- PR #232 — GLiNER typed-entity challenger benchmark, rejecting GLiNER for the current direct world-entity participant slot;
- PR #234 — source-grounded event semantic qualifier evidence.

Current unmerged measured work is issue #235 / PR #236 on branch `v2/phase-3a-event-semantic-qualifier-audit`.

Exact measured audit head:

`95034eef9cfaeb9935756d05fcfc1f3b60dfa2a8`

The audit completed `100 / 100` pinned LitBank documents with `0` failures, typecheck pass, and **`177 / 177` analysis-worker tests passing**, up from `168 / 168` before the audit contract. The test-count increase is regression coverage only, not semantic quality.

No new model inference was run. The audit reused the preserved BookNLP syntax/event artifact from run `34727310506`.

Trigger population and quality remain unchanged:

- triggers: `7,445`;
- precision / recall / F1: `0.8003 / 0.7591 / 0.7791` rounded;
- trigger-count delta: `0`.

The audit found `4,261` candidate negation/modal/conditional cue tokens. `1,528` occur in event-bearing sentences, producing `3,246` cue↔trigger pairs before deterministic nearest-trigger selection. Only `53 / 1,528` nearest-trigger cue associations (`3.47%`) match the strict qualifier policy.

The uncaptured structural distribution is dominated by farther relationships:

- deeper descendants, depth >=2: `961` (`62.89%` of associated cues);
- other connected same-sentence: `354` (`23.17%`);
- sibling/shared head: `149` (`9.75%`);
- direct-child nonqualifying: only `9` (`0.59%`);
- parent/ancestor: only `2` (`0.13%`).

Negation shows the same pattern: `566` negative cues occur in event-bearing sentences, but only `3` are strict captures; `334` are deeper descendants, `82` siblings/shared-head and `146` other connected same-sentence cues.

Decision: **keep the current semantic qualifier policy unchanged.** The audit does not reveal a broad safe one-hop omission. Generic descendant/sibling/nearest-sentence propagation would increase coverage while erasing semantic scope boundaries, and LitBank has no S.A.G.A.-style qualifier-scope/factuality gold to measure the resulting contamination. Unsupported states remain `undetermined`.

Detailed evidence:

- `docs/experiments/BOOKNLP_EVENT_SEMANTIC_QUALIFIERS.md`
- `docs/experiments/BOOKNLP_EVENT_SEMANTIC_QUALIFIER_AUDIT.md`

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

LitBank is **secondary public/gold regression evidence** for reproducible metrics and component isolation. It cannot by itself promote a provider into production. BookNLP's speaker/event models use LitBank-derived annotations, making private modern-fiction qualification especially important.

Copyrighted novel text/EPUB bytes remain private and outside Git. The private EPUB binaries are currently unavailable to the execution environment; do not substitute public-domain novels for the product gate.

## Phase 3 Measured Component State

### Character identity

BookNLP-small is **rejected for primary identity**. Repeatable 100-document LitBank evidence includes canonical precision `0.4613`, recall `0.6030`, incorrect-merge rate `0.1934`, fragmentation `0.4607`, and linked-mention precision `0.2158`.

The deterministic attachment-first resolver remains S.A.G.A.'s policy foundation, but private-suite production qualification is still blocked by source availability.

### Scenes

Scene annotation/evaluation infrastructure and structural/lexical floors are merged. **No scene method is adopted.** Primary-suite annotations remain unavailable.

### Quote detection

- deterministic quote P/R/F1: `0.8570 / 0.8555 / 0.8563`;
- BookNLP quote P/R/F1: `0.7706 / 0.8640 / 0.8146`.

Decision: **retain deterministic quote boundaries as the current public-gold leader**.

### Speaker attribution

Raw component floors with oracle LitBank identity:

- BookNLP matched-known accuracy: `0.7830` vs deterministic `0.3265`;
- BookNLP end-to-end recall: `0.6765` vs deterministic `0.2793`;
- BookNLP contamination: `0.1889` vs deterministic `0.2921`.

Merged combined V2 challenger from PR #221:

- matched-known accuracy: `0.7007`;
- resolved-speaker accuracy: `0.8040`;
- end-to-end recall: `0.5994`;
- contamination: `0.1709`;
- unresolved rate: `0.1285`;
- deterministic quote F1 preserved at `0.8563`.

Decision: **combined V2 is the current public speaker challenger, not a production default**.

### Event triggers

- BookNLP trigger P/R/F1: `0.8003 / 0.7591 / 0.7791`;
- lexical Tier-0 P/R/F1: `0.4914 / 0.0585 / 0.1045`.

BookNLP improves trigger F1 by about `+0.6746` absolute and remains the strongest measured trigger challenger.

### Event participant grounding

PR #222 merged the conservative direct dependency policy: `nsubj`/`agent->pobj` for actors and `dobj`/`nsubjpass` for patients, grounded only through already-linked S.A.G.A. identity spans with matching source locators. Dative, conjunction inheritance and provider cluster IDs remain excluded.

Across `7,445` trigger predictions the corrected public diagnostic measured:

- any grounded participant: `52.13%`;
- actor-opportunity grounding yield: `83.75%`;
- direct syntactic patient-candidate grounding yield: `33.20%`.

The patient audit found **zero true linked-character grounding misses** among `2,546` direct syntactic patient candidates. The low patient-candidate yield is dominated by broad direct-object semantics rather than a measured identity-attachment defect.

These are coverage/failure-mode diagnostics, not participant correctness metrics. Do not broaden attachment rules merely to inflate coverage.

### Typed non-character event participants

BookNLP public diagnostic on the fixed direct-role denominator:

- clean typed non-character candidates: `146 / 6,701` (`2.18%`);
- candidate events gaining typed evidence: `142 / 5,085` (`2.79%`).

GLiNER PR #232 on the same role denominator:

- clean typed non-character candidates: `47 / 6,701` (`0.70%`);
- candidate events gaining typed evidence: `44 / 5,085` (`0.87%`);
- relative coverage vs BookNLP: `0.322x` candidate / `0.310x` event;
- trigger F1 unchanged at `0.7791` rounded.

Decision: **retain the provider-neutral evidence contract, reject GLiNER at this pinned configuration for the current direct-role slot, and do not weaken role or locator policy to make coverage larger.** BookNLP remains the stronger public coverage source for this narrow diagnostic but is still blocked from production by unverified model-weight licensing and the private-corpus gate.

### Event semantic qualifiers

PR #234 merged a deterministic evidence layer over validated trigger/dependency syntax. It records only explicit source-anchored cues and never turns missing evidence into a positive factuality claim.

First public qualifier diagnostic:

- `100 / 100` LitBank documents, `0` failures;
- `168 / 168` tests pass;
- trigger count unchanged at `7,445`;
- trigger P/R/F1 unchanged at `0.8003 / 0.7591 / 0.7791` rounded;
- any explicit qualifier cue: `53` (`0.71%`);
- negated: `3` (`0.04%`);
- modalized: `45` (`0.60%`);
- explicit conditional cue: `5` (`0.07%`);
- irrealis-cued: `50` (`0.67%`);
- unmarked/undetermined: `7,392` (`99.29%`).

Issue #235's 100-document structural audit then increased the model-light regression floor to `177 / 177` and showed that low coverage is **not primarily a missed direct dependency edge**. Only `11 / 1,528` associated cue tokens are uncaptured one-hop cases; most uncaptured cues are farther descendants, siblings or other same-sentence relationships.

Decision: **keep the strict qualifier contract and `undetermined` default unchanged.** Do not propagate cues through generic graph proximity without suitable semantic-scope correctness evidence.

### BookNLP runtime transport

The generic one-shot boundary is validated with exact semantic equality to preserved direct BookNLP evidence.

Persistent BookNLP stdio proof:

- independent-run median analyze latency: `4.627 s` and `2.853 s`;
- one-shot analyze references: `6.314 s` and `8.930 s`;
- peak process-tree RSS remains about `1 GiB`, so persistence is a latency/model-reuse improvement, not a material memory reduction;
- all six persistent passes exactly reproduced the one-shot semantic fingerprint and evidence counts;
- BookNLP model-weight license remains **unverified**.

Decision: **persistent local stdio is preferred for repeated BookNLP execution; one-shot remains the correctness/reference path.** This changes transport, not model quality or production adoption.

## Current Execution Order

1. Merge/close the qualifier coverage audit once exact-head repository gates are green; do not widen qualifier policy from the public structural audit.
2. Move Phase-3 source-neutral work to a genuinely new narrative capability rather than another post-hoc qualifier/provider tuning loop. Prefer a bounded **relationship/state evidence foundation** before timeline/causality, because relationships/state can be source-anchored from already-resolved characters, dialogue, entities and events without pretending to solve chronology first.
3. Keep new public/source-neutral work diagnostic unless suitable gold supports correctness claims.
4. If broader world entities such as artifacts/objects, factions/groups, creatures/species or other story-world classes are needed, introduce them through an explicit ontology contract and separate benchmark; never remap them silently into current labels.
5. When private EPUB access returns, create/score primary-suite scene/dialogue/event/semantic annotations and use those results for production decisions.
6. Adopt no identity, scene, speaker or event method without primary-suite evidence, repeatability, resource/failure review and production-compatible licensing.
7. After a first-pass relationship/state layer is stable, continue chronology/timeline, causality, tension/arcs/themes, then specify the Event / State / Timeline Narrative Graph.

## Working Convention

Every substantial session starts from `AGENTS.md`, this file, `docs/README.md`, `docs/DECISIONS.md`, the Phase-3 contracts, analysis/provider architecture docs, the current-state validation record, component scorecard, and relevant experiment docs.

GitHub is authoritative. Chat history is secondary context only.
