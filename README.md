![S.A.G.A. Logo](docs/assets/saga-logo.svg)

# S.A.G.A.

S.A.G.A. is a production-oriented narrative intelligence system for turning books into reusable canon memory.

The current system focuses on:

- ingesting EPUB and PDF books
- splitting chapters into analysis scenes
- extracting structured scene, event, entity, relationship, state, and visual-world data
- using `booknlp_clean` as the canonical identity source
- storing analysis state in the local SQLite database for retrieval, downstream validation, dashboard review, and later generation workflows

## Current Product Surface

The main operator surface is the local React dashboard in [apps/dashboard_web](/B:/Documents/PyCharm/graduationProject/apps/dashboard_web), served by the local runtime in [apps.dashboard_api/app.py](/B:/Documents/PyCharm/graduationProject/apps.dashboard_api/app.py).

Important repo surfaces:

- [saga_tools.py](/B:/Documents/PyCharm/graduationProject/saga_tools.py)
  Main CLI for encode, validation, retrieval, and utility workflows.
- [sql_store/persistence.py](/B:/Documents/PyCharm/graduationProject/sql_store/persistence.py)
  Local SQLite persistence layer for books, scenes, entities, events, visuals, and generated stories.
- [identity/identity_provider.py](/B:/Documents/PyCharm/graduationProject/identity/identity_provider.py)
  Production BookNLP-clean identity provider entrypoint.
- [query/visual_world_state_service.py](/B:/Documents/PyCharm/graduationProject/query/visual_world_state_service.py)
  Visual/world-state retrieval layer.
- [services/entity_visual_prompt_service.py](/B:/Documents/PyCharm/graduationProject/services/entity_visual_prompt_service.py)
  Database-backed visual prompt generation for saga.domain.entities.

## Core Data Families

The pipeline currently persists these main families in SQLite:

- `chapters`
- `scenes`
- `scene analyses`
- `entity_registry`
- `state_result`
- `timeline`
- `event_ledger`
- `character_timelines`
- `character_profiles`
- `relationship_profiles`
- `stable_character_states`
- `visual_prompts`
- `rendered_images`
- `generated_stories`

## Identity Strategy

The legacy custom resolver has been removed from the production path.

Current canonical identity source:

- `identity_provider = booknlp_clean`

Production identity flow:

1. generate or load per-book BookNLP-clean pipeline identity JSON
2. resolve provider-backed `characters`, `alias_index`, `narrator`, and `reference_entities`
3. inject provider-backed identity into the database-native analysis path
4. prevent scene-level inline identity from overwriting the provider stable roster

Main implementation files:

- [identity/booknlp_identity_adapter.py](/B:/Documents/PyCharm/graduationProject/identity/booknlp_identity_adapter.py)
- [identity/identity_provider.py](/B:/Documents/PyCharm/graduationProject/identity/identity_provider.py)
- [identity/series_identity_provider.py](/B:/Documents/PyCharm/graduationProject/identity/series_identity_provider.py)

## Provider Support

`LLMClient` supports multiple modes through [infrastructure/llm_client.py](/B:/Documents/PyCharm/graduationProject/infrastructure/llm_client.py):

- `deepseek`
- `gpt_oss`
- `codex`
- `general_compute`
- `mistral`
- `gemini`

Important current behavior:

- long canonical Ollama runs should use `analysis_provider_mode = same_provider_rotating`
- cross-provider fallback is non-canonical and should be treated as experimental
- Codex now supports a Hermes-backed device-session transport path in addition to direct API-key usage

Related files:

- [infrastructure/ollama_account_rotator.py](/B:/Documents/PyCharm/graduationProject/infrastructure/ollama_account_rotator.py)
- [infrastructure/general_compute_account_rotator.py](/B:/Documents/PyCharm/graduationProject/infrastructure/general_compute_account_rotator.py)
- [infrastructure/codex_session_store.py](/B:/Documents/PyCharm/graduationProject/infrastructure/codex_session_store.py)
- [infrastructure/openai_account_store.py](/B:/Documents/PyCharm/graduationProject/infrastructure/openai_account_store.py)

## Visual World State

