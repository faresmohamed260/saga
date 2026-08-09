**Canon Extraction Runtime**

Active production slice for Group 2:

- `EventAgent`
- `EntityAgent`
- `RelationshipAgent`
- `TimelineAgent`

This slice depends on persisted Group 1 outputs from the active `Analysis Foundation` runtime:

- books
- chapters
- scenes
- canonical identity bundle

**Active surfaces**

- Package runtime: `packages/canon_extraction`
- LangGraph surface: `packages/agent_runtime/canon_extraction.py`
- Runner script: `scripts/run_canon_extraction.py`

**Artifact families**

- `event`
  - chapter/scene-anchored canon happenings
  - owned by `EventAgent`
- `entity`
  - non-character canon entities
  - owned by `EntityAgent`
- `relationship`
  - meaningful canon relationships between characters and/or entities
  - owned by `RelationshipAgent`
- `timeline`
  - deterministic ordered progression derived from persisted events
  - owned by `TimelineAgent`

**Ownership boundaries**

- `EventAgent`
  - extracts event records only
  - does not own entity deduplication or timeline ordering
- `EntityAgent`
  - extracts non-character entities only
  - excludes canonical characters already handled by Group 1 identity
- `RelationshipAgent`
  - extracts relationship records only
  - resolves against canonical characters and persisted entities
- `TimelineAgent`
  - deterministic only
  - builds ordered timeline rows from persisted event artifacts

**Required env**

- `SAGA_RUNTIME_DB_URL`
- `SAGA_RUNTIME_DB_MODE=supabase_postgres`

Optional:

- `SAGA_RUNTIME_LOCAL_STORAGE_ROOT`
- `SAGA_SUPABASE_API_URL`
- `SAGA_SUPABASE_SERVICE_ROLE_KEY`
- `SAGA_CANON_EXTRACTION_REASONING_PROFILE`
- `SAGA_CANON_EXTRACTION_REASONING_MODE`
- `SAGA_CANON_EXTRACTION_REASONING_TIMEOUT_SECONDS`
- `SAGA_CANON_EXTRACTION_REASONING_MAX_RETRIES`
- `SAGA_CANON_EXTRACTION_PARALLELISM`
- `SAGA_CANON_SCENE_SLICE_BATCH_SIZE`
- `SAGA_CANON_MAX_EVENTS_PER_SCENE`
- `SAGA_CANON_MAX_ENTITIES_PER_SCENE`
- `SAGA_CANON_MAX_RELATIONSHIPS_PER_SCENE`
- `SAGA_CANON_RESUME_STAGES`

If `SAGA_SUPABASE_API_URL` is not configured, `SAGA_RUNTIME_LOCAL_STORAGE_ROOT` must be configured so runtime reports can fall back to local artifact storage while relational persistence still uses PostgreSQL.

**Reasoning prerequisites**

- Reasoning provider accounts must already exist in active provider-config persistence
- Group 2 uses the active reasoning runtime only
- No agent-local provider wiring or secret handling is allowed

**Run on existing Analysis Foundation outputs**

```powershell
venv\Scripts\python.exe scripts\run_canon_extraction.py `
  --series-id real-holly-black-lost-sisters `
  --thread-id canon-extraction-live
```

**Run end to end with upstream Analysis Foundation**

```powershell
venv\Scripts\python.exe scripts\run_canon_extraction.py `
  --series-id real-holly-black-lost-sisters `
  --thread-id canon-extraction-live `
  --run-analysis-foundation `
  --source "D:\Books\Ebooks\Holly Black\The Lost Sisters\The Lost Sisters.epub"
```

This path still consumes persisted Group 1 artifacts. It does not pass raw book text directly into Group 2.

**Current hardening behavior**

- LangGraph-native orchestration with durable checkpointing
- bounded reasoning over deterministic scene-slice batches
- bounded parallel extraction inside event, entity, and relationship stages
- per-job latency instrumentation in runtime reports
- configurable scene-slice batch size
- deterministic per-scene caps for event/entity/relationship fan-out
- terminal leaf fallback for exhausted provider retries
- explicit persisted-stage resume via `SAGA_CANON_RESUME_STAGES`
- durable per-job extraction records for event, entity, and relationship stages
- deterministic final artifact rebuild from persisted stage jobs
- deterministic ID generation and timeline ordering
- deterministic entity/relationship label normalization
- per-batch relationship prompts constrained to scene-relevant entity context
- reruns replace prior canon records for the same series instead of accumulating stale artifacts
- canonical character resolution against Group 1 identity bundle
- non-character entity extraction separated from character identity
- runtime reports stored through active persistence artifacts

