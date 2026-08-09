# S.A.G.A. Dashboard Pro

`apps/dashboard_pro` is the active modular React dashboard for S.A.G.A. It is the only active dashboard frontend in the repo.

## Frontend Structure

- `src/app`: top-level routing and shell composition.
- `src/features`: route-owned page modules and feature-specific state helpers.
- `src/components/*`: concrete reusable UI modules grouped by domain, not compatibility barrels.
- `src/components/primitives`: shared UI primitives.
- `src/hooks`: runtime context, polling, and async helpers.

The intended import direction is `app/features -> concrete component modules -> primitives/hooks/api`. Thin root-level re-export wrappers are intentionally avoided so the repo has one obvious source for each UI module.

## Current Capabilities

- Routed pages for Overview, Import, Runs, Library, Analysis, Visual Assets, Decoder, Providers, and Diagnostics.
- Runtime-backed reads for jobs, books, analysis sections, provider health, generated stories, visual assets, uploads, and prompt metadata.
- Import staging and validation are implemented against unified persistence runtime source-document records.
- Starting a validated import plan delegates to the backend runtime orchestration layer, not an embedded API-only pipeline.
- Import jobs can run deterministic ingest/split only, or the full DB-agent stage list when `shared_config.run_agents=true`.
- Decoder plan validation and decoder job start are wired to the existing decoder runtime.
- Visual prompt versioning, batch render start, and exact single-entity render handoff are wired to existing visual runtime paths.
- Single-entity render passes the selected canonical entity id and prompt data through runtime-backed provider flows.
- Job controls are intentionally conservative: unsupported pause/resume controls are hidden in the UI, and unsupported backend actions return explicit `409` errors instead of pretending to work.

## Deployment

Build:

```powershell
npm --prefix apps\dashboard_pro install
npm --prefix apps\dashboard_pro run build
```

Restart the persistent service from an elevated PowerShell:

```powershell
Restart-Service SagaDashboard
```

If the service manager cannot stop the stale Python process from a normal shell, rerun the installer script from elevated PowerShell:

```powershell
Set-Location "B:\Documents\PyCharm\graduationProject"
powershell -ExecutionPolicy Bypass -File ".\scripts\windows\install_saga_dashboard_service.ps1"
Restart-Service SagaDashboard
```

Verify:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8675/runtime/state
Invoke-WebRequest -UseBasicParsing https://saga.faresuniform.uk
```

## Known Limitations

- Pause/resume from a durable checkpoint is not yet advertised in the UI. Current safe lifecycle actions are cancel at implemented safe boundaries and retry for failed/cancelled DB-native analysis jobs.
- Full DB-agent execution uses real provider calls and should be started deliberately. Automated tests use `run_agents=false` with temporary SQLite databases to avoid mutating production data or burning provider budget.
- The current production Windows service may require elevated permissions to stop/restart because it runs as a service-owned Python process.
