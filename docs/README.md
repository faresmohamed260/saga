# S.A.G.A. Documentation Index

S.A.G.A. is in an owner-authorized v2 rebuild. This index separates the **active v2 source of truth** from retained **v1 historical/reference material**.

## Read First

For substantial current work, read in this order:

1. `../AGENTS.md`
2. `../PROJECT.md`
3. `DECISIONS.md`
4. the active phase contract referenced by `PROJECT.md`
5. any active owner-directed phase amendment
6. the relevant `v2/` architecture/runtime contract
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

Authoritative analysis architecture/runtime and current state:

- `v2/ANALYSIS_ARCHITECTURE_2026.md`
- `v2/LOCAL_LITERARY_PROVIDER_PROTOCOL.md`
- `validation/PHASE_V2_3A_CURRENT_STATE_2026-09-12.md`

## Latest Phase 3 Progress

Merged work includes:

- benchmark-before-adoption experiment governance;
- BookNLP-small primary-identity evaluation and rejection for that role;
- GLiNER/F-Coref component smoke evidence;
- provider-neutral whole-book benchmark infrastructure;
- the private modern-fiction qualification suite;
- restored real-book identity regressions for Harry Potter, The Cruel Prince, Caraval and ACOFAS;
- provider-neutral scene benchmark infrastructure with structural/lexical candidate floors;
- provider-neutral dialogue/speaker benchmark infrastructure with a conservative deterministic candidate floor;
- provider-neutral event-trigger/participant benchmark infrastructure with a dependency-free lexical floor;
- a generic local literary-NLP subprocess execution/validation boundary for real local provider experiments.

Important merged checkpoints:

- PR #191 / merge `88133be6a7d20cfe02fba26f06e0dd636001fbd0` — whole-book benchmark foundation + primary private fiction corpus;
- PR #192 / merge `d6c1a144d0c4b4ad82e7229c583cb22682249f07` — primary-fiction identity regression evaluator;
- PR #193 / merge `201af2638b4df22aa2734b0cac934fa12b8e3e5e` — narrative breadth reference + scene benchmark foundation;
- PR #195 / merge `bb44b169ef00a4f76b84410e655eed7244ac2a3a` — scene source-of-truth synchronization;
- PR #201 / merge `d029e465bc37d738debd1ebc8d5d831ab9249661` — dialogue/speaker benchmark foundation;
- PR #202 / merge `a5634d425e7e95ddac958e623e8c7893f3e67c74` — dialogue source-of-truth synchronization;
- PR #204 / merge `0b638058f355c9e0610b7d13b9364948e4aa003f` — event candidate/participant benchmark foundation;
- PR #205 / merge `64501585f041e5e025fdf04c813ed6f7ec579c36` — event source-of-truth synchronization;
- PR #207 / merge `c1dfa9f9e57545a7a3565b21e779f2514abacd04` — local literary-NLP subprocess execution/validation boundary.

PR #207 exact head `551f22dd318740695a3e1922e56d79fcdcf09ecf` passed Required Check Compatibility, SAGA v2 Analysis Worker CI and Backend Architecture CI. No LitBank workflow was required/run for that path-triggered runtime-boundary PR.

## Benchmark Foundations

### Scene

`experiments/SCENE_SEGMENTATION_BENCHMARK.md` plus the merged scene code provide local annotation, exact and relaxed `±1 paragraph` evaluation, optimal one-to-one tolerant matching, and deterministic structural/lexical floors. Pre-merge review fixed greedy tolerant matching and partial-workspace finalization.

**No scene method is adopted.** Primary-suite annotations remain required.

### Dialogue / speaker

`experiments/DIALOGUE_SPEAKER_BENCHMARK.md` plus the merged dialogue code provide exact quote-span evaluation, known/unknown/ambiguous speaker semantics, contamination/unresolved metrics, and a conservative speech-verb + already-resolved-character floor.

**No speaker method is adopted.** Dependency-aware and BookNLP quote/speaker challengers remain open.

### Events / participants

