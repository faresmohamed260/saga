![S.A.G.A. Logo](docs/assets/saga-logo.svg)

# S.A.G.A.

S.A.G.A. is a local, database-backed narrative analysis and generation workspace for books. It ingests source novels, builds canonical structured memory, exposes the results through a dashboard, and supports visual and decoder workflows on top of the same stored data.

## Repository Status

The repository has been updated around the current production path:

- SQLite-backed canonical storage instead of filesystem-first contracts
- BookNLP-clean identity as the main identity source
- DB-native analysis agents for events, entities, profiles, timelines, states, and visuals
- React + FastAPI dashboard as the main operator surface
- database-backed visual prompt, render, and decoder story workflows

The earlier legacy/prototype architecture is documented for comparison, but the active repo direction is the current DB-native system.

## What Changed In The Repo

Recent structural changes reflected in this repo:

- the main application code is now centered under [saga](B:\Documents\PyCharm\graduationProject\saga)
- the dashboard frontend lives under [apps/dashboard_pro](B:\Documents\PyCharm\graduationProject\apps\dashboard_pro)
- the dashboard runtime/backend lives under [apps/dashboard_api](B:\Documents\PyCharm\graduationProject\apps\dashboard_api)
- persistence, identity, providers, analysis agents, visuals, and decoder code now operate against SQLite-backed storage
- legacy top-level clutter was reduced so the repo is organized around application package, apps, configs, deploy assets, scripts, tests, and docs

## Main Surfaces

### Dashboard

Primary operator UI:

- [apps/dashboard_pro](B:\Documents\PyCharm\graduationProject\apps\dashboard_pro)
- [apps/dashboard_api/app.py](B:\Documents\PyCharm\graduationProject\apps\dashboard_api\app.py)

Used for:

- staging books
- validating import plans
- starting analysis jobs
- inspecting scenes, entities, events, states, visuals, and providers
- launching decoder and rendering workflows

### Narraverse Website

Primary public website surface:

- [apps/narraverse_web](B:\Documents\PyCharm\graduationProject\apps\narraverse_web)
- [docs/narraverse_web.md](B:\Documents\PyCharm\graduationProject\docs\narraverse_web.md)

Hosted locally as the `NarraverseWebsite` Windows service on `127.0.0.1:8676` and exposed publicly at `https://narraverse.faresuniform.uk` through the same Cloudflare Tunnel pattern used for the other `faresuniform.uk` services.

### CLI

Primary CLI entrypoint:

- [saga_tools.py](B:\Documents\PyCharm\graduationProject\saga_tools.py)

Used for:

- targeted local runs
- utilities
- development workflows
- rendering and export tasks

### Application Package

Core package:

- [saga](B:\Documents\PyCharm\graduationProject\saga)

Contains:

- agents
- identity pipeline
- provider infrastructure
- storage and persistence
- services
- retrieval/query logic
- decoder support
- visual generation support

## Repository Layout

- [apps](B:\Documents\PyCharm\graduationProject\apps)
  Frontend and backend application surfaces.
- [configs](B:\Documents\PyCharm\graduationProject\configs)
  Configuration assets.
- [deploy](B:\Documents\PyCharm\graduationProject\deploy)
  Local deployment and provider-account assets.
- [docs](B:\Documents\PyCharm\graduationProject\docs)
  Architecture, schema, dashboard, and testing documentation.
- [integrations](B:\Documents\PyCharm\graduationProject\integrations)
  Integration-specific helpers.
- [saga](B:\Documents\PyCharm\graduationProject\saga)
  Main application code.
- [scripts](B:\Documents\PyCharm\graduationProject\scripts)
  Local scripts and Windows launch/install helpers.
- [tests](B:\Documents\PyCharm\graduationProject\tests)
  Automated tests.

## Installation

```powershell
python -m venv venv
venv\Scripts\activate
pip install -e .[dev]
```

Optional extras:

```powershell
pip install -e .[graph]
```

Frontend dependencies:

```powershell
npm install
cd apps\dashboard_pro
npm install
```

## Run The Dashboard

Recommended local launcher:

```powershell
scripts\windows\run_dashboard.bat
```

Default local URL:

- `http://127.0.0.1:8675`

Background Windows service install:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_saga_dashboard_service.ps1
```

## Current Runtime Stack

- frontend: React
- backend/runtime: FastAPI
- storage: SQLite
- identity: BookNLP-clean pipeline
- generation/render orchestration: local services + provider integrations

## Key Current Components

### Storage

- [saga/storage/models.py](B:\Documents\PyCharm\graduationProject\saga\storage\models.py)
- [saga/storage/persistence.py](B:\Documents\PyCharm\graduationProject\saga\storage\persistence.py)

### Identity

- [saga/identity/booknlp_identity_adapter.py](B:\Documents\PyCharm\graduationProject\saga\identity\booknlp_identity_adapter.py)
- [saga/identity/series_identity_provider.py](B:\Documents\PyCharm\graduationProject\saga\identity\series_identity_provider.py)

### Analysis

- [saga/services/database_analysis_run_service.py](B:\Documents\PyCharm\graduationProject\saga\services\database_analysis_run_service.py)
- [saga/agents](B:\Documents\PyCharm\graduationProject\saga\agents)

### Decoder

- [saga/services/database_decoder_service.py](B:\Documents\PyCharm\graduationProject\saga\services\database_decoder_service.py)
- [saga/services/generated_story_epub_service.py](B:\Documents\PyCharm\graduationProject\saga\services\generated_story_epub_service.py)

### Visuals

- [saga/services/entity_visual_prompt_service.py](B:\Documents\PyCharm\graduationProject\saga\services\entity_visual_prompt_service.py)
- [saga/services/comfyui_character_sheet_service.py](B:\Documents\PyCharm\graduationProject\saga\services\comfyui_character_sheet_service.py)

## Documentation

Top-level methodology / implementation comparison:

- [SYSTEM_METHODOLOGY_AND_IMPLEMENTATION.md](B:\Documents\PyCharm\graduationProject\SYSTEM_METHODOLOGY_AND_IMPLEMENTATION.md)

Additional docs:

- [docs/ARCHITECTURE.md](B:\Documents\PyCharm\graduationProject\docs\ARCHITECTURE.md)
- [docs/AGENT_PIPELINE_DATAFLOW.md](B:\Documents\PyCharm\graduationProject\docs\AGENT_PIPELINE_DATAFLOW.md)
- [docs/DASHBOARD.md](B:\Documents\PyCharm\graduationProject\docs\DASHBOARD.md)
- [docs/SQLITE_SCHEMA.md](B:\Documents\PyCharm\graduationProject\docs\SQLITE_SCHEMA.md)
- [docs/TARGET_SYSTEM.md](B:\Documents\PyCharm\graduationProject\docs\TARGET_SYSTEM.md)
- [docs/TESTING.md](B:\Documents\PyCharm\graduationProject\docs\TESTING.md)

## Local-Only Data

The following remain local and are not intended for Git tracking:

- `analysis_outputs/`
- local database files
- local provider account files
- rendered images and generated EPUB exports

## Notes

- The dashboard/runtime path is the main operational path.
- The current repo is organized around the DB-native system, not the earlier contract-first prototype.
- Methodology and implementation comparison is intentionally kept in the separate top-level document so the README can stay repository-focused.
