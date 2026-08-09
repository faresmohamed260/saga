![S.A.G.A. Logo](docs/assets/saga-logo.svg)

# S.A.G.A.

[![Dashboard Pro CI](https://github.com/faresmohamed260/saga/actions/workflows/dashboard-pro-ci.yml/badge.svg?branch=main)](https://github.com/faresmohamed260/saga/actions/workflows/dashboard-pro-ci.yml)

S.A.G.A. is a narrative analysis and generation workspace for books. It ingests source novels, builds canonical structured memory, exposes the results through a dashboard, and supports visual, retrieval, decoder, and audiobook workflows on top of a unified runtime-backed persistence layer.

## Repository Status

The repository is being rebuilt around the current production path:

- unified persistence/storage runtime instead of filesystem-first contracts
- Supabase/Postgres + object storage as the active persistence provider path
- runtime-native analysis agents for events, entities, profiles, timelines, states, and visuals
- React + FastAPI dashboard as the main operator surface
- independently deployable API, worker, scheduler, and observability roles
- Alembic-owned PostgreSQL migrations and provider-neutral database/artifact recovery
- runtime-backed visual prompt, render, and decoder story workflows

The earlier legacy/prototype architecture is being isolated out of the active tree. The target direction is the unified runtime architecture described in `docs/storage_architecture.md`.

Production build, rollout, rollback, health, and disaster-recovery procedures are documented in `docs/deployment_operations.md`.

## What Changed In The Repo

Recent structural changes reflected in this repo:

- the main application code is now centered under [saga](B:\Documents\PyCharm\graduationProject\saga)
- the dashboard frontend lives under [apps/dashboard_pro](B:\Documents\PyCharm\graduationProject\apps\dashboard_pro)
- the dashboard runtime/backend lives under [apps/dashboard_api](B:\Documents\PyCharm\graduationProject\apps\dashboard_api)
- persistence, identity, providers, analysis agents, visuals, and decoder code are being cut over to the unified runtime
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

## GitHub Workflow

Dashboard Pro frontend work now follows a GitHub PR flow:

- code ownership is defined in [.github/CODEOWNERS](B:\Documents\PyCharm\graduationProject\.github\CODEOWNERS)
- pull requests use [.github/pull_request_template.md](B:\Documents\PyCharm\graduationProject\.github\pull_request_template.md)
- frontend tasks can be opened from [.github/ISSUE_TEMPLATE/dashboard-pro-task.yml](B:\Documents\PyCharm\graduationProject\.github\ISSUE_TEMPLATE\dashboard-pro-task.yml)
- CI for Dashboard Pro runs from [.github/workflows/dashboard-pro-ci.yml](B:\Documents\PyCharm\graduationProject\.github\workflows\dashboard-pro-ci.yml)
- contributor guidance lives in [CONTRIBUTING.md](B:\Documents\PyCharm\graduationProject\CONTRIBUTING.md)

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
- storage abstraction: `packages/persistence_runtime`
- active provider path: Supabase Postgres + pgvector + Supabase Storage
- generation/render orchestration: decoupled provider runtimes + dashboard/runtime surfaces

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

Local temp/cache data is not source-of-truth persistence. Durable artifacts belong in the unified runtime object storage path.

## Notes

- The dashboard/runtime path is the main operational path.
- The active storage architecture is the unified persistence runtime. Supabase is a provider, not the abstraction.
- Methodology and implementation comparison is intentionally kept in the separate top-level document so the README can stay repository-focused.
