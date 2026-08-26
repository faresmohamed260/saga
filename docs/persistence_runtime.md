# Persistence Runtime

`packages/persistence_runtime` is now the active runtime surface for structured persistence, vector storage, and provider-backed object storage.

The system-wide storage inventory and conventions live in [docs/storage_architecture.md](B:\Documents\PyCharm\graduationProject\docs\storage_architecture.md).

## Architecture

- The runtime is provider-oriented.
- `PersistenceRuntimeClient` is the unified surface exposed to applications and agents.
- Providers implement the runtime contracts for:
  - structured relational data
  - provider config/status data
  - vector document storage
  - object/blob storage
- `supabase` is currently the primary provider implementation.

This keeps the runtime reusable outside S.A.G.A. while allowing the actual backing platform to be swapped later.

Active runtime configuration is validated eagerly at construction time. Invalid profile identifiers, non-positive pool/timeouts, and missing required provider fields should fail before any provider initialization happens.

## Production Vs Test-Only Modes

The active persistence runtime is now intentionally strict about production behavior.

Production mode:

- `PersistenceProfile.mode='supabase_postgres'`
- requires a PostgreSQL/Supabase database URL
- uses real Supabase Storage for object/blob persistence
- fails fast on missing or invalid production configuration

Test-only mode:

- `PersistenceProfile.mode='test_harness'`
- exists only for local contract tests
- may use SQLite plus a local object-store directory
- must never be used for production deployments, long-lived operational state, or real artifact persistence

The runtime no longer treats SQLite/local object storage as an ambiguous fallback for production-like execution.

## Current Provider

The active provider is `supabase`, implemented in:

- `packages/persistence_runtime/providers.py`

That provider currently exposes:

- `provider_configs`
- `library`
- `identity`
- `jobs`
- `stories`
- `audiobooks`
- `vectors`
- `objects`
- `artifacts`
- `ephemeral`

## Real Supabase Validation

The repo now includes a real-provider validation path for the active self-hosted Supabase runtime:

- script: [scripts/validate_real_supabase_runtime.py](B:\Documents\PyCharm\graduationProject\scripts\validate_real_supabase_runtime.py)
- env-gated pytest: [tests/test_real_supabase_runtime.py](B:\Documents\PyCharm\graduationProject\tests\test_real_supabase_runtime.py)
- cross-runtime stack validator: [scripts/validate_real_runtime_stack.py](B:\Documents\PyCharm\graduationProject\scripts\validate_real_runtime_stack.py)
- env-gated cross-runtime pytest: [tests/test_real_runtime_stack.py](B:\Documents\PyCharm\graduationProject\tests\test_real_runtime_stack.py)

That validation exercises the active Postgres + Storage path against a live Supabase stack, covering:

- provider config/status lifecycle
- normalized provider operational state
- vector document write/query/delete
- object storage upload/download/delete
- durable runtime artifact storage

The cross-runtime stack validator extends this by persisting a combined report produced from live reasoning, retrieval, and web-search runtime activity through the active artifact path.

It should be enabled only in environments where the real Supabase connection env vars are intentionally configured.

## Agent Tool Surface

The runtime exposes LangGraph-compatible tools directly through `PersistenceRuntimeClient.as_langgraph_tools()`.

Those tools now flow through the shared runtime tool builder, so persistence-tool failures use the same:

- envelope shape
- structured traces
- structured runtime events
- error categories
- retryability flags

as the other active runtimes.

Provider config/status reads now have explicit contract semantics:

- provider config upserts return a typed provider-config record
- provider config lookups return `found/config` instead of faking an empty row
- provider status listings return a typed result set with stable `result_count/results` fields
- provider status rows now also expose a normalized `status` snapshot for common operational fields such as health, request state, URLs, and warm timestamps
- provider status replacement rejects missing or duplicate labels before persistence
- provider config/status upserts now also carry `request_metadata` like the other active runtime tool payloads

Current tool names:

- `persistence_upsert_provider_config`
- `persistence_get_provider_config`
- `persistence_get_provider_operational_state`
- `persistence_upsert_provider_status`
- `persistence_list_provider_statuses`

## Provider Operational State

Provider lifecycle consumers in the active architecture should prefer the normalized provider operational state surface over scraping nested config payloads manually.

The canonical normalized response is:

- `provider_name`
- `found`
- `config`
- `runtime_state`
- `statuses`
- `status_count`
- `healthy_labels`
- `ready_labels`
- `error_labels`

`runtime_state` extracts the operational state currently stored inside `provider_configs.payload.runtime_state` into a stable contract with fields such as:

- `active_label`
- `active_api_url`
- `active_ui_url`
- `active_health_url`
- `runtime_generation`

This keeps dashboard/API/agent callers decoupled from storage layout details while preserving the underlying provider config record as the source of truth.

`runtime_state` now also carries normalization and lifecycle diagnostics for active-provider state:

- `active_status_found`
- `status_labels`
- `status_count`
- `diagnostics`

That means callers can detect malformed or contradictory persisted provider state through the contract itself instead of scraping raw payloads or guessing from missing fields. The normalized active endpoint URLs may be hydrated from the matching provider-status row when the runtime-state payload is incomplete, while mismatches are surfaced through `diagnostics`.

## Storage And Artifact Tool Contracts

Object-storage and artifact tools in the active architecture should also expose typed payloads with `request_metadata`.

This now applies to:

- `persistence_ensure_bucket`
- `persistence_upload_text_object`
- `persistence_upload_json_object`
- `persistence_download_text_object`
- `persistence_list_objects`
- `persistence_delete_object`
- `persistence_store_text_artifact`
- `persistence_store_json_artifact`

Agents should consume these typed storage/artifact payloads directly instead of depending on ad hoc dictionary shapes.

This artifact path is now covered end to end in the active architecture:

- `AgentGraphRuntime` can call `persistence_store_text_artifact`
- the persistence runtime stores the durable artifact under enforced conventions
- `apps/dashboard_api` can serve the same stored object from `/runtime/artifacts/object`

## Structured Domain Read/List Contracts

High-traffic persistence read/list tools should also expose typed result payloads instead of raw `{results, result_count}` dictionaries.

This now applies to:

- `persistence_list_books`
- `persistence_list_scenes`
- `persistence_list_records`
- `persistence_list_jobs`
- `persistence_list_stories`
- `persistence_get_audiobook_run`
- `persistence_list_audiobook_runs`

These payloads now include normalized result records plus `request_metadata` so agent orchestration and diagnostics do not depend on implicit list shapes.

The enclosing runtime `trace` now also carries `events`, which are the canonical structured log trail for persistence-tool execution across agent runs.

Single-record reads and vector operations are also moving under the same contract discipline. In the active architecture, callers should prefer the typed payloads from:

- `persistence_get_identity_series`
- `persistence_get_job`
- `persistence_upsert_vector_documents`
- `persistence_query_vector_documents`
- `persistence_delete_vector_documents`
- `persistence_upsert_series`
- `persistence_upsert_book`
- `persistence_upsert_scene`
- `persistence_upsert_record`
- `persistence_list_books`
- `persistence_list_scenes`
- `persistence_list_records`
- `persistence_upsert_identity_series`
- `persistence_get_identity_series`
- `persistence_create_job`
- `persistence_add_job_log`
- `persistence_get_job`
- `persistence_list_jobs`
- `persistence_upsert_story`
- `persistence_list_stories`
- `persistence_upsert_audiobook_run`
- `persistence_upsert_audiobook_chapter`
- `persistence_get_audiobook_run`
- `persistence_list_audiobook_runs`
- `persistence_upsert_vector_documents`
- `persistence_query_vector_documents`
- `persistence_delete_vector_documents`
- `persistence_ensure_bucket`
- `persistence_upload_text_object`
- `persistence_upload_json_object`
- `persistence_download_text_object`
- `persistence_list_objects`
- `persistence_delete_object`
- `persistence_store_text_artifact`
- `persistence_store_json_artifact`

## Enforced Conventions

The runtime now enforces durable artifact families through code, not just docs.

Exact durable buckets:

- `source-documents`
- `generated-images`
- `identity-exports`
- `story-exports`
- `audio-outputs`
- `runtime-reports`

Durable artifact writes should go through `PersistenceRuntimeClient.artifacts`, which:

- chooses the correct bucket for the artifact family
- builds deterministic object paths
- uploads through provider-backed object storage
- links the artifact back into relational metadata via `library_records`

Provider-backed object storage now also exposes `get_object_info(...)` so active services can read durable artifact metadata, including stored content type, without bypassing the runtime.

Vector namespaces are also validated in code. The active retrieval namespace format is:

- `retrieval.<series_id>.<scope_key>`

Ephemeral workspace data should go through `PersistenceRuntimeClient.ephemeral`, which:

- creates temp-only local files/directories outside durable object storage
- stamps expiry timestamps
- supports cleanup through TTL-based deletion

## Provider Resolution

The runtime resolves a database connection in this order:

1. `PersistenceProfile.database_url`
2. `PersistenceRuntimeConfig.supabase_url`
3. `SAGA_SUPABASE_DB_URL`
4. `SUPABASE_DB_URL`
5. `DATABASE_URL`
6. a self-hosted Supabase component configuration assembled from env vars

Supported component env vars:

- `SAGA_SUPABASE_DB_HOST` or `SUPABASE_DB_HOST`
- `SAGA_SUPABASE_DB_PORT` or `SUPABASE_DB_PORT`
- `SAGA_SUPABASE_DB_NAME` or `SUPABASE_DB_NAME`
- `SAGA_SUPABASE_DB_USER` or `SUPABASE_DB_USER`
- `SAGA_SUPABASE_DB_PASSWORD`, `SUPABASE_DB_PASSWORD`, or `POSTGRES_PASSWORD`
- `SAGA_SUPABASE_POOLER_TENANT_ID`, `SUPABASE_POOLER_TENANT_ID`, or `POOLER_TENANT_ID`
- `SAGA_SUPABASE_DB_SSLMODE` or `SUPABASE_DB_SSLMODE`

The self-hosted default is Supavisor's transaction-pooling port `6543`. Production
deployments that provide an explicit database URL must target the transaction
endpoint as well; port `5432` is the session endpoint and can exhaust the tenant
pool when independently composed services create their own SQLAlchemy pools.

If no explicit DB user is supplied but a pooler tenant id is present, the runtime uses the pooler user form `postgres.<tenant_id>`.

## Storage Provider Resolution

For Supabase object storage, the runtime resolves the storage API URL in this order:

1. `PersistenceRuntimeConfig.supabase_api_url`
2. `SAGA_SUPABASE_STORAGE_API_URL`
3. `SUPABASE_STORAGE_API_URL`
4. `SAGA_SUPABASE_API_URL`
5. `SUPABASE_API_URL`
6. `SUPABASE_PUBLIC_URL`

If none of these are set in production mode, the runtime now fails fast instead of assuming a localhost storage endpoint.

The service-role key is resolved from:

1. `PersistenceRuntimeConfig.supabase_service_role_key`
2. `SAGA_SUPABASE_SERVICE_ROLE_KEY`
3. `SUPABASE_SERVICE_ROLE_KEY`
4. `SERVICE_ROLE_KEY`
5. `SUPABASE_SERVICE_KEY`

## Example

```python
from packages.persistence_runtime import (
    PersistenceProfile,
    PersistenceRuntimeConfig,
    create_persistence_client,
)

profile = PersistenceProfile(
    name="production",
    provider="supabase",
)
client = create_persistence_client(
    config=PersistenceRuntimeConfig(profile=profile),
    profile=profile,
)
client.initialize()
```

For dashboard/runtime tests that intentionally use the local harness, set the runtime mode env explicitly:

- `SAGA_RUNTIME_DB_MODE=test_harness`
- `SAGA_MODAL_STATE_DB_MODE=test_harness`

## Schema

Structured tables are created by the runtime schema plus Supabase migrations.

The vector store migration lives at:

- `supabase/migrations/20260705173000_add_vector_documents.sql`

## Notes

- Supabase is the current provider, not the runtime itself.
- The unit tests still use a SQLite harness only for fast contract validation.
- The SQLite harness uses a local object-store directory only for tests; the production path is the real Supabase storage API.
- `PersistenceProfile.mode='test_harness'` must never be used in production.
- Live verification should always be run against the real Supabase provider.
- Modal-backed provider operational state should be persisted through [docs/modal_runtime.md](B:\Documents\PyCharm\graduationProject\docs\modal_runtime.md), not by direct table writes or local JSON files.
- Invalid persistence operations such as bucket/path escape attempts should fail as categorized validation errors through the shared runtime envelope, not as uncategorized exceptions.
- Runtime-owned provider pools and secret summaries are documented in [docs/runtime_secrets.md](B:\Documents\PyCharm\graduationProject\docs\runtime_secrets.md).
