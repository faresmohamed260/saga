# Durable Execution Runtime

`packages/execution_runtime` is the provider-neutral work admission and worker boundary for production orchestration. Domain stages remain in `production_orchestration`; durable queue state remains owned by `persistence_runtime`.

## Guarantees

- Idempotent submission by immutable `run_id`.
- Atomic Postgres claims using a queue-policy row lock plus `FOR UPDATE SKIP LOCKED`.
- Global, per-series, and per-capability admission limits.
- Opaque lease tokens, periodic heartbeats, and stale-worker write rejection.
- Exponential retry delay, dead-letter decisions, and explicit terminal replay.
- Queued cancellation and cooperative cancellation at the next unresolved stage boundary.
- Accepted orchestration outcomes survive retries and replays.
- Structured queue/worker telemetry is persisted and exported as a runtime report.
- A telemetry-export failure is reported but cannot reverse committed work.
- Terminal execution is normalized by `observability_runtime`; observer or exporter failure cannot reverse committed work.

The scheduler derives capabilities from the resolved stage plan. Requests cannot self-declare cheaper capabilities to bypass image, TTS, coreference, reasoning, retrieval, or storage limits.

## Lifecycle

Queue states are `queued`, `leased`, `retry_wait`, `cancel_requested`, `succeeded`, `cancelled`, and `dead_letter`.

A worker must present the current owner and opaque lease token to heartbeat, complete, or fail work. Expired tokens are rejected before recovery, preventing split-brain completion. Recovery converts expired work to `retry_wait`, `cancelled`, or `dead_letter` according to cancellation and attempt state.

Dead-letter and cancelled items require an explicit `retry` operation. Replay may update the orchestration request and attempt budget, while the orchestration store independently enforces immutable series/story/provider-artifact identity.

## Commands

```powershell
python scripts/run_execution_worker.py submit --request-json request.json
python scripts/run_execution_worker.py worker --worker-id worker-01 --poll
python scripts/run_execution_worker.py status --queue-id <queue-id>
python scripts/run_execution_worker.py cancel --queue-id <queue-id> --reason "operator request"
python scripts/run_execution_worker.py retry --request-json request.json --max-attempts 2
```

Configuration uses `SAGA_RUNTIME_DB_*`, `SAGA_SUPABASE_*`, and:

- `SAGA_EXECUTION_QUEUE_NAME`
- `SAGA_EXECUTION_LEASE_SECONDS`
- `SAGA_EXECUTION_GLOBAL_LIMIT`
- `SAGA_EXECUTION_PER_SERIES_LIMIT`
- `SAGA_EXECUTION_DEFAULT_CAPABILITY_LIMIT`
- `SAGA_EXECUTION_CAPABILITY_LIMITS_JSON`
- `SAGA_OBSERVABILITY_RETENTION_DAYS`

Provider credentials remain in provider-owned persistence records. Queue payloads and telemetry contain no provider tokens.

`SAGA_STAGE_LINEAGE_VERSIONS_JSON` is forwarded unchanged to production orchestration. It contains release identities only, never credentials.

## Validation

`scripts/validate_real_execution_runtime.py` validates independent-client contention, stale-token rejection, lease recovery, replay admission, and telemetry against real Supabase/Postgres.

The August 8, 2026 validation completed in 0.838 seconds with exactly one concurrent claim under `global_limit=1`, one recovered lease, stale completion rejection, and five persisted events.

`scripts/validate_real_production_execution.py` runs a bounded real-book job with stage progress and a hard deadline. The real *The Lost Sisters* run processed 16,224 source words and produced:

- 15 source scenes and 18 resolved identities.
- 48 canon events, 78 entities, and 48 timeline entries.
- 18 character profiles and 78 world-state records.
- One 261-word generated chapter with 100% semantic support, zero contradictions, and all narrative quality metrics at 1.0 after provenance hardening.
- One accepted 512x512 object PNG, 245,087 bytes, entropy 7.243, and no black frame.
- One accepted mono 24 kHz audiobook, 96.725 seconds, with segment word-match rates of 94.21% and 97.39%.
- A valid EPUB 3 package with matching SHA-256 and an accepted manifest.

Fresh provider stages took approximately 598 seconds in aggregate. A hardened reuse-and-package run passed all nine inspectors and completed in 4.4 seconds without provider inference.

The live audit exposed and fixed two fail-closed defects: generated story ID inspection when `story_id` is initially blank, and dropped outline provenance causing false continuity acceptance. Narrative quality is now rechecked by narrative inspection, semantic-support inspection, and packaging.

## Residual Risks

- Cancellation is cooperative between orchestration stages; provider calls need provider-specific cancellation support for immediate interruption.
- Admission limits are queue-local configuration and should be managed as deployment configuration when multiple queue classes are introduced.
- Autoscaling and alert routing remain deployment-platform concerns; this package exports the state and telemetry needed to implement them.
- Immutable lineage snapshot orphan collection is not automated after a storage-success/database-failure edge case.
