# Storage Architecture

This document defines the intended storage architecture for the active S.A.G.A. rebuild.

The source of truth for storage and persistence is the unified runtime in `packages/persistence_runtime`.
Supabase is a provider implementation of that runtime, not the abstraction itself.

## Core Decision

All persisted system data must belong to exactly one of these categories:

1. `operational structured data`
2. `vector semantic data`
3. `object/blob artifacts`
4. `ephemeral working data`

The correct backend for each category is:

- `Postgres / Supabase relational tables` for operational structured data
- `pgvector in Supabase` for vector semantic data
- `Supabase Storage buckets` for durable objects/blobs
- `provider-local temp/cache storage` for ephemeral working data only

## Runtime Surface

The active runtime surface is `packages/persistence_runtime`.

It currently exposes these domains:

- `provider_configs`
- `library`
- `identity`
- `jobs`
- `stories`
- `audiobooks`
- `vectors`
- `objects`

Agent-facing access is through `PersistenceRuntimeClient.as_langgraph_tools()`.

## Storage Matrix

| Data item | Purpose | Category | Backend | Retention | Source of truth | Runtime access path |
| --- | --- | --- | --- | --- | --- | --- |
| Provider configs | store provider/account configuration payloads | operational structured data | Supabase Postgres | durable until explicitly changed | `provider_configs` table | `provider_configs` store, `persistence_upsert_provider_config`, `persistence_get_provider_config` |
| Provider statuses | store health, warm, endpoint, and rotation status snapshots | operational structured data | Supabase Postgres | durable, rolling updates | `provider_statuses` table | `provider_configs` store |
| Library series | canonical series-level records | operational structured data | Supabase Postgres | durable | `library_series` table | `library` store, `persistence_upsert_series` |
| Library books | canonical book-level records | operational structured data | Supabase Postgres | durable | `library_books` table | `library` store, `persistence_upsert_book`, `persistence_list_books` |
| Library scenes | scene/chapter-level narrative units | operational structured data | Supabase Postgres | durable | `library_scenes` table | `library` store, `persistence_upsert_scene`, `persistence_list_scenes` |
| Library records | scoped entities, events, relationships, prompts, manifests, and generic structured records | operational structured data | Supabase Postgres | durable | `library_records` table | `library` store, `persistence_upsert_record`, `persistence_list_records` |
| Identity analysis payloads | coreference / identity outputs at the series level | operational structured data | Supabase Postgres | durable, replaceable by re-analysis | `identity_series` table | `identity` store, `persistence_upsert_identity_series`, `persistence_get_identity_series` |
| Jobs | persistent run orchestration state | operational structured data | Supabase Postgres | durable with operational retention policy | `jobs` table | `jobs` store, `persistence_create_job`, `persistence_get_job`, `persistence_list_jobs` |
| Job logs | structured run logs and step details | operational structured data | Supabase Postgres | durable with operational retention policy | `job_logs` table | `jobs` store, `persistence_add_job_log` |
| Generated stories | generated story metadata and structured outputs | operational structured data | Supabase Postgres | durable | `generated_stories` table | `stories` store, `persistence_upsert_story`, `persistence_list_stories` |
| Audiobook runs | audiobook generation run state | operational structured data | Supabase Postgres | durable | `audiobook_runs` table | `audiobooks` store, `persistence_upsert_audiobook_run`, `persistence_get_audiobook_run`, `persistence_list_audiobook_runs` |
| Audiobook chapters | chapter-level audiobook output metadata | operational structured data | Supabase Postgres | durable | `audiobook_chapters` table | `audiobooks` store, `persistence_upsert_audiobook_chapter` |
| Retrieval vectors | semantic retrieval embeddings and metadata | vector semantic data | Supabase pgvector | durable while index remains valid | `vector_documents` table in pgvector-backed provider | `vectors` store, `persistence_upsert_vector_documents`, `persistence_query_vector_documents`, `persistence_delete_vector_documents` |
| Prompt/reference vectors | embeddings for prompt and reference retrieval | vector semantic data | Supabase pgvector | durable while source content remains relevant | `vector_documents` namespaced entries | `vectors` store |
| Uploaded source files | user-uploaded PDFs/EPUBs and other source documents | object/blob artifacts | Supabase Storage | durable until explicit deletion or archive policy | storage bucket objects, referenced from relational metadata | `objects` store, `persistence_ensure_bucket`, upload/download/list/delete object tools |
| Generated images | final saved image assets | object/blob artifacts | Supabase Storage | durable | storage bucket objects, referenced from relational metadata | `objects` store |
| Image thumbnails | derived preview assets | object/blob artifacts | Supabase Storage | durable while parent asset exists | storage bucket objects, referenced from relational metadata | `objects` store |
| Prompt manifests / render reports | structured artifact payloads better stored as files | object/blob artifacts | Supabase Storage | durable while asset lineage is needed | storage bucket objects plus relational references | `objects` store, `persistence_upload_json_object` |
| Identity JSON exports | raw or packaged identity outputs | object/blob artifacts | Supabase Storage | durable until replaced or archived | storage bucket objects plus relational references | `objects` store |
| Generated EPUB exports | packaged story exports | object/blob artifacts | Supabase Storage | durable | storage bucket objects plus relational references | `objects` store |
| Audio chapter files | rendered audiobook chapter audio | object/blob artifacts | Supabase Storage | durable | storage bucket objects plus relational references | `objects` store |
| Audio bundles | packaged audiobook output files | object/blob artifacts | Supabase Storage | durable | storage bucket objects plus relational references | `objects` store |
| Modal provider operational state | provider endpoint warmth, rotation, health, active endpoint, and failover status | operational structured data | Supabase Postgres | durable rolling operational state | `provider_configs.runtime_state` plus `provider_statuses` rows | unified runtime provider state |
| Modal/ComfyUI workflow cache and prefetch manifest | deployment-local model/workflow cache state | ephemeral working data | Modal container filesystem/cache volume | ephemeral, rebuildable | provider-local runtime cache | not platform persistence; keep outside unified runtime |
| Temporary render/decode scratch files | transient work products during generation | ephemeral working data | provider-local temp storage | TTL-bound, delete after run unless promoted | provider runtime scratch space | not yet centralized; should remain ephemeral |