`experiments/EVENT_CANDIDATE_BENCHMARK.md` plus the merged event code provide exact trigger/participant evaluation, duplicate/unsupported diagnostics and a dependency-free lexical floor with bounded character attachment.

**No event method is adopted.** POS/dependency-aware extraction, BookNLP event evidence, non-character participants, realis/modality and combined candidate stabilization remain open.

## Phase 3B Local Provider Boundary

`v2/LOCAL_LITERARY_PROVIDER_PROTOCOL.md` is the active execution-boundary contract introduced by PR #207.

The merged boundary provides:

- generic `LocalLiteraryEvidenceProvider` ownership behind the TypeScript worker/evaluation stack;
- versioned stdin/stdout JSON `health` / `analyze` / structured-error protocol;
- no-shell process launch;
- bounded input/output/error/time resources;
- explicit retryability classification;
- exact provider/configuration/input fingerprints;
- exact Unicode source-span and structural-locator validation across identity/entity/quote/event evidence;
- duplicate-ID and malformed/partial-payload rejection;
- sanitized child environment so ambient worker secrets are not inherited;
- model-light fixture CI only.

Subprocess is an **experimental execution baseline**, not a permanent transport decision. Persistent loopback HTTP remains allowed and should be compared only after a real provider supplies meaningful startup/runtime measurements.

## Locked Analysis Direction

Owner decisions D-026 through D-030 require:

- textual analysis that works without paid AI APIs/subscriptions;
- Modal reserved for image/media generation, not book NLP/reasoning;
- deterministic/classical/local methods before generative inference;
- whole-book resource accounting as part of provider selection;
- an outbound-only local analysis worker using the existing Supabase durable queue and B2 storage boundaries;
- provider output treated as evidence while deterministic S.A.G.A. policy owns canonical product truth.

The governing cascade is:

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

A 2026-09-12 recheck found historical File Library notes/scripts referencing the books but not the EPUB binaries. Remote Desktop Commander also returned no connected devices. This remains a source-availability blocker for primary-suite runs, not a reason to substitute public-domain books as the product gate.

## Active v2 Architecture / Product Contracts

- `../AGENTS.md` — mandatory working rules/source-of-truth order
- `../PROJECT.md` — current handoff and immediate execution order
- `DECISIONS.md` — durable cross-cutting decisions
- `v2/ARCHITECTURE.md` — web/data/storage/deployment ownership
- `v2/ANALYSIS_ARCHITECTURE_2026.md` — local-first textual analysis architecture
- `v2/LOCAL_LITERARY_PROVIDER_PROTOCOL.md` — local literary-NLP execution/validation boundary
- `v2/FRONTEND_ARCHITECTURE.md` — Next.js route/component/server ownership
- `v2/UI_SYSTEM.md` — Narrative Desk UI/UX/render-review rules
- `v2/ACCESS_AND_INVITATIONS.md` — closed-demo identity/account/admin contract
- `phases/PHASE_V2_3_LOCAL_FIRST_NARRATIVE_ANALYSIS.md` — active Phase-3 contract
- `phases/PHASE_V2_3_PRIMARY_EVALUATION_CORPUS.md` — active corpus-priority amendment
- `operations/VERCEL_DEPLOYMENT_POLICY.md` — manual-only Vercel deployment rule

## Active v2 Code

### Web application

- `../apps/web/` — active Next.js product
- `../apps/web/src/features/library/` — source upload interaction
- `../apps/web/src/features/characters/` — private identity evidence UI
- `../apps/web/src/server/story/` — owner-scoped project/source/job/result services
- `../apps/web/src/server/storage/` — provider-neutral object-storage boundary
- `../apps/web/src/server/supabase/` — SSR and isolated privileged Supabase boundaries
- `../apps/web/supabase/migrations/` — active v2 migration lineage
- `../apps/web/supabase/tests/` — disposable-Postgres contracts

### Analysis worker

