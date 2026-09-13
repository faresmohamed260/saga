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

Durable owner decisions D-026 through D-030 require local-first, subscription-free text analysis; Modal media-only; a cost-aware evidence cascade; measurement-driven provider adoption; and local workers using the existing Supabase/B2 control plane.

## Current Authoritative Checkpoint

At this handoff, merged `main` is:

- `a3aba893f92e9e98e29d5e6f97e08672cc80637f`
- PR #212 — repeatable public BookNLP quote/speaker/event component benchmark

Exact final PR #212 head:

- `280a2132d78ba8312d38f2d1f74267160830cd74`
- Required Check Compatibility — success
- S.A.G.A. v2 Analysis Worker CI — success
- S.A.G.A. v2 LitBank Oracle Baseline — success
- Backend Architecture CI — success

PR #210 / merge `9dfdd7e0c1234c021c9b2d2e5526a27b3d89bfe3` previously instantiated the BookNLP quote/speaker/event provider-specific subprocess adapter behind the generic local literary provider boundary.

Always verify live GitHub state before continuing. This SHA is a handoff checkpoint, not a substitute for checking newer commits/PRs.

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

Copyrighted novel text/EPUB bytes remain private and outside Git.

## Phase 3 Measured Component State

### Character identity

BookNLP-small is **rejected for primary identity**. Repeatable 100-document LitBank evidence includes canonical precision `0.4613`, recall `0.6030`, incorrect-merge rate `0.1934`, fragmentation `0.4607`, and linked-mention precision `0.2158`.

The deterministic attachment-first resolver remains S.A.G.A.'s policy foundation, but private-suite production qualification is still blocked by source availability.

### Scenes

Scene annotation/evaluation infrastructure and structural/lexical floors are merged. **No scene method is adopted.** Primary-suite annotations remain unavailable.

### Quote detection

PR #212 measured 100 pinned LitBank documents twice with identical semantic output:

- deterministic quote P/R/F1: `0.8570 / 0.8555 / 0.8563`;
- BookNLP quote P/R/F1: `0.7706 / 0.8640 / 0.8146`.

Decision: **retain deterministic quote boundaries as the current public-gold leader**.

### Speaker attribution

With oracle LitBank identity used only to isolate attribution quality:

- BookNLP matched-known accuracy: `0.7830` vs deterministic `0.3265`;
- BookNLP end-to-end recall: `0.6765` vs deterministic `0.2793`;
- BookNLP contamination: `0.1889` vs deterministic `0.2921`;
- BookNLP unresolved rate: `0.0282` vs deterministic `0.3815`.

Decision: BookNLP is a **strong restricted speaker challenger**, but `18.89%` contamination is too high for direct canonical use. Issue #213 / PR #215 measure a combined deterministic-quote + confidence-gated BookNLP-speaker policy.

### Event triggers

- BookNLP trigger P/R/F1: `0.8003 / 0.7591 / 0.7791`;
- lexical Tier-0 P/R/F1: `0.4914 / 0.0585 / 0.1045`.

BookNLP improves trigger F1 by about `+0.6746` absolute and is the strongest measured trigger challenger. This does **not** qualify participant grounding, negation/modality/realis, state, causality or canonical event acceptance. Issue #214 tracks dependency-aware participant grounding.

### Repeatability / resources

Two independent 100-document BookNLP component runs produced identical semantic fingerprint:

`e0ec94d8d1f678f98057a29117d365926a3253a4a6d5e6e0f7c96e36cab3bef9`

- run 1: `452.68 s`, `1123.8 MiB` peak RSS;
- run 2: `293.66 s`, `1157.2 MiB` peak RSS;
- model artifacts: `160,398,571 bytes`;
- each run: `100 / 100` documents, `0` failures;
- heavyweight validation: `111 / 111` analysis-worker tests passed on both attempts.

BookNLP model-weight license remains **unverified** and blocks production adoption.

## Phase 3B Runtime State

PR #207 merged the generic `LocalLiteraryEvidenceProvider` subprocess execution/validation boundary. PR #210 added the BookNLP-specific process/runner adapter while normal CI remained model-light.

Important distinction: PR #212's real model benchmark used the dedicated benchmark harness; it did **not** execute the real model end-to-end through the generic subprocess boundary. That measured boundary proof remains open.

Subprocess is also not permanently selected over loopback HTTP. Compare transports only after real startup/throughput measurements justify the comparison.

## Private EPUB Availability

The actual user-owned primary-suite EPUB binaries remain unavailable to the current execution environment. Historical paths remain under `B:/Documents/PyCharm/graduationProject/uploads/...`.

Do not replace the private suite with public-domain books. Continue source-neutral benchmark/runtime work, then run the real product gate when lawful EPUB access returns.

## Current Execution Order

1. qualify PR #215's combined deterministic-quote + gated BookNLP-speaker policy by measuring contamination versus recall on the same pinned LitBank benchmark;
2. develop BookNLP-triggered dependency-aware event participant grounding under issue #214;
3. execute a real BookNLP run through the generic subprocess boundary with exact preinstalled artifacts/caches; compare persistent loopback only if startup/runtime measurements justify it;
4. when private EPUBs become reachable, create/score scene/dialogue/event annotations for the primary modern-fiction suite;
5. adopt no identity, scene, speaker or event method without primary-suite evidence, repeatability, resource/failure review and production-compatible licensing;
6. after measured first-pass evidence stacks exist, continue locations/entities, relationships/state, timeline, causality, tension/arcs/themes, then specify the Event / State / Timeline Narrative Graph.

## Working Convention

Every substantial session starts from `AGENTS.md`, this file, `docs/README.md`, `docs/DECISIONS.md`, the Phase-3 contracts, analysis/provider architecture docs, the current-state validation record, component scorecard, and relevant experiment docs.

GitHub is authoritative. Chat history is secondary context only.
