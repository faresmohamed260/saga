# S.A.G.A. Project

S.A.G.A. is being rebuilt as a web-first storytelling-intelligence platform. The active architecture is the S.A.G.A. v2 rebuild; pre-v2 runtime material is historical/reference only unless a current v2 decision deliberately re-adopts an idea behind a v2-owned contract.

This file is the short source-of-truth handoff for current work. For detailed Phase-3A evidence, read `docs/validation/PHASE_V2_3A_CURRENT_STATE_2026-09-12.md`.

## Current Status

**Phase 1 — Closed-Demo Main Site, Accounts & Invitations: COMPLETE.**

**Phase 2 — Story Intake & Character Identity Foundation: REPOSITORY FOUNDATION COMPLETE; ORIGINAL HOSTED-PROVIDER PATH SUPERSEDED.**

- 2A Product/Data Foundation — COMPLETE
- 2B Source Storage & Deterministic Ingestion — COMPLETE
- 2C Character Identity Engine — COMPLETE
- 2D Repository/CI Qualification — COMPLETE
- Phase-2 hosted Supabase migrations — APPLIED AND VERIFIED 2026-09-12
- experimental Modal/xCoRe text-analysis proof — SUPERSEDED by the owner’s local-first analysis decision

**Phase 3 — Local-First Narrative Analysis Rebaseline: ACTIVE.**

Authoritative Phase-3 documents:

- `docs/phases/PHASE_V2_3_LOCAL_FIRST_NARRATIVE_ANALYSIS.md`
- `docs/phases/PHASE_V2_3_PRIMARY_EVALUATION_CORPUS.md`
- `docs/v2/ANALYSIS_ARCHITECTURE_2026.md`
- `docs/validation/PHASE_V2_3A_CURRENT_STATE_2026-09-12.md`

Durable owner decisions D-026 through D-030 require local-first, subscription-free text analysis; Modal media-only; a cost-aware evidence cascade; measurement-driven provider adoption; and local workers using the existing Supabase/B2 control plane.

## Current Authoritative Checkpoint

At the time of this handoff, merged `main` is:

- `d029e465bc37d738debd1ebc8d5d831ab9249661`
- PR #201 — merged the source-neutral dialogue/speaker benchmark foundation after exact-head qualification

Always verify live GitHub state before continuing. This SHA is a handoff checkpoint, not a substitute for checking newer commits/PRs.

## Product Goal

S.A.G.A. is not a book summarizer. Its analysis runtime should reverse-engineer a novel or series into an evidence-linked narrative model covering:

- source/book/chapter/scene structure;
- canonical characters, aliases and mentions;
- dialogue and speaker attribution;
- locations, organizations, objects, creatures, factions and other entities;
- atomic events and grounded participants;
- relationships and changing state;
- narrative order plus story-world chronology and flashbacks;
- causal links, motivations and consequences;
- arcs, tension, conflict, themes and summaries;
- later canon-aware retrieval, visualization, media and generation.

Keep three layers distinct:

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

For every stage prefer:

```text
Tier 0 deterministic structure/rules
  -> Tier 1 lightweight local NLP
  -> Tier 2 specialized local model for unresolved ambiguity
  -> Tier 3 small local generative reasoning over bounded evidence packets only
```

Do not repeatedly pass an entire raw novel through a large LLM merely because a context window permits it. Provider/model output is evidence; deterministic S.A.G.A. policy owns canonical IDs, admission/merge decisions, provenance and accepted/uncertain/rejected state.

## Primary Evaluation Policy

Primary product qualification corpus:

- *Harry Potter and the Philosopher's Stone*;
- *The Cruel Prince*;
- *Caraval*;
- ACOTAR series, with *A Court of Frost and Starlight* retained as the historical regression anchor.

LitBank remains **secondary public/gold regression evidence** for reproducible metrics and component isolation. It cannot by itself promote a provider into production. If LitBank and the private modern-fiction suite disagree, the private suite governs the product decision and the discrepancy must be documented.

Copyrighted novel text/EPUB bytes remain private and outside Git. Repository benchmark artifacts contain only metadata, fingerprints, non-reconstructive labels/diagnostics and expectations.

## Phase 3A Results So Far

### Character/entity evidence

BookNLP-small is **rejected for primary character identity**. Two independent 100-document public-regression runs produced the same semantic output, but identity quality was poor: canonical precision about `0.4613`, recall `0.6030`, incorrect merges `0.1934`, fragmentation `0.4607`, linked-mention precision `0.2158`. Its speaker/event/syntax roles remain separate candidates.

A five-document GLiNER-small-v2.1 + F-Coref public smoke produced useful component evidence but the fully real combined stack is **not adoption-ready**. Do not select or reject individual component roles solely from LitBank; the private suite remains the production gate.

PR #192 / merge `d6c1a144d0c4b4ad82e7229c583cb22682249f07` restored provider-neutral modern-fiction identity regressions such as Harry/Harry Potter, Dumbledore/Professor Dumbledore, Az/Azriel, Cardan/Prince Cardan, supporting-character leakage and fantasy location/group/species contamination.

### Whole-book benchmark foundation

PR #191 / merge `88133be6a7d20cfe02fba26f06e0dd636001fbd0` added a provider-neutral whole-book harness that records source SHA-256, provider/model/revision/license, runtime, RAM/VRAM, output size and semantic fingerprints without storing novel text.

### Scene benchmark foundation

PR #193 / merge `201af2638b4df22aa2734b0cac934fa12b8e3e5e` merged:

- the recovered *Cruel Prince* historical breadth baseline as reference evidence, not gold truth;
- `docs/experiments/SCENE_SEGMENTATION_BENCHMARK.md`;
- local-only scene annotation workspace + CLI;
- source-anchored paragraph IDs;
- exact and relaxed `±1 paragraph` boundary evaluation;
- deterministic structural and lexical scene baselines;
- deterministic regression tests.

Pre-merge review fixed an undercounting greedy tolerant matcher and fail-open partial annotation finalization. Exact head `a3fc13dc81c6fe8f30c218c84e6a81943b7ebfb7` passed all four required CI gates.

**No scene-segmentation method is adopted yet.** Production selection remains blocked on measured primary-suite annotations.

### Dialogue/speaker benchmark foundation

PR #201 / merge `d029e465bc37d738debd1ebc8d5d831ab9249661` merged the first source-neutral dialogue/speaker benchmark slice. Exact head `acf0b4cd5759901bb7a0aa65c802c4957413f9c9` passed Analysis Worker CI, LitBank Oracle Baseline, Backend Architecture CI and Required Check Compatibility.

It provides:

- `docs/experiments/DIALOGUE_SPEAKER_BENCHMARK.md`;
- provider-neutral exact quote-span reference/prediction/evaluation contracts;
- paired curly/straight double-quote deterministic extraction;
- a conservative speech-verb + already-resolved-character attribution sieve;
- exact Unicode code-point source offsets and semantic fingerprints;
- quote precision/recall/F1;
- strict speaker accuracy, resolved-speaker accuracy, unresolved rate, cross-character contamination and end-to-end speaker recall;
- explicit `known` / `unknown` / `ambiguous` gold-speaker semantics;
- deterministic/adversarial tests and CLI entry points.

The Tier-0 baseline intentionally remains unresolved where evidence is weak. Pronoun attribution, paragraph-spanning dialogue, nested quotation handling, dependency-aware attribution and BookNLP speaker evidence remain measured challengers.

**No dialogue/speaker method is adopted yet.** Private-suite qualification is still required.

## Private EPUB Availability

The actual user-owned primary-suite EPUB binaries remain unavailable to the current execution environment.

A File Library recheck on 2026-09-12 found historical notes/scripts and paths but not the EPUB binaries. Remote Desktop Commander also returned no connected devices. Historical paths remain under `B:/Documents/PyCharm/graduationProject/uploads/...`.

Do not replace the primary suite with public-domain novels because of this source-availability blocker. Continue source-neutral benchmark/evidence infrastructure where useful, then run the real books when lawful EPUB access returns.

## Recovered Historical Breadth Baseline

The old graduation prototype processed the complete *The Cruel Prince* and reported 111,351 words, 35 chapters, 135 scenes, 53 unique characters, 55 locations, 24 key causal events, average tension 5.49/10 and reported climax chapter 16. These are coverage/reference observations, not gold targets.

## Existing Phase-2 Foundations To Preserve

- Phase 2A — member-owned projects/sources, forced RLS, durable lease-based jobs, immutable runs and private product surfaces.
- Phase 2B — provider-neutral B2 source contracts, upload verification, hashing, deterministic TXT/EPUB normalization, separate v2 worker.
- Phase 2C — provider-neutral identity evidence, precision-first canonical admission, unresolved/quarantine policy, deterministic stabilization and immutable character/alias/mention evidence.
- Phase 2D — repository qualification, LitBank oracle-policy ceiling/reference and job lifecycle hardening.

## Hosted Resources / Boundaries

- **Supabase:** dedicated project `scmeqnpmhomzcwecjdtu`, region `eu-central-1`; five repository-qualified Phase-2 migrations applied and verified 2026-09-12.
- **Backblaze B2:** private bucket `saga-v2-faresmohamed260-1207062480`, region `us-east-005`; master credentials bootstrap-only, runtime must use scoped non-master keys.
- **Modal:** image/media only. Do not revive the old hosted text-analysis proof as the production path.
- **Vercel:** project `saga`, root `apps/web`; automatic Git-triggered deployments disabled. Any Preview or Production deployment requires fresh explicit owner approval after stating reason, deployment type and exact SHA.

## Current Execution Order

1. verify live `main`, PR/issue state and repository governance before every new implementation slice;
2. while primary EPUBs are unavailable, continue source-neutral Phase-3A benchmark/evidence foundations that do not pretend to establish product quality;
3. next source-neutral slice: event-candidate/participant evaluation contracts and a conservative deterministic verb-candidate floor, while leaving dependency-aware and BookNLP event challengers explicit;
4. when private EPUBs become reachable, create scene and dialogue annotation workspaces first for Harry Potter, The Cruel Prince, Caraval and ACOFAS and score the merged baselines;
5. test stronger permissively licensed local candidates only where cheaper tiers leave a measured quality gap;
6. adopt no scene, speaker, identity or event provider without primary-suite evidence, repeatability, resource cost, failure-mode review and production-compatible licensing;
7. after measured first-pass evidence stacks exist, continue with locations/entities, tension, relationships/state, timeline and causality;
8. wire adopted local providers into the durable worker only after benchmark evidence justifies them;
9. use measured Phase-3 evidence to specify the later Event / State / Timeline Narrative Graph contract.

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
9. relevant active experiment docs such as `docs/experiments/SCENE_SEGMENTATION_BENCHMARK.md` and `docs/experiments/DIALOGUE_SPEAKER_BENCHMARK.md`

GitHub is authoritative. Chat history is secondary context only.