The pipeline now includes dedicated visual-state extraction during analysis instead of relying only on post-hoc adapters.

Current visual/state-oriented components:

- [query/visual_world_state_service.py](/B:/Documents/PyCharm/graduationProject/query/visual_world_state_service.py)

These outputs are intended to support:

- character appearance baselines
- clothing and condition changes
- object and creature visual state
- location atmosphere and state
- scene-level visual prompt generation

## Running The System

## Installation

```powershell
python -m venv venv
venv\Scripts\activate
pip install -e .[dev]
```

Optional graph extras:

```powershell
pip install -e .[graph]
```

## Launch The Local Dashboard

Recommended Windows path:

```powershell
scripts\windows\run_dashboard.bat
```

That launcher:

1. installs dashboard dependencies if needed
2. builds the React dashboard
3. starts the local web runtime

Default local runtime URL:

- `http://127.0.0.1:8675`

Optional background-service path on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_saga_dashboard_service.ps1
```

That installs the local dashboard as the `SagaDashboard` Windows service using NSSM so the UI can stay available without an open terminal.

Fresh-clone local requirements:

- Python 3.10+
- Node.js + npm
- a virtual environment at `venv/`
- local provider/account files under `deploy/` as needed for your chosen model path

## Common CLI Flow

Production analysis and rendering runs now go through the DB-native agent pipeline and the local dashboard runtime.

## Repository Layout

- [analysis](/B:/Documents/PyCharm/graduationProject/analysis)
  DB-native scene analysis agents, evidence extraction, reconciliation, and visual-state extraction.
- [core](/B:/Documents/PyCharm/graduationProject/core)
  Normalization, builders, and stable-state logic.
- [entities](/B:/Documents/PyCharm/graduationProject/entities)
  Entity registry and identity post-processing helpers.
- [infrastructure](/B:/Documents/PyCharm/graduationProject/infrastructure)
  Model/provider transport, credential stores, Neo4j ingestion.
- [query](/B:/Documents/PyCharm/graduationProject/query)
  Retrieval context, indexing, target states, and visual world state saga.services.
- [services](/B:/Documents/PyCharm/graduationProject/services)
  Production orchestration, prompt generation, rendering, export, and persistence workflows.
- [apps/dashboard_web](/B:/Documents/PyCharm/graduationProject/apps/dashboard_web)
  React + Tailwind local dashboard frontend.
- [apps.dashboard_api](/B:/Documents/PyCharm/graduationProject/apps.dashboard_api)
  Local web runtime for serving the dashboard.
- [identity](/B:/Documents/PyCharm/graduationProject/identity)
  Minimal BookNLP identity support code retained by production.
- [docs](/B:/Documents/PyCharm/graduationProject/docs)
  Architecture and operator documentation.

## Credentials And Local-Only Files

Local credential files stay out of Git:

- `deploy/ollama/accounts.local.json`
- `deploy/general_compute/accounts.local.json`
- `deploy/openai/accounts.local.json`

Use the example templates:

- [deploy/general_compute/accounts.local.example.json](/B:/Documents/PyCharm/graduationProject/deploy/general_compute/accounts.local.example.json)
- [deploy/openai/accounts.local.example.json](/B:/Documents/PyCharm/graduationProject/deploy/openai/accounts.local.example.json)

Generated outputs are also local-only:

- `analysis_outputs/`

## Key Docs

- [docs/ARCHITECTURE.md](/B:/Documents/PyCharm/graduationProject/docs/ARCHITECTURE.md)
- [docs/DASHBOARD.md](/B:/Documents/PyCharm/graduationProject/docs/DASHBOARD.md)
- [docs/JSON_CONTRACT.md](/B:/Documents/PyCharm/graduationProject/docs/JSON_CONTRACT.md)
- [docs/NEO4J.md](/B:/Documents/PyCharm/graduationProject/docs/NEO4J.md)
- [docs/TARGET_SYSTEM.md](/B:/Documents/PyCharm/graduationProject/docs/TARGET_SYSTEM.md)
- [docs/TESTING.md](/B:/Documents/PyCharm/graduationProject/docs/TESTING.md)
