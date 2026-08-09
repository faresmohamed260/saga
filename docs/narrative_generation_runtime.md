# Narrative Generation Runtime

`packages/narrative_generation` is the first prose-generation slice in the rebuilt S.A.G.A. architecture.

It consumes persisted generation blueprints and produces durable generated story/chapter prose. Its semantic-support stage retrieves persisted source-book evidence through the active retrieval runtime. It does not depend on legacy code and uses only active runtime packages.

## Ownership

The runtime owns these artifact families:

- `narrative_scene_prose`
- `narrative_chapter_draft`
- `narrative_continuity_check`
- `narrative_revision`
- `narrative_support_audit`
- `narrative_support_decision`
- generated story records through `persistence.stories.upsert_story`
- `narrative_generation` validation reports

## Inputs

The runtime consumes:

- `GenerationBlueprintArtifact` from `packages/generation_planning`
- canon refs from the blueprint
- character refs from the blueprint
- entity refs from the blueprint
- optional canon/CWM context loaded through active stores
- reasoning runtime for bounded scene prose generation
- persistence runtime for records, story storage, reports, and checkpointing

## Graph

The LangGraph pipeline is:

1. `NarrativeGenerationAgent`
2. `ContinuityGuardAgent`
3. `RewriteRevisionAgent`

`NarrativeGenerationAgent` generates one prose artifact per planned scene.

`ContinuityGuardAgent` assembles scene prose into chapter drafts and checks coverage against the source blueprint.

`RewriteRevisionAgent` records and applies deterministic repairs for failed continuity checks, then persists the final generated story.

The independently callable semantic-support graph is:

1. `CanonEvidenceIndexAgent`
2. `SemanticSupportAgent`
3. `SupportRevisionAgent` when required
4. `SemanticSupportAgent` re-evaluation when required
5. `SupportDecisionAgent`

It keeps all primary source-scene chunks searchable, filters derived canon artifacts to blueprint-relevant refs, distinguishes supported canon from permissible creative expansion, and fails closed on provider failure or unresolved contradictions.

## Contracts

Primary contracts live in `packages/narrative_generation/contracts.py`:

- `SceneProseArtifact`
- `ChapterDraftArtifact`
- `ContinuityCheckArtifact`
- `RevisionRecordArtifact`
- `GeneratedStoryArtifact`
- `NarrativeGenerationResult`
- `SupportEvidenceArtifact`
- `ClaimSupportArtifact`
- `SceneSupportAuditArtifact`
- `NarrativeSupportDecisionArtifact`
- `NarrativeSupportResult`

## Quality Gates

`packages/narrative_generation/quality.py` validates:

- chapter completeness
- scene coverage
- canon reference validity
- character reference validity
- entity reference validity
- continuity pass rate
- prose substance

The quality gate passes only when generated prose covers the source blueprint and does not introduce invalid refs.

Semantic support uses severity-weighted claim metrics rather than raw claim counts:

- factual support rate
- unsupported invention rate
- contradiction rate
- live-provider success rate
- accepted/revised/rejected scene count

High-impact identity, history, relationship, state, power, and world-rule claims carry more weight than non-contradictory set dressing. Contradictions always require repair and unresolved failures reject the story. `require_narrative_semantic_acceptance(...)` is the fail-closed guard for visual, audiobook, and export workflows.

## Runtime Configuration

The service uses the active runtime env conventions:

- `SAGA_RUNTIME_DB_URL`
- `SAGA_RUNTIME_DB_MODE`
- `SAGA_RUNTIME_DB_PROVIDER`
- `SAGA_RUNTIME_LOCAL_STORAGE_ROOT`
- `SAGA_SUPABASE_URL`
- `SAGA_SUPABASE_ANON_KEY`
- `SAGA_SUPABASE_SERVICE_ROLE_KEY`
- `SAGA_NARRATIVE_GENERATION_REASONING_PROFILE`
- `SAGA_NARRATIVE_GENERATION_REASONING_MODE`
- `SAGA_NARRATIVE_GENERATION_REASONING_TIMEOUT_SECONDS`
- `SAGA_NARRATIVE_GENERATION_REASONING_MAX_RETRIES`
- `SAGA_NARRATIVE_GENERATION_REASONING_BASE_DELAY_SECONDS`
- `SAGA_NARRATIVE_GENERATION_SCENE_DELAY_SECONDS`
- `SAGA_NARRATIVE_SUPPORT_REASONING_PROFILE`
- `SAGA_NARRATIVE_SUPPORT_REASONING_MODE`
- `SAGA_NARRATIVE_SUPPORT_REASONING_TIMEOUT_SECONDS`
- `SAGA_NARRATIVE_SUPPORT_REASONING_MAX_RETRIES`
- `SAGA_NARRATIVE_SUPPORT_EMBEDDING_MODEL`
- `SAGA_NARRATIVE_SUPPORT_EMBEDDING_URL`
- `SAGA_NARRATIVE_SUPPORT_MIN_FACTUAL_SUPPORT_RATE`
- `SAGA_NARRATIVE_SUPPORT_MAX_UNSUPPORTED_RATE`

