# S.A.G.A. JSON Contract

The production contract is the stable artifact bundle written by the encoder path and reused for validation, retrieval, dashboard inspection, and later generation support.

Main builder path:

- [core/pipeline_contract.py](/B:/Documents/PyCharm/graduationProject/core/pipeline_contract.py)
- [services/encoder_persistence_service.py](/B:/Documents/PyCharm/graduationProject/services/encoder_persistence_service.py)

## Top-Level Shape

Typical contract shape:

```json
{
  "contract_version": "1.0.0",
  "generated_at_utc": "2026-06-12T12:00:00+00:00",
  "app": {},
  "configuration": {},
  "inputs": {},
  "outputs": {},
  "runtime": {}
}
```

## Key Sections

## `configuration`

Important configuration fields may include:

- `analysis_model`
- `identity_model`
- `identity_provider`
- `analysis_provider_mode`
- `scene_failure_policy`
- `target_scene_words`

## `inputs`

Typical input fields:

- `books`
- `series_id`
- `series_title`

## `outputs`

Main production output families:

- `chapters`
- `scene_analyses`
- `resolved_scene_analyses`
- `entity_registry`
- `state_result`
- `canon_snapshot`
- `timeline`
- `event_ledger`
- `character_timelines`
- `character_profiles`
- `relationship_profiles`
- `stable_character_states`
- `identity_result`
- `story_index_summary`
- `causal_graph_result`
- `visual_prompt_sets`

Depending on the run and rebuild path, additional provider-oriented identity payloads may also appear, such as:

- `pipeline_identity`

## `runtime`

Typical runtime metadata may include:

- elapsed timing
- processed scene counts
- provider/model metadata
- run status
- scene quality diagnostics

## Scene Analysis Payloads

`scene_analyses` and `resolved_scene_analyses` are especially important because downstream builders depend on them.

Current scene payloads may include:

- `scene_summary`
- `events`
- `entities_present`
- `entity_descriptions`
- `state_changes`
- `relationship_changes`
- `location`
- `time_signals`
- `canonical_characters`
- `character_mentions`
- `entity_world_state`
- `visual_analysis`
- provider and runtime metadata such as:
  - `provider`
  - `resolved_model`
  - `provider_account_alias`
  - `provider_mode`
  - `rotation_used`
  - `attempt_count`
  - `final_status`
  - `error_category`
  - `last_error`

## Identity Payload Expectations

With the current production identity path, the contract should preserve provider-backed identity data such as:

- `alias_map`
- `provider_alias_index`
- `provider_characters`
- `narrator`
- `reference_entities`
- `provider_locked`

The canonical production expectation is:

- `identity_provider = booknlp_clean`

## Failure-State Expectations

Recent hardening work changed contract expectations for failed or degraded runs.

A catastrophic scene-failure run should no longer look like a healthy successful contract with empty canon artifacts.

Contracts should reflect:

- `run_status`
- scene-quality diagnostics
- failed/partial indicators where appropriate
- artifact invalidation if scene failure thresholds are exceeded

## Notes

- the contract intentionally excludes live Python service objects
- the contract is meant to be deterministic enough for downstream rebuild and audit workflows
- contract validation is available through `saga_tools.py validate-encoder-artifacts`
