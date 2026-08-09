# Production Qualification

## Accepted Run

- Run: `qualification-heart-20260809a`
- Series: `qualification-heart-series-20260809a`
- Source: `Once Upon a Broken Heart.epub`
- Source SHA-256: `89f8e1a7dd808a8d40280608f5499f520fdf16aa01206f7a5f62afed9247b7a5`
- Release provenance: `release-0.1.0-staging.20260809-8aae86b8977b`
- Result: accepted with noncritical warnings
- Persisted report: `runtime-reports/providers/qualification-runtime/reports/production-qualification/d70c478ccbd1-qualification-heart-20260809a-production-qualification.json`

The run processed one previously unseen EPUB through analysis, Modal XCore LitBank identity resolution, canon extraction, character/world modeling, planning, narrative generation, semantic support, Modal image generation, Modal TTS, transcription QA, and EPUB/manifest packaging. All nine stage lineage records use `execution_mode=executed`.

## Evidence

- 1 book, 58 chapters, 107 scenes
- 179 evidence-supported identities
- 336 canon events, 718 entities, and 336 timeline rows with valid references
- 321-word generated chapter with accepted continuity and semantic support
- 3 accepted visual artifacts, all 512x512 and nonblank
- 123.64-second mono 24 kHz audiobook; maximum WER `0.0988`
- valid one-chapter EPUB and complete manifest
- 96 observability records, including provider and queue telemetry
- total recorded stage time: `1152.9948` seconds across the original run and bounded resumptions

## Resilience

Real Supabase validation passed controlled queued cancellation, lease-expiry worker replacement, and retry after a transient provider failure. Cooperative cancellation stopped a live canon workload within 7.8 seconds. Test queues and the aborted Frost input were removed afterward.

## Warnings

- Creature and location were allowed visual types but had no grounded story-linked targets, so they were intentionally not rendered.
- Providers exposed request latency/status but not billable token or compute usage; estimated cost remains unavailable.
- Manual image review found moderate hand fidelity and scene-action alignment issues despite automated acceptance. These are tracked as visual quality-policy hardening, not blank/corrupt output.
- This is not a promotable release because the source worktree is not a clean committed CI revision.

## Regression Gates

- Backend: `243 passed, 3 skipped`
- Dashboard: `13 passed`; production Vite build succeeded
- Security-sensitive runtime suite: `60 passed`
- Dashboard production dependencies: `0` known vulnerabilities
- Exact supplied Hugging Face token scan: no exposure in the active source tree
- Release promotion: intentionally skipped because `574` worktree paths are pending; the staging provenance is retained but is not production-promotable

## Reproduction

Run `python -m scripts.run_production_qualification` with the production Supabase environment, an unseen EPUB, an immutable release ID, and bounded global/stage deadlines. Use `--resume` only for checkpoints created by the same run and series.
