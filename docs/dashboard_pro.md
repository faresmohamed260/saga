# S.A.G.A. Dashboard Pro

`apps/dashboard_pro` is the active modular React dashboard for S.A.G.A. It is the only dashboard frontend served by `apps.dashboard_api.app`.

## Current Capabilities

- Routed pages for Overview, Import, Runs, Library, Analysis, Visual Assets, Decoder, Providers, and Diagnostics.
- Public Landing, Sign In, and Sign Up routes are available at `/`, `/signin`, and `/signup`.
- Sign Up and Sign In call FastAPI auth endpoints under `/api/auth/*`; account records are stored in MongoDB.
- Database-backed runtime reads for jobs, books, analysis sections, provider health, generated stories, visual assets, uploads, and prompt metadata.
- Import staging and validation are implemented against SQLite uploaded-source records.
- Starting a validated import plan delegates to `saga.services.database_analysis_run_service.DatabaseAnalysisRunService`, not an embedded API-only pipeline.
- Import jobs can run deterministic ingest/split only, or the full DB-agent stage list when `shared_config.run_agents=true`.
- Decoder plan validation and decoder job start are wired to the existing decoder runtime.
- Visual prompt versioning, batch render start, and exact single-entity render handoff are wired to existing visual runtime paths.
- Single-entity render passes both the selected SQLite entity id and optional prompt id through the API, CLI, manifest builder, and ComfyUI render service.
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

MongoDB auth configuration:

```powershell
$env:SAGA_MONGODB_URI="mongodb://127.0.0.1:27017"
$env:SAGA_MONGODB_DATABASE="saga"
$env:SAGA_MONGODB_USERS_COLLECTION="users"
```

`SAGA_MONGODB_URI` can also be supplied as `MONGODB_URI`. The auth endpoints create a unique email index on the users collection before inserting a new signup record.

## Known Limitations

- Pause/resume from a durable checkpoint is not yet advertised in the UI. Current safe lifecycle actions are cancel at implemented safe boundaries and retry for failed/cancelled DB-native analysis jobs.
- Full DB-agent execution uses real provider calls and should be started deliberately. Automated tests use `run_agents=false` with temporary SQLite databases to avoid mutating production data or burning provider budget.
- The current production Windows service may require elevated permissions to stop/restart because it runs as a service-owned Python process.
