# Production Orchestration Runtime

`packages/production_orchestration` is the active top-level coordinator and deliverable-packaging slice. It coordinates rebuilt agent groups without owning or duplicating their domain logic.

## Boundaries

The core owns:

- explicit stage order and dependency policy
- portable orchestration requests, outcomes, decisions, lineage, and manifests
- lineage-verified inspect-before-execute idempotency
- bounded retry and fail-closed routing
- durable run state and logs through `persistence_runtime.jobs`
- LangGraph checkpoints after every stage
- versioned EPUB and JSON-manifest packaging

Each stage is an injected `OrchestrationStage`. The production composition root binds active services for execution and active stores for persisted acceptance inspection. Providers remain owned by their existing runtimes. The graph has no Modal, ComfyUI, Kokoro, identity-provider, retrieval-provider, or reasoning-provider imports.

Large image and audio objects never enter graph state or packaging memory. The manifest references accepted objects in storage. Only generated chapter text is materialized to build the EPUB.

## Stage Policy

The production order is:

1. analysis foundation
2. canon extraction
3. character/world modeling
4. generation planning
5. narrative generation
6. narrative semantic support
7. visual generation
8. audiobook generation
9. artifact packaging

Selecting a stage expands its required dependencies. Packaging inclusion is separate from execution selection: `include_visuals` and `include_audiobook` collect existing accepted artifacts, while `selected_stages` explicitly controls whether those generators run.

Before executing a stage, the coordinator inspects durable acceptance artifacts and recomputes their lineage. Reuse requires matching request inputs, direct parent fingerprints, runtime/schema/policy/prompt/workflow/model/provider identities, current output fingerprints, and an immutable output snapshot. A mismatch reruns exactly that stage and its transitive dependents. Executable stages receive upstream outcomes only, so stale current or downstream story IDs cannot leak into inspection. See `docs/lineage_runtime.md`.

A failed stage stops downstream execution. Resuming the same run preserves accepted outcomes and retries only unresolved or invalidated stages up to `max_attempts`. Adding a new stage invalidates only that stage and downstream outcomes. Run IDs cannot be rebound to another series, story, blueprint, audiobook, or packaging-inclusion policy.

## Deliverables

The version-1 package contains:

- EPUB 3 chapter content
- references to accepted visual assets
- reference to the accepted audiobook manifest/object
- newest runtime report per producing stage
- canon, character, entity, blueprint, and stage-decision provenance
- canonical JSON manifest with run-scoped immutable storage paths
- SHA-256 for newly built EPUB content and existing images when available

## Operations

Package existing accepted artifacts without provider inference:

```powershell
python scripts/run_production_orchestration.py `
  --run-id <immutable-run-id> `
  --series-id <series-id> `
  --story-id <accepted-story-id> `
  --audiobook-run-id <accepted-audiobook-run-id> `
  --stages artifact_packaging
```

Execute or resume selected generation stages before packaging:

```powershell
python scripts/run_production_orchestration.py `
  --run-id <run-id> `
  --series-id <series-id> `
  --story-id <story-id> `
  --stages visual_generation,audiobook_generation,artifact_packaging `
  --max-attempts 2
```

The service uses the existing `SAGA_RUNTIME_DB_*` and `SAGA_SUPABASE_*` configuration. Provider secrets remain in their owning runtimes and are never accepted by the orchestration request.

Non-secret lineage release identities may be overridden with `SAGA_STAGE_LINEAGE_VERSIONS_JSON`.

## Validation

Deterministic persistence-backed tests cover dependency expansion, accepted-stage reuse, fail-closed routing, selective resume, idempotent completed runs, immutable run identity, manifest equality, and EPUB structure.

Real package-only validation used accepted *The Lost Sisters* and *The Queen of Nothing* artifacts in Supabase:

- *The Lost Sisters* hardened run: 9.6 seconds, three chapters, four accepted visuals, one accepted audiobook, four latest runtime reports, and one EPUB.
- *The Queen of Nothing*: 14.6 seconds, four chapters, four accepted visuals, one accepted audiobook, runtime reports, and one EPUB.
- Supabase integrity verification confirmed returned/persisted manifest equality, EPUB SHA-256 equality, valid ZIP entries, and the required uncompressed EPUB MIME entry.
- No reasoning, retrieval, Modal, ComfyUI, Kokoro, or identity-provider inference was initialized during package-only runs.

Local validation reports are under `tmp_live_production_orchestration/`; durable EPUBs and manifests are in the private `story-exports` bucket.

## Execution Hardening

Production work now runs through `packages/execution_runtime`, which provides durable admission, distributed concurrency policy, leases, heartbeats, retries, explicit replay, cancellation, stale-worker recovery, and telemetry. See `docs/execution_runtime.md` for operations and real raw-book validation.

The packaging boundary independently requires both narrative-generation quality and semantic-support acceptance. A stale accepted stage outcome cannot bypass final quality validation.

## Lineage Validation

The real queued input-mutation run `real-lineage-input-20260808a` reused only analysis, canon, and character/world outputs. Planning, narrative, support, visual, audio, and packaging reran. The final manifest references one consistent new story and contains accepted image, audiobook, and EPUB artifacts. Full metrics and operations are in `docs/lineage_runtime.md`.