- `../services/analysis-worker/` — active v2 durable analysis worker/control plane
- `../services/analysis-worker/src/ingestion/` — deterministic TXT/EPUB normalization
- `../services/analysis-worker/src/identity/` — provider-neutral evidence + precision-first resolver
- `../services/analysis-worker/src/local-analysis/` — generic local literary evidence types, BookNLP normalization, strict evidence validation and subprocess boundary
- `../services/analysis-worker/src/evaluation/` — identity/whole-book/scene/dialogue/event benchmark contracts
- `../services/analysis-worker/tests/` — deterministic/model-light fixtures and regressions

Do not add new v2 analysis behavior to historical pre-v2 runtime packages.

## Validation Records

- `validation/PHASE_V2_2A_PRODUCT_DATA_FOUNDATION_2026-09-12.md`
- `validation/PHASE_V2_2B_SOURCE_INGESTION_2026-09-12.md`
- `validation/PHASE_V2_2C_CHARACTER_IDENTITY_2026-09-12.md`
- `validation/PHASE_V2_2D_LITBANK_ORACLE_BASELINE_2026-09-12.md`
- `validation/PHASE_V2_2D_REPOSITORY_QUALIFICATION_2026-09-12.md`
- `validation/PHASE_V2_3A_CURRENT_STATE_2026-09-12.md`

The 100-document LitBank oracle-evidence result remains a useful resolver-policy ceiling/reference, not product acceptance on modern fiction.

## Hosted Resource Reality

- **Supabase:** dedicated project `scmeqnpmhomzcwecjdtu` in `eu-central-1`; all five repository-qualified Phase-2 migrations applied/verified 2026-09-12.
- **Backblaze B2:** private bucket `saga-v2-faresmohamed260-1207062480` in `us-east-005`; runtime access must use scoped non-master credentials.
- **Analysis runtime:** permanent text path is local-first. `ops/phase2-hosted-proof` is historical experimental evidence only; Modal remains image/media-only.
- **Vercel:** dedicated project `saga`, root `apps/web`, with Git-triggered deployments disabled. Preview/Production deployment requires fresh explicit owner approval for reason, deployment type and exact SHA.

## Immediate Continuation

1. Verify live repository state before each new slice.
2. Use the merged local provider boundary to instantiate a real local literary-NLP challenger without putting heavyweight model downloads in normal CI.
3. Reuse the existing BookNLP output normalization for BookNLP quote/speaker/event evidence rather than inventing a duplicate evidence schema.
4. Keep provider executable/model/revision/license/configuration and runtime/resource measurements explicit.
5. Do not wire an experimental provider into durable application jobs or call it production-qualified before benchmark evidence justifies it.
6. When lawful primary EPUB access returns, create scene/dialogue/event annotation workspaces for Harry Potter, The Cruel Prince, Caraval and ACOFAS and score the merged baselines/challengers.
7. Test stronger local candidates only if cheaper tiers leave a measurable gap; preserve negative results.

## Historical v1 References

Historical documents such as `analysis_foundation_runtime.md`, `canon_extraction_runtime.md`, and `character_world_modeling_runtime.md` remain evidence about prior quality, breadth, latency and failure modes, but their old provider/agent topology is not active v2 architecture.

The clean pre-v2 boundary is `b689e17bf2b70ea6c2ade0c3795bb85bb048d57b`.

## Documentation Maintenance

When v2 changes:

- current state/next action -> `PROJECT.md`
- cross-cutting decision -> `DECISIONS.md`
- phase scope/evidence -> `phases/` and `validation/`
- experiment protocols/results -> `experiments/`
- textual analysis architecture -> `v2/ANALYSIS_ARCHITECTURE_2026.md`
- local provider execution protocol -> `v2/LOCAL_LITERARY_PROVIDER_PROTOCOL.md`
- broader web/data/storage/deployment boundary -> `v2/ARCHITECTURE.md`
- frontend/server ownership -> `v2/FRONTEND_ARCHITECTURE.md`
- UI rules -> `v2/UI_SYSTEM.md`
- account/auth rules -> `v2/ACCESS_AND_INVITATIONS.md`
