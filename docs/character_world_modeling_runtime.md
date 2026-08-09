# Character World Modeling Runtime

This runtime is Group 3 of the rebuilt analysis architecture. It consumes persisted Group 1 and Group 2 outputs and writes three durable artifact families:

- `character_profile`
- `stable_character_state`
- `world_state`

## Inputs

- persisted books, chapters, scenes
- persisted canonical identity bundle
- persisted events, entities, relationships, timeline

## Outputs

- `character_profile`: durable character profile synthesis for each canonical character
- `stable_character_state`: stable canonical facts for each canonical character
- `world_state`: grounded world-state summary for each persisted non-character entity

All records are written through `packages/persistence_runtime` into `library_records`. Reruns replace prior records for the same `series_id`.

## Environment

- `SAGA_RUNTIME_DB_MODE`
- `SAGA_RUNTIME_DB_PROVIDER`
- `SAGA_RUNTIME_DB_URL`
- `SAGA_RUNTIME_LOCAL_STORAGE_ROOT`
- `SAGA_SUPABASE_URL` or `SAGA_SUPABASE_API_URL`
- `SAGA_SUPABASE_ANON_KEY`
- `SAGA_SUPABASE_SERVICE_ROLE_KEY`
- `SAGA_CHARACTER_WORLD_MODELING_PERSISTENCE_PROFILE`
- `SAGA_CHARACTER_WORLD_MODELING_REASONING_PROFILE`
- `SAGA_CHARACTER_WORLD_MODELING_REASONING_MODE`
- `SAGA_CHARACTER_WORLD_MODELING_REASONING_TIMEOUT_SECONDS`
- `SAGA_CHARACTER_WORLD_MODELING_REASONING_MAX_RETRIES`
- `SAGA_CWM_CHARACTER_BATCH_SIZE`
- `SAGA_CWM_ENTITY_BATCH_SIZE`
- `SAGA_CWM_PARALLELISM`
- `SAGA_CWM_RESUME_STAGES`

## Entrypoints

- runtime: `packages.character_world_modeling.CharacterWorldModelingRuntime`
- service: `packages.character_world_modeling.CharacterWorldModelingService`
- LangGraph export: `packages.agent_runtime.character_world_modeling`
- script: `python scripts/run_character_world_modeling.py <series_id> [thread_id]`

## Notes

- The runtime is LangGraph-native.
- It uses only package runtime surfaces.
- It does not depend on legacy dashboard, sqlite-specific code, or old adapters.
- The world-state slice is intentionally non-character-only because character durability is owned by `character_profile` plus `stable_character_state`.
- World-state synthesis supports bounded parallel batches, incremental persistence, and persisted-stage resume.
- Profile and stable-state stages support persisted-stage resume and conservative terminal fallback on exhausted provider leaf batches.

## Quality Hardening: July 22, 2026

The CWM runtime now has deterministic post-synthesis quality gates for profile grounding, stable attributes, notable relationships, entity deduplication/usefulness, and world fact support. These gates live in the active runtime packages, not in legacy glue.

### Fixed Owners

- `packages.character_world_modeling.pipeline`: rejects ungrounded first/latest summaries, contextual-object actor/speaker matches, non-relationship action claims, character-to-entity `artifact_usage` profile relationships, unsupported stable attributes, unsupported world facts, generic world facts, aliases-as-facts, and unsupported active conditions.
- `packages.character_world_modeling.quality`: reusable metrics for profile grounding, unsupported profile claims, stable attribute precision, relationship support, entity deduplication, entity usefulness, and unsupported world facts.
- `packages.canon_extraction.pipeline`: sibling relationships now use the same direct pair-support guard as family relationships, preventing false edges such as "Nicasia sibling Taryn" when the text only says Taryn should renounce her own sister.
- `packages.canon_extraction.store`: entity-name normalization strips leading articles so `Folk` and `the Folk` dedupe.

### Required Metrics

- `profile_grounding_rate`
- `unsupported_profile_claim_rate`
- `stable_attribute_precision`
- `relationship_support_rate`
- `entity_deduplication_rate`
- `useful_entity_rate`
- `unsupported_world_fact_rate`

### Lost Sisters Validation

Baseline CWM report:
`analysis_outputs/unified_storage/runtime-reports/providers/character-world-modeling/reports/validation/b61b53b2534b-real-holly-black-lost-sisters-v10-narrative-grounding-cwm-v10-r19-character-world-modeling-report.json`

Baseline metrics:

- `profile_grounding_rate`: `1.0`
- `unsupported_profile_claim_rate`: `0.1412`
- `stable_attribute_precision`: `1.0`
- `relationship_support_rate`: `0.9`
- `entity_deduplication_rate`: `0.9911`
- `useful_entity_rate`: `1.0`
- `unsupported_world_fact_rate`: `0.2917`

Final validated reports:

- Analysis foundation: `analysis_outputs/unified_storage/runtime-reports/providers/analysis-foundation/reports/validation/9c59386d44a1-real-holly-black-lost-sisters-v10-cwm-quality-af-v10-r20-analysis-foundation-report.json`
- Canon extraction: `analysis_outputs/unified_storage/runtime-reports/providers/canon-extraction/reports/validation/7fb051913377-real-holly-black-lost-sisters-v10-cwm-quality-canon-v10-r23-canon-extraction-report.json`
- CWM: `analysis_outputs/unified_storage/runtime-reports/providers/character-world-modeling/reports/validation/8a0424ad32ec-real-holly-black-lost-sisters-v10-cwm-quality-cwm-v10-r30-character-world-modeling-report.json`
- Attribution regression: `tmp_live_canon_extraction_pg/lost_sisters_v10_attribution_eval_r23.json`

