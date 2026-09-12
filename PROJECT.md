# S.A.G.A. Project

S.A.G.A. is being rebuilt as a web-first storytelling-intelligence platform. The active architecture is the S.A.G.A. v2 rebuild; pre-v2 runtime material is historical/reference only unless a current v2 decision deliberately re-adopts an idea behind a v2-owned contract.

This file is the short source-of-truth handoff for current work. For the detailed Phase-3A state, read `docs/validation/PHASE_V2_3A_CURRENT_STATE_2026-09-12.md`.

## Current Status

**Phase 1 — Closed-Demo Main Site, Accounts & Invitations: COMPLETE.**

**Phase 2 — Story Intake & Character Identity Foundation: REPOSITORY FOUNDATION COMPLETE; ORIGINAL HOSTED-PROVIDER PATH SUPERSEDED.**

- 2A Product/Data Foundation — COMPLETE
- 2B Source Storage & Deterministic Ingestion — COMPLETE
- 2C Character Identity Engine — COMPLETE
- 2D Repository/CI Qualification — COMPLETE
- Phase-2 hosted Supabase migrations — APPLIED AND VERIFIED 2026-09-12
- experimental Modal/xCoRe worker/provider proof — SUPERSEDED by the owner’s local-first analysis decision

**Phase 3 — Local-First Narrative Analysis Rebaseline: ACTIVE.**

Authoritative Phase-3 documents:

- `docs/phases/PHASE_V2_3_LOCAL_FIRST_NARRATIVE_ANALYSIS.md`
- `docs/phases/PHASE_V2_3_PRIMARY_EVALUATION_CORPUS.md`
- `docs/v2/ANALYSIS_ARCHITECTURE_2026.md`
- `docs/validation/PHASE_V2_3A_CURRENT_STATE_2026-09-12.md`

Durable owner decisions D-026 through D-030 require local-first, subscription-free text analysis; Modal media-only; a cost-aware evidence cascade; measurement-driven provider adoption; and local workers using the existing Supabase/B2 control plane.

## Current Authoritative Checkpoint

At the time of this handoff, merged `main` is:

- `d6c1a144d0c4b4ad82e7229c583cb22682249f07`
- PR #192 — restored the primary-fiction regression evaluator

Always verify live GitHub state before continuing. This SHA is a handoff checkpoint, not a substitute for checking newer commits/PRs.

## Product Goal

S.A.G.A. is not a book summarizer. Its analysis runtime should progressively reverse-engineer a novel or series into an evidence-linked narrative model supporting:

- source/book/chapter/scene structure;
- canonical characters, aliases and mentions;
- dialogue and speaker attribution;
- locations, organizations, objects, creatures, factions and other entities;
- atomic events and grounded participants;
- relationships and how they change;
- character/world state over time;
- narrative order plus story-world chronology and flashbacks;
- causal links, motivations and consequences;
- higher-level arcs, tension, conflict, themes and summaries;
- later canon-aware retrieval, visualization, media and generation.

Keep three conceptual layers distinct:

1. **source layer** — immutable text/structure and exact evidence spans;
2. **resolved layer** — identities, references, speakers and other confidence-gated interpretation;
3. **derived intelligence layer** — events, relationships, state, timeline, causality and higher narrative models.

Do not rewrite source text when later evidence changes interpretation.

## Locked Analysis Strategy

The default textual-analysis topology is:

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

The analysis host should require outbound HTTPS only. No public inbound home-server port is required.

The existing TypeScript `services/analysis-worker` remains the preferred job/orchestration owner unless measurements prove a better reason to change it.

For every stage prefer:

```text
Tier 0 deterministic structure/rules
  -> Tier 1 lightweight local NLP
  -> Tier 2 specialized local model for unresolved ambiguity
  -> Tier 3 small local generative reasoning over bounded evidence packets only
```

Do not repeatedly pass an entire raw novel through a large LLM merely because a context window permits it. Provider/model output is evidence; deterministic S.A.G.A. policy owns canonical IDs, admission/merge decisions, provenance and accepted/uncertain/rejected state.