**Validation expectations**

- verify event/entity/relationship/timeline records persist correctly
- verify timeline sequence is contiguous and event-backed
- verify canonical character references resolve through Group 1 identity
- verify real runtime/provider metadata is captured in output records and reports
- verify output quality for:
  - events
  - entities
  - relationships
  - timeline coherence

**Current known risk**

- Quality still depends on the active reasoning provider's JSON extraction quality. The runtime owns deterministic structure and normalization, but nuanced canon judgment may still need another hardening pass after real-book evaluation.

**Scalability Validation Snapshot - 2026-07-22**

Lost Sisters optimized canon run:

- Output: `tmp_live_canon_extraction_pg/lost_sisters_canon_scalability_r13_cold_job_durable.json`
- Rebuilt output after deterministic participant-support fix: `tmp_live_canon_extraction_pg/lost_sisters_canon_scalability_r16_remerge_dialogue_support.json`
- Report: `analysis_outputs/unified_storage/runtime-reports/providers/canon-extraction/reports/validation/04d832187231-real-holly-black-lost-sisters-v10-canon-scalability-lost-sisters-r13-cold-job-durable-canon-extraction-report.json`
- Counts: 55 events, 121 entities, 55 relationships, 55 timeline rows
- Cold runtime: 631.7711s
- Resume/remerge runtime: 1.8137s
- Attribution: `tmp_live_canon_extraction_pg/lost_sisters_attribution_eval_scalability_r16_remerge_dialogue_support.json`
- Attribution metrics: F1 1.0, narrator accuracy 1.0, unsupported ref rate 0.0, contamination rate 0.0
- Downstream CWM report: `analysis_outputs/unified_storage/runtime-reports/providers/character-world-modeling/reports/validation/1812a55ae0da-real-holly-black-lost-sisters-v10-cwm-after-canon-scalability-lost-sisters-r16-remerge-dialogue-support-character-world-modeling-report.json`
- Downstream CWM metrics: all grounding/support/dedup/usefulness rates clean

Queen of Nothing optimized canon run:

- Output: `tmp_live_canon_extraction_pg/queen_of_nothing_canon_scalability_r12_cold_job_durable.json`
- Report: `analysis_outputs/unified_storage/runtime-reports/providers/canon-extraction/reports/validation/5cb02c2e3c7e-real-holly-black-queen-of-nothing-cwm-quality-v1-canon-scalability-qon-r12-cold-job-durable-canon-extraction-report.json`
- Counts: 433 events, 945 entities, 420 relationships, 433 timeline rows
- Cold runtime: 2810.693s
- Durable stage jobs: 33 event jobs, 33 entity jobs, 33 relationship jobs
- Stage timings: event 730.4872s, entity 1239.6778s, relationship 833.6485s, timeline 6.8795s
- Structural quality: titles present, entity names present, no invalid relationships, contiguous event-backed timeline

Remaining blocker:

- Provider latency remains the dominant limit; entity extraction is still the longest stage on full novels.
- The current bounded full-novel evidence completes inside the 50-minute validation bound, but this is not yet a low-latency runtime.
- Queen of Nothing downstream CWM passes after CWM scalability/resume hardening.

Queen of Nothing downstream CWM validation:

- Report: `analysis_outputs/unified_storage/runtime-reports/providers/character-world-modeling/reports/validation/2da27289f547-real-holly-black-queen-of-nothing-cwm-quality-v1-cwm-after-canon-scalability-qon-r11-character-world-modeling-report.json`
- Counts: 173 character profiles, 173 stable character states, 834 world states
- Quality: profile grounding 1.0, unsupported profile claims 0.0, stable attribute precision 1.0, relationship support 1.0, entity deduplication 1.0, useful entity rate 1.0, unsupported world fact rate 0.0