Final CWM metrics:

- `profile_grounding_rate`: `1.0`
- `unsupported_profile_claim_rate`: `0.0`
- `stable_attribute_precision`: `1.0`
- `relationship_support_rate`: `1.0`
- `entity_deduplication_rate`: `1.0`
- `useful_entity_rate`: `1.0`
- `unsupported_world_fact_rate`: `0.0`

Provider proof:

- Analysis identity provider: `modal_xcore_litbank`
- Reasoning model for CWM profile/stable/world stages: `gpt-oss:120b-cloud`

Timings:

- Analysis foundation r20: `40.1824s`
- Canon extraction r23: `462.0376s`
- CWM r30: profile `48.5082s`, stable state `24.6824s`, world state `150.2743s`

Narrator-attribution regression:

- `participant_precision`: `1.0`
- `participant_recall`: `1.0`
- `attribution_f1`: `1.0`
- `narrator_attribution_accuracy`: `1.0`
- `unsupported_ref_rate`: `0.0`
- `contamination_rate`: `0.0`

### Second Real-Book Validation

Full `The Queen of Nothing.epub` analysis foundation completed, but full-book canon extraction exceeded the bounded 20-minute validation timeout and was stopped. To complete the required second-book end-to-end validation without allowing an uncontrolled long run, a temporary real excerpt was extracted from the same EPUB:

`tmp_live_canon_extraction_pg/queen_of_nothing_real_excerpt.txt`

Excerpt source:
`D:/Books/Ebooks/Holly Black/The Queen of Nothing/The Queen of Nothing.epub`

Excerpt size:

- `3` substantial chapters
- `7,627` words

Final validated reports:

- Analysis foundation: `analysis_outputs/unified_storage/runtime-reports/providers/analysis-foundation/reports/validation/9c6300500ba4-real-holly-black-queen-of-nothing-excerpt-cwm-quality-v1-cwm-quality-af-qon-excerpt-v1-analysis-foundation-report.json`
- Canon extraction: `analysis_outputs/unified_storage/runtime-reports/providers/canon-extraction/reports/validation/d2972bffb1f9-real-holly-black-queen-of-nothing-excerpt-cwm-quality-v1-cwm-quality-canon-qon-excerpt-v1-canon-extraction-report.json`
- CWM: `analysis_outputs/unified_storage/runtime-reports/providers/character-world-modeling/reports/validation/5d0f81b856a4-real-holly-black-queen-of-nothing-excerpt-cwm-quality-v1-cwm-quality-cwm-qon-excerpt-v1-character-world-modeling-report.json`

Second-book CWM metrics:

- `profile_grounding_rate`: `1.0`
- `unsupported_profile_claim_rate`: `0.0`
- `stable_attribute_precision`: `1.0`
- `relationship_support_rate`: `1.0`
- `entity_deduplication_rate`: `1.0`
- `useful_entity_rate`: `1.0`
- `unsupported_world_fact_rate`: `0.0`

Second-book timings:

- Analysis foundation: `37.3622s`
- Canon extraction: `292.5394s`
- CWM: profile `94.1982s`, stable state `39.0315s`, world state `192.9404s`

Provider proof:

- Analysis identity provider: `modal_xcore_litbank`
- Identity model: `sapienzanlp/xcore-litbank`
- Reasoning model for CWM profile/stable/world stages: `gpt-oss:120b-cloud`

### Remaining Risks

- Full-novel canon extraction latency needs separate scalability work. The Queen of Nothing full-book canon pass exceeded a 20-minute bound.
- The second-book excerpt exposed upstream identity-quality noise such as vocative or non-character clusters. CWM now keeps those grounded/conservative, but the correct long-term owner is the identity runtime, not CWM.

## Scalability Hardening: July 23, 2026

Queen of Nothing downstream CWM over optimized full-novel canon now passes quality after CWM resumability and world-state scalability hardening.

Validated report:

`analysis_outputs/unified_storage/runtime-reports/providers/character-world-modeling/reports/validation/2da27289f547-real-holly-black-queen-of-nothing-cwm-quality-v1-cwm-after-canon-scalability-qon-r11-character-world-modeling-report.json`

Latest validation over the cold durable-job canon output:

`analysis_outputs/unified_storage/runtime-reports/providers/character-world-modeling/reports/validation/b582d79af99a-real-holly-black-queen-of-nothing-cwm-quality-v1-cwm-after-canon-scalability-qon-r12-cold-job-durable-character-world-modeling-report.json`

Counts:

- `character_profile_count`: `173`
- `stable_character_state_count`: `173`
- `world_state_count`: `945` on the latest r12 validation

Quality metrics:

- `profile_grounding_rate`: `1.0`
- `unsupported_profile_claim_rate`: `0.0`
- `stable_attribute_precision`: `1.0`
- `relationship_support_rate`: `1.0`
- `entity_deduplication_rate`: `1.0`
- `useful_entity_rate`: `1.0`
- `unsupported_world_fact_rate`: `0.0`

Run shape:

- `character_profile_synthesis`: regenerated, `32` reasoning calls, `376.1923s`
- `stable_state_synthesis`: regenerated, `29` reasoning calls, `138.2764s`
- `world_state_synthesis`: parallel/incremental, `54` reasoning calls, `200.348s`

Important limitation:

- This proves downstream CWM can pass quality over the latest full Queen of Nothing canon output.
- Provider latency remains the dominant limit for profile and stable-state stages, which are still serial.