## CLI

Run against a persisted blueprint:

```powershell
python scripts\run_narrative_generation.py --series-id <series-id> --blueprint-id <blueprint-id> --story-id <story-id> --output-json tmp_live_narrative_generation\run.json
```

Audit a persisted generated story:

```powershell
python scripts\run_narrative_support.py --series-id <series-id> --story-id <story-id> --output-json tmp_live_narrative_generation\support.json
```

## Current Validation

Local runtime tests passed:

```powershell
python -m pytest tests\test_narrative_generation.py tests\test_generation_planning.py tests\test_reasoning_runtime.py -q
```

Real Supabase/Postgres validation passed through the local self-hosted Supabase pooler on `127.0.0.1:6543`, with `psycopg` prepared statements disabled for transaction-pooler compatibility.

Live Mistral validation:

- `real-holly-black-lost-sisters-v10`
- blueprint: `generation-blueprint-196ee89f9b922978`
- story: `narrative-lost-sisters-mistral-r3-backoff`
- output: `tmp_live_narrative_generation\lost_sisters_narrative_mistral_r3_backoff.json`
- report: `runtime-reports/providers/narrative-generation/reports/validation/43ac9fc004f2-real-holly-black-lost-sisters-v10-narrative-lost-sisters-mistral-r3-backoff-narrative-generation-report.json`
- result: 3 chapters, 6 scenes, 859 words, 80.7998s narrative stage, `fallback_scene_count=0`, `live_provider_success_rate=1.0`, quality gate passed

- `real-holly-black-queen-of-nothing-cwm-quality-v1`
- blueprint: `generation-blueprint-5d34092a85b94d0f`
- story: `narrative-qon-mistral-r3-backoff`
- output: `tmp_live_narrative_generation\queen_of_nothing_narrative_mistral_r3_backoff.json`
- report: `runtime-reports/providers/narrative-generation/reports/validation/06ccf6a8c1ed-real-holly-black-queen-of-nothing-cwm-quality-v1-narrative-qon-mistral-r3-backoff-narrative-generation-report.json`
- result: 4 chapters, 8 scenes, 1088 words, 118.1472s narrative stage, `fallback_scene_count=0`, `live_provider_success_rate=1.0`, quality gate passed

The Queen of Nothing validation initially exposed Mistral SDK 429 throttling. The fix lives in `packages/reasoning_runtime`: SDK-style rate-limit exceptions now use the same exponential backoff path as HTTP 429s, and narrative quality gates reject deterministic provider fallback.

Live semantic-support validation:

- Lost Sisters: 6/6 scenes accepted, factual support `1.0`, unsupported invention `0.0`, contradictions `0.0`, provider success `1.0`; cached evidence indexing `0.2982s`; output `tmp_live_narrative_generation\lost_sisters_semantic_support_r4.json`
- Queen of Nothing: 8/8 scenes accepted after two targeted repairs, factual support `0.99`, unsupported invention `0.01`, contradictions `0.0`, provider success `1.0`; first 433-document evidence index `22.9773s`; output `tmp_live_narrative_generation\queen_of_nothing_semantic_support_r1.json`
- Reports: `runtime-reports/providers/narrative-support/reports/validation/8abd61447809-real-holly-black-lost-sisters-v10-narrative-lost-sisters-mistral-r3-backoff-lost-sisters-semantic-support-r4-narrative-support-report.json` and `runtime-reports/providers/narrative-support/reports/validation/721db6c5441e-real-holly-black-queen-of-nothing-cwm-quality-v1-narrative-qon-mistral-r3-backoff-queen-of-nothing-semantic-support-r1-narrative-support-report.json`

## Remaining Hardening

The narrative slice and semantic-support gate are structurally decoupled and live-validated. Remaining hardening opportunities are:

- tune prompt/context size for target latency
- batch or parallelize provider-safe scene audits to reduce evaluation latency
- add calibrated human-labeled claim-support benchmarks across more genres
- add an optional dedicated NLI verifier for high-impact claims
