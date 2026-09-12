# S.A.G.A. Documentation Index

S.A.G.A. is in an owner-authorized v2 rebuild. This index separates the **active v2 source of truth** from retained **v1 historical/reference material**.

## Read First

For substantial current work, read in this order:

1. `../AGENTS.md`
2. `../PROJECT.md`
3. `DECISIONS.md`
4. the active phase contract referenced by `PROJECT.md`
5. any active owner-directed phase amendment
6. the relevant `v2/` architecture document
7. the current validation/handoff record for the active phase

GitHub is authoritative. Do not reconstruct project state from chat history when the repository can establish it.

## Current Phase State

**Phase 1 — Closed-Demo Main Site, Accounts & Invitations: COMPLETE.**

**Phase 2 — Story Intake & Character Identity Foundation: REPOSITORY FOUNDATION COMPLETE; ORIGINAL HOSTED-TEXT-PROVIDER PATH SUPERSEDED.**

- 2A Product/Data Foundation — COMPLETE
- 2B Source Storage & Deterministic Ingestion — COMPLETE
- 2C Character Identity Engine — COMPLETE
- 2D Repository/CI Qualification — COMPLETE
- hosted Phase-2 Supabase migrations — APPLIED/VERIFIED 2026-09-12
- experimental Modal/xCoRe text-analysis proof — SUPERSEDED by owner decision

**Phase 3 — Local-First Narrative Analysis Rebaseline: ACTIVE.**

Authoritative contract:

- `phases/PHASE_V2_3_LOCAL_FIRST_NARRATIVE_ANALYSIS.md`

Active owner-directed benchmark-corpus amendment:

- `phases/PHASE_V2_3_PRIMARY_EVALUATION_CORPUS.md` — contemporary/private fiction is the primary product qualification corpus; LitBank is secondary public regression evidence.

Authoritative analysis architecture:

- `v2/ANALYSIS_ARCHITECTURE_2026.md`

Current detailed handoff:

- `validation/PHASE_V2_3A_CURRENT_STATE_2026-09-12.md`

Phase 2 remains the durable application/control-plane foundation. Its original plan to prove a permanent hosted text worker/provider is no longer the architecture target; end-to-end acceptance moves to the local-first worker path.

## Latest Phase 3A Progress

Merged work now includes:

- benchmark-before-adoption experiment governance;
- BookNLP-small primary-identity evaluation and rejection for that role;
- GLiNER/F-Coref component smoke evidence;
- provider-neutral whole-book benchmark infrastructure;
- the owner-directed private primary fiction suite;
- restored real-book identity regressions for Harry Potter, The Cruel Prince, Caraval and ACOFAS.

Important merged checkpoints:

- PR #191 / merge `88133be6a7d20cfe02fba26f06e0dd636001fbd0` — whole-book benchmark foundation + primary private fiction corpus;
- PR #192 / merge `d6c1a144d0c4b4ad82e7229c583cb22682249f07` — primary-fiction identity regression evaluator.

### Active unmerged scene-analysis branch

Do not recreate this work. Continue from:

- branch `v2/phase-3a-cruel-prince-analysis-baseline`;
- handoff head `cc28f37270c389f7be288f48245105d4f9fdefc7`.

At that head the branch was 21 commits ahead of the merged checkpoint and all exact-head checks were green.

It already contains:

- `experiments/2026-09-12_CRUEL_PRINCE_HISTORICAL_ANALYSIS_BASELINE.md`;
- `experiments/SCENE_SEGMENTATION_BENCHMARK.md`;
- scene annotation workspace/CLI;
- exact + relaxed scene-boundary evaluator/CLI;
- structural scene baseline/CLI;
- lexical scene-change baseline/CLI;
- deterministic tests for the scene benchmark stack.

No scene method has been adopted yet.

## Locked Analysis Direction

Owner decisions D-026 through D-030 require:

- textual analysis that works without paid AI APIs/subscriptions;
- Modal reserved for image/media generation, not book NLP/reasoning;
- deterministic/classical/local methods before generative inference;
- whole-book resource accounting as part of provider selection;
- an outbound-only local analysis worker using the existing Supabase durable queue and B2 storage boundaries;
- model/provider output treated as evidence, while deterministic S.A.G.A. policy owns canonical product truth.

The corpus amendment additionally requires that production provider selection be judged primarily on the private modern-fiction suite built around Harry Potter, The Cruel Prince, Caraval and ACOTAR. LitBank remains useful for reproducible gold metrics but cannot by itself promote a provider.

The governing analysis cascade is:

```text
Tier 0 deterministic structure/rules
  -> Tier 1 lightweight local NLP
  -> Tier 2 specialized local model for unresolved ambiguity
  -> Tier 3 small local structured reasoning over bounded evidence packets
```

Do not repeatedly pass a full raw novel through a large generative model merely because a context window exists.

## Primary Fiction Evaluation

Primary product qualification material:

- *Harry Potter and the Philosopher's Stone*;
- *The Cruel Prince*;
- *Caraval*;
- ACOTAR series, with *A Court of Frost and Starlight* as a historical regression anchor.

Primary-suite metadata and protocols:

- `../services/analysis-worker/benchmarks/whole-book-primary-fiction-suite.v1.json`;
- `experiments/WHOLE_BOOK_BENCHMARK.md`;
- `phases/PHASE_V2_3_PRIMARY_EVALUATION_CORPUS.md`.

The actual user-owned EPUBs are currently not available through ChatGPT File Library, and the historical remote machine was not online through the connected desktop integration at handoff. This is a source-availability blocker for real primary-suite runs, not a reason to substitute public-domain books as the production gate.

