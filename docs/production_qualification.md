# Production Qualification

This document separates historical behavioral evidence from the current clean-source qualification contract. A successful run is promotable evidence only when it is bound to exact committed source, the required provider/storage configuration, complete usage pricing, and the repository-defined qualification checks.

## Historical Accepted Run — 2026-08-09

- Run: `qualification-heart-20260809a`
- Series: `qualification-heart-series-20260809a`
- Source: `Once Upon a Broken Heart.epub`
- Source SHA-256: `89f8e1a7dd808a8d40280608f5499f520fdf16aa01206f7a5f62afed9247b7a5`
- Release provenance: `release-0.1.0-staging.20260809-8aae86b8977b`
- Result: accepted with noncritical warnings
- Persisted report: `runtime-reports/providers/qualification-runtime/reports/production-qualification/d70c478ccbd1-qualification-heart-20260809a-production-qualification.json`

The run processed one previously unseen EPUB through analysis, Modal XCore LitBank identity resolution, canon extraction, character/world modeling, planning, narrative generation, semantic support, Modal image generation, Modal TTS, transcription QA, and EPUB/manifest packaging. All nine stage lineage records use `execution_mode=executed`.

### Evidence

- 1 book, 58 chapters, 107 scenes
- 179 evidence-supported identities
- 336 canon events, 718 entities, and 336 timeline rows with valid references
- 321-word generated chapter with accepted continuity and semantic support
- 3 accepted visual artifacts, all 512x512 and nonblank
- 123.64-second mono 24 kHz audiobook; maximum WER `0.0988`
- valid one-chapter EPUB and complete manifest
- 96 observability records, including provider and queue telemetry
- total recorded stage time: `1152.9948` seconds across the original run and bounded resumptions

### Resilience evidence

Real Supabase validation passed controlled queued cancellation, lease-expiry worker replacement, and retry after a transient provider failure. Cooperative cancellation stopped a live canon workload within 7.8 seconds. Test queues and the aborted Frost input were removed afterward.

### Historical warnings / limitations

- Creature and location were allowed visual types but had no grounded story-linked targets, so they were intentionally not rendered.
- Providers exposed request latency/status but not billable token or compute usage; estimated cost was unavailable for that run.
- Manual image review found moderate hand fidelity and scene-action alignment issues despite automated acceptance. These remain visual quality-policy evidence rather than blank/corrupt-output failures.
- **The run is not a promotable release baseline** because its source worktree was not a clean committed CI revision.

### Historical regression gates

- Backend: `243 passed, 3 skipped`
- Dashboard: `13 passed`; production Vite build succeeded
- Security-sensitive runtime suite: `60 passed`
- Dashboard production dependencies: `0` known vulnerabilities
- Exact supplied Hugging Face token scan: no exposure in the active source tree
- Release promotion: intentionally skipped because `574` worktree paths were pending

## Current Clean-Source Qualification Contract

The repository-owned entrypoint remains:

```text
python -m scripts.run_production_qualification
```

Phase 0 adds the manual GitHub Actions control plane:

```text
.github/workflows/production-qualification.yml
```

That workflow is deliberately `workflow_dispatch` only. It must never run on ordinary pushes or pull requests because it can use paid/live providers and a protected commercial book.

### Preconditions

Before any protected-book processing, the workflow must prove:

1. the operator explicitly sets `confirm_live_cost=true`;
2. checkout `HEAD` equals the workflow `GITHUB_SHA` and tracked source is clean;
3. frozen Python dependencies install successfully;
4. a production Supabase database/API/service-role configuration is available;
5. the production schema matches the current migration contract;
6. persisted Modal credentials exist for:
   - `modal_xcore_litbank`;
   - `modal_comfyui`;
   - `modal_kokoro_tts`;
7. persisted Ollama/gpt-oss reasoning configuration is available for the current default reasoning stages;
8. Mistral is configured either through persistence or `MISTRAL_API_KEY` for current Mistral reasoning/vision/transcription stages;
9. `SAGA_PROVIDER_COST_RATES_JSON` contains valid, versioned provider-wide fallback rates for `ollama`, `mistral`, and `modal`; more-specific model/account rates may override those fallbacks;
10. the selected protected asset is reachable from private R2 storage and its SHA-256 matches `docs/operations/protected_assets.manifest.json`.

The non-destructive readiness check is:

```text
python -m scripts.check_production_qualification_readiness
```

It reports only bounded configuration/provider readiness metadata. It does not print database credentials, provider secrets, provider payloads, or cost-rate values.

### Protected source handling

The workflow acquires exactly one manifest-selected protected EPUB through `scripts/check_protected_asset_storage.py`, verifies it through `scripts/verify_protected_assets.py`, keeps it only in runner temporary storage, and removes it in an `always()` cleanup step.

Protected EPUB bytes must never be committed or uploaded as a GitHub Actions artifact. The temporary local JSON qualification report is also removed after the run; the qualification evaluator persists the authoritative report through S.A.G.A.'s persistence/artifact contract.

Issue #142 tracks the current private-R2 availability prerequisite. A historical `HeadObject` 403 is not enough to distinguish wrong access/jurisdiction from a missing object; use the revised protected-asset diagnostic categories.

### Exact-source identity and bounded execution

For GitHub qualification, the release identity is derived from the exact checked-out commit:

```text
qualification-${GITHUB_SHA}
```

The workflow also creates unique run/series identifiers from the GitHub Actions run id/attempt. The production qualification command remains bounded by global and per-stage deadlines, maximum retries, and maximum visual attempts.

The workflow does **not** deploy or promote S.A.G.A. merely because qualification passes.

## Promotion Interpretation

A clean-source run may be used as promotable qualification evidence only when the evaluator accepts it and the persisted report is bound to the exact release/source identity.

In particular, the usage-cost check requires:

- at least one recorded charge;
- zero unpriced charges;
- complete reconciliation evidence.

A placeholder such as `SAGA_PROVIDER_COST_RATES_JSON=[]` therefore cannot qualify a release. Do not invent provider prices merely to satisfy the gate; configure versioned rates that correspond to the actual provider pricing/accounting policy.

## Reproduction

Preferred Phase-0 reproduction path:

1. resolve issue #142 and make the selected protected asset reachable/hash-valid;
2. configure the required Supabase/provider secrets and persisted provider rows;
3. configure the non-secret `SAGA_PROVIDER_COST_RATES_JSON` GitHub Actions variable with versioned provider-wide fallbacks for `ollama`, `mistral`, and `modal` plus any desired more-specific overrides;
4. manually dispatch **Clean-Source Production Qualification** on the exact `main` commit intended for qualification;
5. choose one protected `asset_id` and the correct R2 jurisdiction;
6. explicitly authorize live cost;
7. preserve the resulting persisted qualification evidence and update `PROJECT.md` / Phase 0 from the exact result.

For controlled local reproduction, run `python -m scripts.run_production_qualification` with the same production contracts, a verified unseen EPUB, an immutable release ID, and bounded global/stage deadlines. Use `--resume` only for checkpoints created by the same run and series.
