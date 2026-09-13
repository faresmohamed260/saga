# S.A.G.A. Project

S.A.G.A. is being rebuilt as a web-first storytelling-intelligence platform. The active architecture is S.A.G.A. v2; pre-v2 runtime material is historical/reference only unless a current v2 decision explicitly re-adopts an idea behind a v2-owned contract.

This file is the short source-of-truth handoff. For detailed Phase-3 state and measured component evidence, read:

- `docs/validation/PHASE_V2_3A_CURRENT_STATE_2026-09-12.md`
- `docs/validation/PHASE_V2_3_COMPONENT_SCORECARD.md`

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

At this handoff, merged `main` is:

`7261d9c31adacdb80b7304f1e47808353f42e152`

Latest merged checkpoints:

- PR #223 — patient-candidate failure-mode audit;
- PR #225 — real BookNLP proof through the generic one-shot subprocess boundary;
- PR #227 — persistent loaded BookNLP stdio runtime, completing issue #226.

The persistent runtime was measured twice on exact implementation head `2fa30b185cb037180f3e7762f2166067096e08c5`. Across six real analyses it reproduced the exact validated one-shot evidence fingerprint and exact counts. Model-light qualification is **145 / 145 tests passing**, up from the prior `139 / 139` baseline.

Persistent median analyze latency measured `4.627 s` and `2.853 s` on two independent hosted runners versus one-shot measurements of `6.314 s` and `8.930 s`. Peak process-tree RSS remained close to one-shot, so persistence is a latency/model-reuse improvement rather than a material memory reduction. Cold startup is not faster than one-shot health.

Decision: **when S.A.G.A. invokes BookNLP repeatedly, use the persistent local stdio runtime; keep one-shot subprocess execution as the simple correctness/reference path.**

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

The patient audit then found **zero true linked-character grounding misses** among `2,546` direct syntactic patient candidates. The low patient-candidate yield is dominated by broad direct-object semantics, especially common nouns/pronouns, rather than a measured identity-attachment defect.

These are coverage/failure-mode diagnostics, not participant correctness metrics. Do not broaden attachment rules merely to inflate coverage.

### BookNLP runtime transport

The generic one-shot boundary is validated with exact semantic equality to preserved direct BookNLP evidence.

Persistent BookNLP stdio proof, exact implementation head `2fa30b185cb037180f3e7762f2166067096e08c5`:

- attempt 1 median analyze: `4.627 s`, peak RSS `1007.1 MiB`;
- attempt 2 median analyze: `2.853 s`, peak RSS `1028.7 MiB`;
- validated one-shot analyze measurements: `6.314 s` and `8.930 s`;
- all six persistent passes exactly reproduced evidence fingerprint `8be0f789a80ecf47c0b902b51e0492c17ef016023c3e215df6a4d57ff3e27add`;
- exact evidence counts stayed `230 / 230 / 5 / 20 / 2,319`;
- model-light and heavyweight qualification: `145 / 145` tests pass;
- full prepared offline runtime footprint remains about `439 MiB`;
- BookNLP model-weight license remains **unverified**.

Decision: **persistent local stdio is preferred for repeated BookNLP execution; one-shot remains the correctness/reference path.** This changes transport, not model quality or production adoption.

Detailed evidence:

- `docs/experiments/BOOKNLP_SUBPROCESS_RUNTIME_PROOF.md`
- `docs/experiments/BOOKNLP_PERSISTENT_RUNTIME_PROOF.md`

## Current Execution Order

1. Return Phase-3 work from runtime plumbing to **new narrative semantic capability**.
2. For events, prefer genuinely new information—starting with explicit **non-character entity participants** and/or negation/modality/realis—rather than expanding character-attachment rules for higher coverage.
3. Keep new public/source-neutral event work diagnostic unless suitable gold supports correctness claims.
4. When private EPUB access returns, create/score primary-suite scene/dialogue/event annotations and use those results for production decisions.
5. Adopt no identity, scene, speaker or event method without primary-suite evidence, repeatability, resource/failure review and production-compatible licensing.
6. After first-pass event/entity evidence is stable, continue relationships/state, timeline, causality, tension/arcs/themes, then specify the Event / State / Timeline Narrative Graph.

## Working Convention

Every substantial session starts from `AGENTS.md`, this file, `docs/README.md`, `docs/DECISIONS.md`, the Phase-3 contracts, analysis/provider architecture docs, the current-state validation record, component scorecard, and relevant experiment docs.

GitHub is authoritative. Chat history is secondary context only.