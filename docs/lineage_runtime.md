# Artifact Lineage Runtime

`packages/lineage_runtime` is the provider-neutral identity and history boundary for stage artifacts. It does not know about books, agents, Modal, Supabase, or orchestration policy.

## Guarantees

- Canonical SHA-256 fingerprints are stable across dictionary ordering and reject non-finite floats.
- Secret-like fields are redacted before hashing or persistence.
- A stage input fingerprint covers projected request inputs, direct parent lineage fingerprints, and explicit runtime, schema, quality-policy, prompt, workflow, model, and provider-configuration identities.
- Output fingerprints cover the owning stage's persisted artifact projection, not timing or retry metadata.
- Every execution, adoption, and reuse event is appended to `stage_lineage_records`; no update or delete operation is exposed.
- Production executions also store an immutable output snapshot through `persistence_runtime.artifacts`. The lineage record contains its bucket, object path, record ID, and output fingerprint.
- Reuse requires both matching lineage and a current accepted output snapshot. Missing or mutated artifacts fail closed.

## Invalidation

`production_orchestration` computes lineage immediately before each stage. Unchanged stages are reused. A changed input, source digest, artifact output, prompt/model/workflow/provider identity, schema, runtime, or quality policy invalidates that stage. Its new lineage fingerprint then invalidates only transitive downstream stages.

Executable domain stages receive accepted upstream outcomes only. Their own prior outcome and downstream outcomes are excluded, preventing stale story IDs or media from influencing post-execution inspection. Packaging is the sole exception because its current manifest is its persisted inspection surface.

Generation intents and blueprints are retained as immutable content versions. New planning inputs no longer delete prior versions.

## Configuration

The composition root resolves non-secret active identifiers from stage configuration and code/workflow digests. Deployment operators can override identifiers without code changes:

```powershell
$env:SAGA_STAGE_LINEAGE_VERSIONS_JSON = '{"visual_generation":{"workflow":"entity-workflow-v4"},"narrative_support":{"quality_policy":"support-v3"}}'
```

The value must be a JSON object keyed by stage. Never place tokens or credentials in this variable. Provider credentials remain in provider-owned persistence records and are excluded by canonical sanitization as defense in depth.

## Operations

Use `scripts/validate_real_production_execution.py` for a bounded queued validation. It accepts `--premise`, `--target-words-per-scene`, and `--visual-type`, reports lineage modes, and enforces a hard deadline.

Inspect history through `persistence.lineage.list(run_id=...)`. For each latest record verify:

- accepted status
- expected execution mode
- expected parent fingerprints
- non-empty version identities
- `payload.output_artifact_version.bucket_name`
- `payload.output_artifact_version.object_path`

Storage writes occur before the lineage database append. A database failure after upload can leave an unreferenced immutable object; periodic orphan collection should compare lineage artifact records with storage objects before deletion.

## Real Validation

On August 8, 2026, run `real-lineage-input-20260808a` reused analysis foundation, canon extraction, and character/world modeling for the accepted *The Lost Sisters* series after changing the story premise. Planning through packaging reran. All nine latest stages have immutable output snapshots.

The first support attempt failed closed because an evaluator confused blueprint-authorized present events with unsupported prior canon. Temporal scope and plan alignment were added to the owning support contract; retry accepted only after the unsupported prior-motive claim was revised.

Final evidence:

- one 348-word chapter; support rate 1.0, unsupported rate 0.0, contradiction rate 0.0
- continuity coverage 1.0 for canon, character, and entity references
- accepted 512x512 object image; non-black; visual scores 0.95-0.98
- accepted mono 24 kHz audiobook; 129.89 seconds; mean WER 0.0238
- valid EPUB 3 with an uncompressed first `mimetype` entry
- one consistent story ID across narrative, visual, audio, and package records

The local audit is `tmp_live_execution_runtime/real-lineage-input-20260808a/quality-audit.json`.

## Residual Risks

- Provider calls are not immediately cancellable mid-request; execution cancellation remains cooperative at stage boundaries.
- Orphan snapshot collection is not automated yet.
- Historical mutable domain projections created before lineage remain migration-era records; immutable snapshots apply to newly recorded production lineage.
- Code-file digests are conservative and may invalidate a stage for a non-behavioral edit in its prompt-owning module. Explicit release identifiers can replace digests when deployment release management is introduced.