## Primary Evaluation Policy

The owner explicitly corrected the benchmark priority during Phase 3A.

**Primary product qualification corpus:**

- *Harry Potter and the Philosopher's Stone*;
- *The Cruel Prince*;
- *Caraval*;
- ACOTAR series, with *A Court of Frost and Starlight* retained as the historical regression anchor.

LitBank remains **secondary public/gold regression evidence** for reproducible metrics and component isolation. It cannot by itself promote a provider into production. If LitBank and the private modern-fiction suite disagree, the private suite governs the product decision and the discrepancy must be documented.

The repository stores only metadata, fingerprints, bounded diagnostics and expectations for copyrighted books. Novel text/EPUB bytes remain private and outside Git.

## Phase 3A Results So Far

### Experiment governance

Provider adoption is results-driven. Every experiment must preserve source/model/config/resource provenance, including negative and rejected candidates. Repeatability requires multiple completed runs; one successful result is not enough.

### BookNLP-small

BookNLP-small is **rejected for primary character identity**. Two independent 100-document public-regression runs produced the same semantic output, but identity quality was poor: canonical precision about `0.4613`, recall `0.6030`, incorrect merges `0.1934`, fragmentation `0.4607`, linked-mention precision `0.2158`. Its speaker/event/syntax outputs remain separate candidates.

### GLiNER-small-v2.1 + F-Coref

A technically valid five-document public smoke produced useful component evidence but the fully real combined stack is **not adoption-ready**. Approximate smoke results: GLiNER proper-name PERSON precision `0.763`, recall `0.657`; F-Coref with oracle mentions canonical precision `0.780`, recall `0.889`, incorrect merges `0.180`; combined real stack canonical precision `0.412`, recall `0.500`, linked-mention precision `0.076`.

Do not select or reject individual GLiNER/F-Coref roles solely from LitBank. The private suite is the production gate.

### Whole-book benchmark foundation

PR #191 / merge `88133be6a7d20cfe02fba26f06e0dd636001fbd0` added a provider-neutral whole-book harness that records source SHA-256, provider/model/revision/license, runtime, RAM/VRAM, output size and semantic fingerprints without storing novel text.

### Primary-fiction identity regressions

PR #192 / merge `d6c1a144d0c4b4ad82e7229c583cb22682249f07` restored provider-neutral regressions for the historical real-book failures, including Harry/Harry Potter, Dumbledore/Professor Dumbledore, Az/Azriel, Cardan/Prince Cardan, supporting-character leakage, and fantasy location/group/species contamination.

Opening-prefix expectations are kept separate from full-book expectations.

## Private EPUB Availability

The actual user-owned EPUB binaries are currently **not available in ChatGPT File Library**.

Historical test records reference old local paths under `B:/Documents/PyCharm/graduationProject/uploads/...`, but the connected Remote Desktop Commander had no online authorized device during the handoff session.

Do not replace the primary suite with public-domain novels because of this temporary availability issue. Continue building and qualifying source-neutral harnesses, then run the real books when lawful EPUB access returns.

## Active Unmerged Work — Scene Segmentation

**Continue this branch; do not recreate it:**

- branch: `v2/phase-3a-cruel-prince-analysis-baseline`
- handoff head: `cc28f37270c389f7be288f48245105d4f9fdefc7`
- ahead of merged `main` checkpoint by 21 commits at handoff

Exact-head checks at that SHA are green:

- SAGA v2 Analysis Worker CI — success
- SAGA v2 LitBank Oracle Baseline — success
- Backend Architecture CI — success
- Required Check Compatibility — success

The branch already contains:

- recovered *Cruel Prince* historical full-analysis reference data;
- `docs/experiments/SCENE_SEGMENTATION_BENCHMARK.md`;
- scene annotation workspace + CLI;
- exact and relaxed scene-boundary evaluator + CLI;
- deterministic structural scene baseline + CLI;
- cheap lexical scene-change baseline + CLI;
- deterministic tests for all of the above.

