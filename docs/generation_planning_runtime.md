# Generation Planning Runtime

`packages/generation_planning` is the first story-generation slice in the rebuilt architecture.

It is a portable, LangGraph-native runtime that turns persisted canon memory into reusable generation blueprints. It does not read raw book text and does not depend on legacy/dashboard code.

## Ownership

The runtime owns these artifact families:

- `generation_story_intent`
- `generation_canon_grounding`
- `generation_blueprint`
- `generation_planning` validation reports

The runtime consumes active upstream artifacts only:

- analysis foundation: books and canonical identity bundle
- canon extraction: events, entities, relationships, timeline
- character/world modeling: character profiles, stable states, world states
- reasoning runtime: bounded blueprint synthesis
- persistence runtime: durable records, reports, checkpoint storage

## Graph

The LangGraph pipeline is:

1. `StoryIntentAgent`
2. `CanonGroundingAgent`
3. `BlueprintSynthesisAgent`

`StoryIntentAgent` normalizes the requested premise, audience, tone, continuation mode, and chapter count.

`CanonGroundingAgent` builds a bounded context from canon/CWM artifacts. It intentionally keeps context small enough for reliable structured inference.

`BlueprintSynthesisAgent` asks the configured reasoning provider for a JSON blueprint, validates contract shape, sanitizes references against persisted canon IDs, repairs completeness gaps, and persists the final artifact.

## Contracts

Primary contracts live in `packages/generation_planning/contracts.py`:

- `StoryIntentArtifact`
- `CanonGroundingArtifact`
- `ChapterOutlineItem`
- `ScenePlanItem`
- `GenerationBlueprintArtifact`
- `GenerationPlanningResult`

Blueprints include:

- story title and premise
- continuation and divergence plan
- chapter outline
- scene plan
- visual requirements
- audio requirements
- canon, character, and entity references

## Quality Gates

`packages/generation_planning/quality.py` validates:

- canon reference validity
- character reference validity
- entity reference validity
- chapter outline completeness
- scene plan completeness
- scene visual requirement coverage
- scene audio requirement coverage

The quality gate passes only when references are valid and coverage is complete.

## Runtime Configuration

The service uses the active runtime env conventions:

- `SAGA_RUNTIME_DB_URL`
- `SAGA_RUNTIME_DB_MODE`
- `SAGA_RUNTIME_DB_PROVIDER`
- `SAGA_RUNTIME_LOCAL_STORAGE_ROOT`
- `SAGA_SUPABASE_URL`
- `SAGA_SUPABASE_ANON_KEY`
- `SAGA_SUPABASE_SERVICE_ROLE_KEY`
- `SAGA_GENERATION_PLANNING_REASONING_PROFILE`
- `SAGA_GENERATION_PLANNING_REASONING_MODE`
- `SAGA_GENERATION_PLANNING_REASONING_TIMEOUT_SECONDS`
- `SAGA_GENERATION_PLANNING_REASONING_MAX_RETRIES`

## CLI

Run against persisted canon/CWM data:

```powershell
python scripts\run_generation_planning.py --series-id <series-id> --premise "<premise>" --desired-chapter-count 3 --output-json tmp_live_generation_planning\run.json
```

## Real Validation

Lost Sisters final validation:

- output: `tmp_live_generation_planning/lost_sisters_generation_planning_mistral_r3_tight.json`
- report: `analysis_outputs/unified_storage/runtime-reports/providers/generation-planning/reports/validation/5afecf1e23c7-real-holly-black-lost-sisters-v10-generation-planning-lost-sisters-mistral-r3-tight-generation-planning-report.json`
- provider: Mistral `mistral-large-2512`
- fallback: false
- blueprint synthesis: 41.2119 seconds
- quality gate: pass

Queen of Nothing final validation:

- output: `tmp_live_generation_planning/queen_of_nothing_generation_planning_mistral_r2_tight.json`
- report: `analysis_outputs/unified_storage/runtime-reports/providers/generation-planning/reports/validation/42da8fed45c6-real-holly-black-queen-of-nothing-cwm-quality-v1-generation-planning-qon-mistral-r2-tight-generation-planning-report.json`
- provider: Mistral `mistral-large-2512`
- fallback: false
- blueprint synthesis: 48.1034 seconds
- quality gate: pass

Regression tests:

```powershell
python -m pytest tests\test_generation_planning.py tests\test_reasoning_runtime.py tests\test_character_world_modeling.py -q
```

Result: `32 passed`.

## Remaining Hardening

The runtime is structurally decoupled and functional, but planner latency is still high for production UX. The next hardening pass should add retrieval-ranked grounding selection so the planner gets the most premise-relevant canon/CWM slices instead of a fixed recent/top-supported window.
