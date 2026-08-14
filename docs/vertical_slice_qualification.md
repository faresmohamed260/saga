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

## First canon checkpoint

Run `vertical-slice-canon2-20260814b` used `ollama_local` with `mistral:7b-instruct`, one inference worker, a 45-second request deadline, and a 240-second stage deadline. It persisted 10 of 50 chapter-canon jobs before cancellation at the declared deadline. The model was then explicitly unloaded.

An isolated first-chapter request used 7,630 input tokens and 841 output tokens, completed in 23.0 seconds at 45.2 output tokens/second, and returned schema-valid events, entities, and relationships with no fallback. The unchanged full canon stage is therefore functional but projects to roughly 20 minutes on this workstation.

## Diagnosed defects

1. Partial-stage qualification incorrectly invoked the full-deliverable evaluator and demanded a generated story. The CLI now persists a stage-slice report instead.
2. Analysis-only qualification invoked an unrelated cloud generation-planning preflight. Preflights are now stage-aware.
3. Canon request budgeting hardcoded provider `mistral`; local requests were rejected before inference. The budget now follows the configured runtime provider.
4. Canon errors discarded the provider `last_error`. Failure messages now retain it.

## Current decision

The analysis foundation is operational on real book data. Canon extraction is operational and checkpointed but is not yet fast enough for an efficient development loop. Planning and chapter generation have not been reached. The next bounded action should improve canon throughput without weakening evidence validation or exceeding workstation resource limits, then resume from the 10 persisted chapter jobs.