## Active v2 Architecture / Product Contracts

- `../AGENTS.md` — mandatory working rules/source-of-truth order
- `../PROJECT.md` — current handoff and immediate execution order
- `DECISIONS.md` — durable cross-cutting decisions
- `v2/ARCHITECTURE.md` — web/data/storage/deployment ownership
- `v2/ANALYSIS_ARCHITECTURE_2026.md` — local-first textual analysis architecture
- `v2/FRONTEND_ARCHITECTURE.md` — Next.js route/component/server ownership
- `v2/UI_SYSTEM.md` — Narrative Desk UI/UX/render-review rules
- `v2/ACCESS_AND_INVITATIONS.md` — closed-demo identity/account/admin contract
- `phases/PHASE_V2_3_LOCAL_FIRST_NARRATIVE_ANALYSIS.md` — active Phase-3 contract
- `phases/PHASE_V2_3_PRIMARY_EVALUATION_CORPUS.md` — active Phase-3 corpus-priority amendment
- `operations/VERCEL_DEPLOYMENT_POLICY.md` — manual-only Vercel deployment rule

## Active v2 Code

### Web application

- `../apps/web/` — active Next.js product
- `../apps/web/src/features/library/` — source upload interaction
- `../apps/web/src/features/characters/` — private identity evidence UI
- `../apps/web/src/server/story/` — owner-scoped project/source/job/result services
- `../apps/web/src/server/storage/` — provider-neutral object-storage boundary
- `../apps/web/src/server/supabase/` — ordinary SSR and isolated privileged Supabase boundaries
- `../apps/web/supabase/migrations/` — active v2 migration lineage
- `../apps/web/supabase/tests/` — disposable-Postgres contracts

### Analysis worker

- `../services/analysis-worker/` — active v2 durable analysis-worker/control-plane runtime
- `../services/analysis-worker/src/ingestion/` — deterministic TXT/EPUB normalization
- `../services/analysis-worker/src/identity/` — provider-neutral evidence + precision-first resolver
- `../services/analysis-worker/src/evaluation/` — benchmark/evaluation contracts
- `../services/analysis-worker/src/runtime/` — Supabase/B2/config boundaries
- `../services/analysis-worker/tests/` — deterministic ingestion/identity/evaluation fixtures

Phase 3 should extend these v2-owned surfaces or add a narrow v2 local-NLP sidecar. Do not add new v2 analysis behavior to historical pre-v2 runtime packages.

## Phase 2 Baseline Evidence

Validation records:

- `validation/PHASE_V2_2A_PRODUCT_DATA_FOUNDATION_2026-09-12.md`
- `validation/PHASE_V2_2B_SOURCE_INGESTION_2026-09-12.md`
- `validation/PHASE_V2_2C_CHARACTER_IDENTITY_2026-09-12.md`
- `validation/PHASE_V2_2D_LITBANK_ORACLE_BASELINE_2026-09-12.md`
- `validation/PHASE_V2_2D_REPOSITORY_QUALIFICATION_2026-09-12.md`
- `validation/PHASE_V2_3A_CURRENT_STATE_2026-09-12.md`

The 100-document LitBank oracle-evidence result remains a useful resolver-policy ceiling/reference, not a production-provider score and not product acceptance on modern fiction.

## Historical Full-Analysis Reference

The recovered graduation-project *Cruel Prince* run reported:

- 111,351 words;
- 35 chapters;
- 135 scenes;
- 53 characters;
- 55 locations;
- 24 key causal events;
- average tension 5.49/10;
- climax chapter 16.

These are reference/coverage observations only. They are not gold thresholds.

## Hosted Resource Reality

### Supabase

Dedicated project ref `scmeqnpmhomzcwecjdtu` in `eu-central-1`. All five repository-qualified Phase-2 migrations were applied and verified on 2026-09-12.

### Backblaze B2

Dedicated private bucket `saga-v2-faresmohamed260-1207062480` in `us-east-005`. Master credentials remain operator-only; runtime access must use scoped non-master application keys.

### Analysis runtime

The permanent text-analysis target is local-first. `ops/phase2-hosted-proof` is experimental historical evidence and must not be merged as the active text runtime. Modal remains image/media-only.

### Vercel

Dedicated project `saga`, root `apps/web`, with Git-triggered deployments disabled. Any Preview or Production deployment requires fresh explicit owner approval after stating reason, deployment type and exact SHA.

## Historical v1 References

Historical documents such as:

- `analysis_foundation_runtime.md`
- `canon_extraction_runtime.md`
- `character_world_modeling_runtime.md`

are evidence about prior quality, breadth, latency and failure modes, but their old LangGraph/provider/package topology is not active v2 architecture.

Important historical lesson: cloud-heavy full-book extraction repeatedly retransmitted overlapping context and provider latency dominated. Phase 3 replaces that pattern with deterministic narrowing, specialized local models and bounded reasoning.

The clean pre-v2 boundary is `b689e17bf2b70ea6c2ade0c3795bb85bb048d57b`.

## Documentation Maintenance

When v2 changes:

- current state/next action -> `PROJECT.md`
- cross-cutting decision -> `DECISIONS.md`
- phase scope/evidence -> `phases/` and `validation/`
- experiment protocols/results -> `experiments/`
- textual analysis architecture -> `v2/ANALYSIS_ARCHITECTURE_2026.md`
- broader web/data/storage/deployment boundary -> `v2/ARCHITECTURE.md`
- frontend/server ownership -> `v2/FRONTEND_ARCHITECTURE.md`
- UI rules -> `v2/UI_SYSTEM.md`
- account/auth rules -> `v2/ACCESS_AND_INVITATIONS.md`