## Conventions

### Relational ownership boundaries

- `provider_configs` and `provider_statuses` own provider metadata and operational state.
- `library_*` owns canonical source-analysis data.
- `identity_series` owns identity/coreference structured outputs.
- `jobs` and `job_logs` own orchestration state.
- `generated_stories` owns generated story metadata.
- `audiobook_*` owns audiobook run metadata.
- file/blob references should be stored in relational payloads or dedicated record rows, but file bodies must not be stored in relational rows.

### Vector namespaces

Use stable namespace prefixes:

- `library:<series_id>:scenes`
- `library:<series_id>:books`
- `identity:<series_id>:entities`
- `prompts:<series_id>:references`
- `stories:<series_id>:generated`

Each vector document should carry metadata that includes:

- `series_id`
- `book_id` when applicable
- `scene_id` when applicable
- `record_type`
- `source_scope`
- `content_version` or equivalent invalidation marker when available

### Object storage buckets and path layout

Recommended bucket families:

- `source-documents`
- `generated-images`
- `identity-exports`
- `story-exports`
- `audio-outputs`
- `runtime-reports`

Recommended object path layout:

- `series/<series_id>/books/<book_id>/...`
- `series/<series_id>/assets/<entity_id>/...`
- `series/<series_id>/audio/runs/<run_id>/...`
- `series/<series_id>/stories/<story_id>/...`
- `providers/<provider_name>/reports/...`

Object path rules:

- never use absolute paths
- never use `..`
- prefer stable ids over display names
- keep derivative assets near their owning parent object

### Ephemeral data lifecycle

Ephemeral data must obey these rules:

- it is not the system source of truth
- it must be safe to delete and regenerate
- it should live in provider-local temp/cache space only
- if it becomes a user-visible or workflow-relevant artifact, promote it into `objects`
- if it becomes queryable metadata, store a relational reference in `library_records`, `jobs`, `generated_stories`, or `audiobook_*`

Recommended lifecycle:

1. create in provider-local temp/cache storage
2. use during the running task
3. delete automatically at task completion or TTL expiry
4. promote only explicit keep-worthy outputs into object storage

## Current Coverage Assessment

Covered now by the unified runtime:

- provider configs
- provider statuses at the schema/store level
- library series/books/scenes/records
- identity series payloads
- jobs and logs
- generated stories
- audiobook runs and chapters
- vector persistence
- object/blob storage
- enforced durable artifact bucket/path policies
- enforced vector namespace validation
- ephemeral workspace lifecycle helpers
- LangGraph-native tool access for the domains above

## Remaining Bypasses

Resolved in the active architecture:

- [packages/retrieval_runtime/client.py](B:\Documents\PyCharm\graduationProject\packages\retrieval_runtime\client.py) now persists durable retrieval state through `packages.persistence_runtime.vectors` instead of local `index.json`.
- [integrations/comfyui/token_pool.py](B:\Documents\PyCharm\graduationProject\integrations\comfyui\token_pool.py), [integrations/kokoro_tts/token_pool.py](B:\Documents\PyCharm\graduationProject\integrations\kokoro_tts\token_pool.py), [integrations/xcore_litbank/token_pool.py](B:\Documents\PyCharm\graduationProject\integrations\xcore_litbank\token_pool.py), and [saga/providers/modal_state.py](B:\Documents\PyCharm\graduationProject\saga\providers\modal_state.py) now persist provider operational state through `provider_configs` and `provider_statuses`.

## Residual External Couplings

The remaining active couplings outside the unified runtime boundary are now narrow and explicit:

- provider-local Modal model/workflow caches in:
  - [integrations/comfyui/modal_app.py](B:\Documents\PyCharm\graduationProject\integrations\comfyui\modal_app.py)
  - [integrations/kokoro_tts/modal_app.py](B:\Documents\PyCharm\graduationProject\integrations\kokoro_tts\modal_app.py)
  - [integrations/xcore_litbank/modal_app.py](B:\Documents\PyCharm\graduationProject\integrations\xcore_litbank\modal_app.py)
- local-only debug entrypoints in the Modal apps that now print metadata to stdout but do not create durable local artifacts
- provider runtime caches and temp files that remain intentionally ephemeral and outside canonical persistence

The dashboard now consumes runtime artifact references and `/runtime/artifacts/object` for durable artifact access. The old `/runtime/file` fallback has been removed from the active architecture.

## Enforcement Rule

For new code in the active architecture:

- do not add new direct database writes outside `packages/persistence_runtime`
- do not add new durable file/blob writes outside `packages/persistence_runtime.objects`
- do not add new semantic vector writes outside `packages/persistence_runtime.vectors`
- do not treat provider-local cache files as durable system state

If a new feature needs storage and does not fit the current runtime surface, extend the unified runtime instead of creating a side abstraction.
