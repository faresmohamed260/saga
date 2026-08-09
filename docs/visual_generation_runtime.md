# Visual Generation Runtime

`packages/visual_generation` is the active, LangGraph-native visual planning and rendering slice. It has no legacy dependency and consumes only generated stories that passed `require_narrative_semantic_acceptance(...)`.

## Ownership

The package owns portable contracts and agents for:

- character visual baselines
- evidence-driven per-scene character-state deltas
- location, creature, and object dossiers
- scene visual plans
- positive and negative prompt policy
- render requests and persisted image artifacts
- technical and semantic quality decisions
- bounded retry, re-audit, and rejected-target resume behavior

Concrete providers are injected. The composition root in `service.py` wires:

- `persistence_runtime` for Postgres/Supabase records and object storage
- `reasoning_runtime` for Mistral visual planning and multimodal semantic QA
- `modal_runtime` plus `integrations/comfyui` for account rotation, endpoint lifecycle, and image rendering

The domain graph never imports Modal or ComfyUI. Image bytes are persisted immediately and are not stored in LangGraph checkpoint state.

## Graph

The main graph is:

1. visual planning
2. prompt construction
3. render
4. technical and semantic audit
5. conditional retry
6. final decision

Planning is split into concurrent character, entity, and scene calls. Bounded jobs scope planning to requested targets and selected-scene dependencies. One targeted repair round requests missing stable IDs before the graph fails closed.

Characters route to `character_sheet`; locations, creatures, objects, and scenes route to `entity_generation`. Every render attempt receives a cryptographically randomized 63-bit seed. Both workflow files retain `control_after_generate: randomize`.

## Quality Policy

Technical QA rejects corrupt data, wrong dimensions, undersized payloads, black images, and blank images. Semantic QA uses a Mistral vision profile and checks prompt alignment, subject consistency, composition, photorealism, defects, and explicit hard-constraint violations.

Explicit negative-prompt or target violations override contradictory numeric scores. Failed semantic providers fail closed. Accepted renders are preserved while only rejected targets are eligible for retry.

## Operations

Run a new bounded job:

```powershell
python scripts/run_visual_generation.py `
  --series-id <series-id> `
  --story-id <accepted-story-id> `
  --include-types character,location,creature,object,scene `
  --max-renders-per-type 1 `
  --max-attempts 2
```

Re-audit persisted images without rendering:

```powershell
python scripts/run_visual_generation.py --series-id <series-id> --story-id <story-id> --audit-existing
```

Retry only persisted rejected targets:

```powershell
python scripts/run_visual_generation.py --series-id <series-id> --story-id <story-id> --retry-existing --max-attempts 2
```

Required environment configuration follows the existing runtime conventions: `SAGA_RUNTIME_DB_*`, `SAGA_SUPABASE_*`, `MISTRAL_API_KEY`, and persisted `modal_comfyui` provider configuration. Visual-specific overrides are `SAGA_VISUAL_PLANNING_*`, `SAGA_VISUAL_QUALITY_MODE`, `SAGA_VISUAL_QUALITY_MODEL`, and `SAGA_VISUAL_IMAGE_*`.

## Live Validation

Validation used accepted persisted stories from *The Lost Sisters* and *The Queen of Nothing*, one target per image type, 512x512, four steps, CFG 1.2, and no warm GPU reservation.

- *The Lost Sisters*: five technically valid renders; four semantic accepts; the Lake of Masks location was correctly rejected twice because people and narrative action violated the empty-location policy.
- *The Queen of Nothing*: final corrected run completed in 69.5 seconds: planning 13.6 seconds, five renders 24.2 seconds, semantic audit 14.4 seconds. Four renders passed. Baphen's character sheet remained rejected after one selective retry because of side-profile identity/anatomy drift.
- Selective retries rendered one target in 4.8-5.1 seconds and audited it in 3.2-4.4 seconds without regenerating accepted targets.
- All attempts used distinct randomized seeds and the persisted Modal account pool (`47` accounts available; live tests used `member-01`).

The rejected outputs are expected fail-closed evidence, not runtime failures. Preview files and complete JSON reports are under `tmp_live_visual_generation/`; durable reports and images are in Supabase object storage.
