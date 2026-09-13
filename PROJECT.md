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

Durable owner decisions D-026 through D-030 require local-first, subscription-free text analysis; Modal media-only; a cost-aware evidence cascade; measurement-driven provider adoption; and local workers using the existing Supabase/B2 control plane. D-031 partitions Modal accounts by project and does not change the text-analysis prohibition.

## Current Authoritative Checkpoint

At this handoff, merged `main` is:

- `a3396e5cc829008a4bed2af87186726a3e201123`
- PR #222 — merged dependency-aware event participant-grounding challenger infrastructure

PR #222 exact qualified head was `1878167b6344dee34f435831169ac88003d2b3e0`; Required Check Compatibility, S.A.G.A. v2 Analysis Worker CI, S.A.G.A. v2 LitBank Oracle Baseline and Backend Architecture CI all passed before merge.

The follow-up patient-candidate failure-mode audit is on branch `v2/phase-3a-event-patient-audit`. Its exact measured scorer head `dc71151491e8fafb8f92f3fad98921bdb57d1c2d` reused the same preserved BookNLP inference, completed `100 / 100` LitBank documents with zero failures, passed typecheck and `139 / 139` analysis-worker tests, and produced report fingerprint `c8f36fb6a0af333c70c038e7dbe42ef94d78c3d1daf5b41fae24d6e4d412a571`.

Always verify live GitHub state before continuing. These SHAs are handoff checkpoints, not substitutes for checking newer commits/PRs.

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

V2 improves end-to-end recall by `+0.1150` absolute over rejected V1 and keeps contamination `0.0180` absolute below raw BookNLP. It retains about `80.6%` of BookNLP's incremental recall gain over the deterministic floor.

Decision: **combined V2 is the current public speaker challenger, not a production default**.

### Event triggers

- BookNLP trigger P/R/F1: `0.8003 / 0.7591 / 0.7791`;
- lexical Tier-0 P/R/F1: `0.4914 / 0.0585 / 0.1045`.

BookNLP improves trigger F1 by about `+0.6746` absolute and remains the strongest measured trigger challenger.

### Event participant grounding

PR #222 merged issue #214's conservative direct dependency policy: `nsubj`/`agent->pobj` for actors and `dobj`/`nsubjpass` for patients, grounded only through already-linked S.A.G.A. identity spans with matching source locators. Dative, conjunction inheritance and provider cluster IDs remain excluded.

The corrected 100-document scorer measured across `7,445` trigger predictions:

- any grounded participant: `3,881` (`52.13%`);
- actor: `3,406` (`45.75%`);
- patient: `822` (`11.04%`);
- actor + patient: `347` (`4.66%`);
- actor opportunity grounding yield: `83.75%`;
- direct syntactic patient-candidate grounding yield: `33.20%`.

Trigger P/R/F1 remained exactly `0.8003 / 0.7591 / 0.7791`.

The follow-up patient audit explains the low direct-patient candidate yield rather than treating it as an attachment bug. Across `2,546` direct `dobj`/`nsubjpass` candidates:

- grounded character: `824` (`32.36%`);
- same-character duplicate already grounded through another mention: `4`;
- **true linked-character grounding misses: `0`**;
- structural-locator mismatches: `0`;
- gold-linked people missing from oracle identity: `0`;
- ambiguous linked characters: `17`;
- no identity/entity evidence: `1,503` (`59.03%`).

Of the no-entity bucket, `1,216 / 1,503` (`80.90%`) are `NOUN`, `226` (`15.04%`) are `PRON`, and only `7` (`0.47%`) are `PROPN`. `dobj` dominates the candidate denominator (`2,304 / 2,546`, `90.49%`) and grounds as a character only `29.77%` of the time, while `nsubjpass` grounds `57.02%`.

These are coverage/failure-mode diagnostics, **not participant correctness metrics**, because LitBank event annotations do not provide S.A.G.A.-style actor/patient gold.

Decision: **keep the strict character-grounding policy unchanged**. Do not enable dative, conjunction inheritance or provider clusters merely to inflate coverage. Direct dependency grounding remains the current public participant-grounding challenger infrastructure, not a production event default.

Detailed evidence:

- `docs/experiments/BOOKNLP_EVENT_DEPENDENCY_GROUNDING.md`
- `docs/experiments/BOOKNLP_EVENT_PATIENT_AUDIT.md`

### Repeatability / resources

Two independent 100-document BookNLP component runs produced identical semantic fingerprint:

`e0ec94d8d1f678f98057a29117d365926a3253a4a6d5e6e0f7c96e36cab3bef9`

- run 1: `452.68 s`, `1123.8 MiB` peak RSS;
- run 2: `293.66 s`, `1157.2 MiB` peak RSS;
- model artifacts: `160,398,571 bytes`;
- each run: `100 / 100` documents, `0` failures.

BookNLP model-weight license remains **unverified** and blocks production adoption.

Deterministic speaker/event policy scorers reuse the preserved native BookNLP output instead of rerunning the heavyweight model for every policy change.

## Phase 3B Runtime State

PR #207 merged the generic `LocalLiteraryEvidenceProvider` subprocess execution/validation boundary. PR #210 added the BookNLP-specific process/runner adapter while normal CI remained model-light. PR #217 exposed validated provider-neutral syntax evidence required for dependency-aware event grounding.

Important distinction: the real 100-document BookNLP benchmarks use the dedicated benchmark harness. They do **not** yet prove the real model end-to-end through the generic subprocess protocol. That measured boundary proof remains open.

Subprocess is also not permanently selected over loopback HTTP. Compare transports only after real startup/throughput measurements justify the comparison.

## Private EPUB Availability

The actual user-owned primary-suite EPUB binaries remain unavailable to the current execution environment. Historical paths remain under `B:/Documents/PyCharm/graduationProject/uploads/...`.

Do not replace the private suite with public-domain books. Continue source-neutral benchmark/runtime work, then run the real product gate when lawful EPUB access returns.

## Current Execution Order

1. qualify and merge the event patient failure-mode audit so the strict grounding decision and denominator semantics are durable;
2. execute a real BookNLP run through the generic subprocess boundary with exact preinstalled artifacts/caches; compare persistent loopback only if startup/runtime measurements justify it;
3. for event semantics, prefer genuinely new capability—non-character entity participants and negation/modality/realis—over attachment-rule expansion that merely raises coverage;
4. when private EPUBs become reachable, create/score scene/dialogue/event annotations for the primary modern-fiction suite;
5. adopt no identity, scene, speaker or event method without primary-suite evidence, repeatability, resource/failure review and production-compatible licensing;
6. after measured first-pass evidence stacks exist, continue locations/entities, relationships/state, timeline, causality, tension/arcs/themes, then specify the Event / State / Timeline Narrative Graph.

## Working Convention

Every substantial session starts from `AGENTS.md`, this file, `docs/README.md`, `docs/DECISIONS.md`, the Phase-3 contracts, analysis/provider architecture docs, the current-state validation record, component scorecard, and relevant experiment docs.

GitHub is authoritative. Chat history is secondary context only.
