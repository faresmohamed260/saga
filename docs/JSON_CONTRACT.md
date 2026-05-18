# S.A.G.A. JSON Contract

The dashboard export produces a single JSON document representing the current S.A.G.A. run.

## Top-Level Shape

```json
{
  "contract_version": "1.0.0",
  "generated_at_utc": "2026-04-10T12:00:00+00:00",
  "app": {},
  "configuration": {},
  "inputs": {},
  "outputs": {},
  "runtime": {}
}
```

## Sections

### `app`

- `name`
- `pipeline_status`

### `configuration`

- `analysis_model`
- `identity_model`
- `target_scene_words`

### `inputs`

- `books`

### `outputs`

- `chapters`
- `scene_analyses`
- `resolved_scene_analyses`
- `entity_registry`
- `state_result`
- `canon_snapshot`
- `timeline`
- `character_timelines`
- `identity_result`
- `causal_graph_result`
- `story_index_summary`

### `runtime`

- `elapsed_seconds`
- `last_scene_seconds`
- `avg_scene_seconds`
- `processed_scene_count`
- `estimated_total_scenes`

## Notes

- The export intentionally excludes live service objects such as in-memory query/index instances.
- The export is suitable for saving, sharing, and downstream automation.
- `target_scene_words = 0` means one full chapter per scene and is the default mode.
