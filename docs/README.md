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

Authoritative contract and amendment:

- `phases/PHASE_V2_3_LOCAL_FIRST_NARRATIVE_ANALYSIS.md`
- `phases/PHASE_V2_3_PRIMARY_EVALUATION_CORPUS.md`

Authoritative analysis architecture and current state:

- `v2/ANALYSIS_ARCHITECTURE_2026.md`
- `validation/PHASE_V2_3A_CURRENT_STATE_2026-09-12.md`

## Latest Phase 3A Progress

Merged work includes:

- benchmark-before-adoption experiment governance;
- BookNLP-small primary-identity evaluation and rejection for that role;
- GLiNER/F-Coref component smoke evidence;
- provider-neutral whole-book benchmark infrastructure;
- the owner-directed private primary fiction suite;
- restored real-book identity regressions for Harry Potter, The Cruel Prince, Caraval and ACOFAS;
- the first provider-neutral scene-segmentation benchmark foundation.

Important merged checkpoints:

- PR #191 / merge `88133be6a7d20cfe02fba26f06e0dd636001fbd0` — whole-book benchmark foundation + primary private fiction corpus;
- PR #192 / merge `d6c1a144d0c4b4ad82e7229c583cb22682249f07` — primary-fiction identity regression evaluator;
- PR #193 / merge `201af2638b4df22aa2734b0cac934fa12b8e3e5e` — historical narrative breadth reference + scene annotation/evaluation + structural/lexical scene baselines.

### Scene benchmark foundation now on `main`

The merged scene slice contains:

- `experiments/2026-09-12_CRUEL_PRINCE_HISTORICAL_ANALYSIS_BASELINE.md`;
- `experiments/SCENE_SEGMENTATION_BENCHMARK.md`;
- scene annotation workspace/CLI;
- exact + relaxed scene-boundary evaluator/CLI;
- deterministic structural scene baseline/CLI;
- lexical scene-change baseline/CLI;
- deterministic tests for the scene benchmark stack.

Pre-merge review hardened benchmark integrity in two places:

- tolerant one-to-one boundary matching now deterministically maximizes the number of valid matches before minimizing paragraph error rather than using a greedy distance-first assignment;
- selected annotation workspaces cannot be finalized while any selected section remains pending.

PR #193 exact head `a3fc13dc81c6fe8f30c218c84e6a81943b7ebfb7` passed Analysis Worker CI, LitBank Oracle Baseline, Backend Architecture CI and Required Check Compatibility before merge.

**No scene method has been adopted yet.** Primary-suite manual annotations and direct candidate measurements are still required.

## Locked Analysis Direction

Owner decisions D-026 through D-030 require:

- textual analysis that works without paid AI APIs/subscriptions;
- Modal reserved for image/media generation, not book NLP/reasoning;
- deterministic/classical/local methods before generative inference;
- whole-book resource accounting as part of provider selection;
- an outbound-only local analysis worker using the existing Supabase durable queue and B2 storage boundaries;
- model/provider output treated as evidence, while deterministic S.A.G.A. policy owns canonical product truth.

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

A 2026-09-12 recheck found historical File Library notes/scripts that reference the books, but not the actual EPUB binaries. Remote Desktop Commander also returned no connected devices. This remains a source-availability blocker for real primary-suite scene annotations/runs, not a reason to substitute public-domain books as the product gate.

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
- `../services/analysis-worker/src/evaluation/` — benchmark/evaluation contracts, including merged scene tooling
- `../services/analysis-worker/tests/` — deterministic ingestion/identity/evaluation fixtures

Phase 3 should extend these v2-owned surfaces or add a narrow v2 local-NLP sidecar. Do not add new v2 analysis behavior to historical pre-v2 runtime packages.

## Phase 2 / 3 Validation Records

- `validation/PHASE_V2_2A_PRODUCT_DATA_FOUNDATION_2026-09-12.md`
- `validation/PHASE_V2_2B_SOURCE_INGESTION_2026-09-12.md`
- `validation/PHASE_V2_2C_CHARACTER_IDENTITY_2026-09-12.md`
- `validation/PHASE_V2_2D_LITBANK_ORACLE_BASELINE_2026-09-12.md`
- `validation/PHASE_V2_2D_REPOSITORY_QUALIFICATION_2026-09-12.md`
- `validation/PHASE_V2_3A_CURRENT_STATE_2026-09-12.md`

The 100-document LitBank oracle-evidence result remains a useful resolver-policy ceiling/reference, not a production-provider score and not product acceptance on modern fiction.

## Historical Full-Analysis Reference

The recovered graduation-project *Cruel Prince* run reported 111,351 words, 35 chapters, 135 scenes, 53 characters, 55 locations, 24 key causal events, average tension 5.49/10 and climax chapter 16. These are reference/coverage observations only, not gold thresholds.

## Hosted Resource Reality

### Supabase

Dedicated project ref `scmeqnpmhomzcwecjdtu` in `eu-central-1`. All five repository-qualified Phase-2 migrations were applied and verified on 2026-09-12.

### Backblaze B2

Dedicated private bucket `saga-v2-faresmohamed260-1207062480` in `us-east-005`. Master credentials remain operator-only; runtime access must use scoped non-master application keys.

### Analysis runtime

The permanent text-analysis target is local-first. `ops/phase2-hosted-proof` is experimental historical evidence and must not be merged as the active text runtime. Modal remains image/media-only.

### Vercel

Dedicated project `saga`, root `apps/web`, with Git-triggered deployments disabled. Any Preview or Production deployment requires fresh explicit owner approval after stating reason, deployment type and exact SHA.

## Immediate Continuation

1. Verify live repository state before each new slice.
2. When lawful primary EPUB access returns, create scene annotation workspaces for Harry Potter, The Cruel Prince, Caraval and ACOFAS first.
3. Annotate representative chapters across dialogue, action, travel, explicit/subtle temporal changes, flashbacks, focal changes, decorative breaks and long continuous scenes.
4. Compare the merged structural and lexical baselines first using exact + relaxed metrics and resource measurements.
5. Test stronger local scene candidates only if cheaper tiers leave a measurable gap; adopt nothing before primary-suite evidence.
6. After a measured scene baseline exists, proceed to dialogue/speaker, event/participant, location/entity, tension, relationships/state, timeline and causality experiments.
7. Keep adoption/rejection records and negative experiments durable in the repository.

## Historical v1 References

Historical documents such as `analysis_foundation_runtime.md`, `canon_extraction_runtime.md`, and `character_world_modeling_runtime.md` remain evidence about prior quality, breadth, latency and failure modes, but their old LangGraph/provider/package topology is not active v2 architecture.

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