Scene gold/reference data is paragraph-indexed and contains no copyrighted prose. Exact boundary F1 and relaxed `±1 paragraph` F1 are both retained; ambiguous/disputed boundaries are explicitly represented so annotator uncertainty does not become fake model error.

No scene method has been adopted yet.

## Recovered Historical Breadth Baseline

The old graduation prototype processed the complete *The Cruel Prince* and reported:

- 111,351 words;
- 35 chapters;
- 135 scenes;
- 53 unique characters;
- 55 locations;
- 24 key causal events;
- average tension 5.49/10;
- reported climax chapter 16.

These are **coverage/reference observations, not gold targets**. The new architecture should reproduce or improve analytical breadth while being cheaper, more reproducible, source-grounded and reliable.

## Existing Phase-2 Foundations To Preserve

- Phase 2A — member-owned projects/sources, forced RLS, durable lease-based jobs, immutable runs and private product surfaces.
- Phase 2B — provider-neutral B2 source contracts, upload verification, hashing, deterministic TXT/EPUB normalization, separate v2 worker.
- Phase 2C — provider-neutral identity evidence, precision-first canonical admission, unresolved/quarantine policy, deterministic stabilization and immutable character/alias/mention evidence.
- Phase 2D — repository qualification, LitBank oracle-policy ceiling/reference and job lifecycle hardening.

The 100-document LitBank oracle-evidence resolver ceiling remains useful as a policy reference, not as a production-provider score.

## Hosted Resources / Boundaries

### Supabase

Dedicated project ref `scmeqnpmhomzcwecjdtu`, region `eu-central-1`. All five repository-qualified Phase-2 migrations were applied and verified on 2026-09-12.

### Backblaze B2

Dedicated private bucket `saga-v2-faresmohamed260-1207062480`, region `us-east-005`. Master credentials remain bootstrap/operator-only; runtime access must use scoped non-master application keys.

### Modal

Modal is reserved for image/media generation. The old `ops/phase2-hosted-proof` text-analysis experiment is non-authoritative and must not be revived as the production NLP runtime.

### Vercel

Dedicated project `saga`, root `apps/web`. Automatic Git-triggered deployments are disabled. Before any Preview or Production deploy, state reason, deployment type and exact SHA, then obtain fresh explicit owner approval.

## Current Execution Order

1. verify live `main`, active branch/PR state and issue #185;
2. read the mandatory governance/Phase-3 docs plus `docs/validation/PHASE_V2_3A_CURRENT_STATE_2026-09-12.md`;
3. continue from `v2/phase-3a-cruel-prince-analysis-baseline` instead of rebuilding the scene foundation;
4. review the 21-commit scene slice, fix benchmark-integrity issues if any, and open/qualify a PR when appropriate;
5. once private EPUBs are reachable, generate scene annotation workspaces for Harry Potter, The Cruel Prince, Caraval and ACOFAS first and annotate representative chapter types;
6. compare structural, lexical/local semantic and later licensed local model candidates using exact + relaxed scene metrics and resource measurements;
7. after scene segmentation has a measured baseline, proceed independently to dialogue/speaker, event/participant, location/entity and tension experiments;
8. choose production defaults only from real primary-suite evidence, repeatability, resource cost, failure modes, maintainability and licensing;
9. wire adopted local providers into the durable worker only after benchmark evidence justifies them;
10. use measured Phase-3 evidence to specify the later Event / State / Timeline Narrative Graph contract.

## Working Convention

Every substantial session starts from:

1. `AGENTS.md`
2. `PROJECT.md`
3. `docs/README.md`
4. `docs/DECISIONS.md`
5. `docs/phases/PHASE_V2_3_LOCAL_FIRST_NARRATIVE_ANALYSIS.md`
6. `docs/phases/PHASE_V2_3_PRIMARY_EVALUATION_CORPUS.md`
7. `docs/v2/ANALYSIS_ARCHITECTURE_2026.md`
8. `docs/validation/PHASE_V2_3A_CURRENT_STATE_2026-09-12.md`
9. relevant active experiment docs such as `docs/experiments/SCENE_SEGMENTATION_BENCHMARK.md`

GitHub is authoritative. Chat history is secondary context only.
