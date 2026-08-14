# Real-book vertical slice qualification

## Scope

- Source: *A Curse for True Love* by Stephanie Garber.
- Source size: 82,145 parsed words across 50 chapters.
- Execution: current clean architecture, Supabase/Postgres persistence, Modal XCore LitBank identity resolution, and loopback-only Ollama reasoning.
- Cloud LLM fallback: disabled for the canon run.

## Accepted analysis

Run `vertical-slice-20260814b` accepted `analysis_foundation` in 236.8 seconds. Persisted output contains:

- 1 book
- 50 chapters
- 100 scenes
- 179 identities
- identity provider `modal_xcore_litbank`

Run `vertical-slice-canon-20260814b` reused the accepted analysis in 1.93 seconds, proving lineage-based reuse.

## Accepted canon and character/world model

Run `vertical-slice-canon7-20260814b` completed the resumed canon stage in 214.19 seconds. Persisted output contains 148 events, 36 entities, 39 relationships, and 148 timeline entries, with no orphan timeline rows or empty names/titles. All semantic artifacts identify `ollama_local` and `mistral:7b-instruct`; no cloud fallback was used.

Character/world synthesis completed within two bounded 240-second checkpoint windows. Per-batch persistence retained all progress across the boundary. Run `vertical-slice-cwm5-20260814b` then accepted the persisted result in 13.6 seconds total: 42 canon-grounded character profiles, 42 stable character states, and 36 world states.

The local model-facing character evidence is now deterministically compacted and dynamically batched by a 14,000-character prompt budget. On the real book, the largest single prompt was 12,732 characters and the largest batch prompt was 13,615 characters. A real Evangeline profile request completed in 19.28 seconds, including an 8.58-second model load.

## Accepted generation

Run `vertical-slice-plan3-20260814b` generated and accepted a new one-chapter blueprint with exactly two scenes. Generation planning took 13.0 seconds with successful local-provider provenance and no deterministic fallback.

The final qualification uses the unambiguous premise: “During the first winter after the war, Evangeline discovers that a disputed Solstice oath could reopen an old alliance or destroy the fragile peace.” The persisted blueprint is `generation-blueprint-e78c6c2a2307e590`.

Run `vertical-slice-final-narrative2-20260814b` generated the chapter in 11.03 seconds after one bounded quality rewrite recovered a sparse first response. The persisted story is `generated-story-ffffd58c9d9bc765` and contains one 215-word chapter, *The Solstice Oath*.

Run `vertical-slice-final-support-20260814b` completed retrieval-grounded semantic support in 142.76 seconds and accepted the final story with factual-support rate 1.0, unsupported-invention rate 0.0, contradiction rate 0.0, and provider-success rate 1.0. It performed one semantic revision and then accepted both scenes. The final orchestration report completed in 153.8 seconds and is persisted at:

`runtime-reports/providers/qualification-runtime/reports/production-stage-slice/754c32f11886-vertical-slice-final-support-20260814b-narrative_support-qualification.json`

## Diagnosed defects

1. Partial-stage qualification incorrectly invoked the full-deliverable evaluator and demanded a generated story. The CLI now persists a stage-slice report instead.
2. Analysis-only qualification invoked an unrelated cloud generation-planning preflight. Preflights are now stage-aware.
3. Canon request budgeting hardcoded provider `mistral`; local requests were rejected before inference. The budget now follows the configured runtime provider.
4. Canon errors discarded the provider `last_error`. Failure messages now retain it.
5. Fixed-size character batches exceeded the local model context and lost stage progress. Prompt-size batching, evidence compaction, and atomic batch persistence now bound and resume the work.
6. Planning accepted duplicate chapter indices and orchestration reused malformed cached plans. Planning now normalizes exact requested structure, the quality gate validates it, and orchestration refuses malformed reuse.
7. Sparse prose was silently replaced with template text and counted as live-provider success. Narrative generation now rejects sparse/meta-contaminated prose, records fallback provenance, and permits one bounded quality rewrite.
8. Planning, narrative generation, and narrative support lacked explicit local model selection. Each service now passes its model override through the shared reasoning-runtime contract.

## Decision

The requested local-only real-book vertical slice is operational and accepted through retrieval-grounded narrative support. Analysis, canon, character/world modeling, planning, prose generation, semantic revision, and persistence all ran through the clean production architecture on real EPUB data. The final chapter contains no internal artifact IDs or generation metacommentary, and its remaining character descriptions are grounded in the accepted character profiles/stable states.

This qualification does not establish a structured contract for unnamed new participants. That capability should be designed explicitly in generation-planning contracts rather than inferred from free-form role phrases.
