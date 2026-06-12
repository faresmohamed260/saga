![S.A.G.A. Logo](docs/assets/saga-logo.svg)

# S.A.G.A.

S.A.G.A. is a production-oriented narrative intelligence system for turning books into reusable canon memory.

The current system focuses on:

- ingesting EPUB and PDF books
- splitting chapters into analysis scenes
- extracting structured scene, event, entity, relationship, state, and visual-world data
- using `booknlp_clean` as the canonical identity source
- building contract artifacts for retrieval, downstream validation, and later generation workflows

## Current Product Surface

The main operator surface is now the local React dashboard in [dashboard_app](/B:/Documents/PyCharm/graduationProject/dashboard_app), served by the local runtime in [dashboard_runtime/app.py](/B:/Documents/PyCharm/graduationProject/dashboard_runtime/app.py).

Important repo surfaces:

- [saga_tools.py](/B:/Documents/PyCharm/graduationProject/saga_tools.py)
  Main CLI for encode, validation, retrieval, and utility workflows.
- [services/encoder_persistence_service.py](/B:/Documents/PyCharm/graduationProject/services/encoder_persistence_service.py)
  Production encoder path.
- [redesign_lab/identity/identity_provider.py](/B:/Documents/PyCharm/graduationProject/redesign_lab/identity/identity_provider.py)
  Production BookNLP-clean identity provider entrypoint.
- [query/visual_world_state_service.py](/B:/Documents/PyCharm/graduationProject/query/visual_world_state_service.py)
  Visual/world-state retrieval layer.
- [query/comfyui_prompt_pack_service.py](/B:/Documents/PyCharm/graduationProject/query/comfyui_prompt_pack_service.py)
  ComfyUI prompt-pack generation.

## Core Output Families

The encoder currently builds these main artifact families:

- `chapters`
- `scene_analyses`
- `resolved_scene_analyses`
- `entity_registry`
- `state_result`
- `canon_snapshot`
- `timeline`
- `event_ledger`
- `character_timelines`
- `character_profiles`
- `relationship_profiles`
- `stable_character_states`
- `story_index_summary`
- `visual_prompt_sets`

## Identity Strategy

The legacy custom resolver has been removed from the production path.

Current canonical identity source:

- `identity_provider = booknlp_clean`

Production identity flow:

1. generate or load per-book BookNLP-clean pipeline identity JSON
2. resolve provider-backed `characters`, `alias_index`, `narrator`, and `reference_entities`
3. inject provider-backed identity into the contract path
4. prevent scene-level inline identity from overwriting the provider stable roster

Main implementation files:

- [redesign_lab/identity/booknlp_identity_adapter.py](/B:/Documents/PyCharm/graduationProject/redesign_lab/identity/booknlp_identity_adapter.py)
- [redesign_lab/identity/identity_provider.py](/B:/Documents/PyCharm/graduationProject/redesign_lab/identity/identity_provider.py)
- [redesign_lab/identity/series_identity_provider.py](/B:/Documents/PyCharm/graduationProject/redesign_lab/identity/series_identity_provider.py)

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

- [analysis/visual_state_analyzer.py](/B:/Documents/PyCharm/graduationProject/analysis/visual_state_analyzer.py)
- [analysis/entity_world_state_analyzer.py](/B:/Documents/PyCharm/graduationProject/analysis/entity_world_state_analyzer.py)
- [query/visual_world_state_service.py](/B:/Documents/PyCharm/graduationProject/query/visual_world_state_service.py)
- [query/comfyui_prompt_pack_service.py](/B:/Documents/PyCharm/graduationProject/query/comfyui_prompt_pack_service.py)

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

## Common CLI Flow

Production encode runs go through `saga_tools.py`.

Example bounded encode:

```powershell
.\venv\Scripts\python.exe saga_tools.py encode-store ^
  --book "D:\Books\Example.epub" ^
  --series-id example-series ^
  --series-title "Example Series" ^
  --book-index-base 1 ^
  --analysis-model gpt_oss ^
  --identity-model gpt_oss ^
  --analysis-provider-mode same_provider_rotating ^
  --identity-provider booknlp_clean ^
  --identity-json "analysis_outputs\identity_series\example\book_01\booknlp_small_pipeline_identity.json" ^
  --scene-failure-policy fail_fast ^
  --skip-ingest
```

Example contract validation:

```powershell
.\venv\Scripts\python.exe saga_tools.py validate-encoder-artifacts ^
  --contract "analysis_outputs\encode_runs\...\contracts\01_book.contract.json" ^
  --identity-provider booknlp_clean ^
  --identity-json "analysis_outputs\identity_series\example\book_01\booknlp_small_pipeline_identity.json"
```

## Repository Layout

- [analysis](/B:/Documents/PyCharm/graduationProject/analysis)
  Scene analysis, evidence extraction, reconciliation, and visual-state extraction.
- [core](/B:/Documents/PyCharm/graduationProject/core)
  Contract rebuild, normalization, builders, and stable-state logic.
- [entities](/B:/Documents/PyCharm/graduationProject/entities)
  Entity registry and identity post-processing helpers.
- [infrastructure](/B:/Documents/PyCharm/graduationProject/infrastructure)
  Model/provider transport, credential stores, Neo4j ingestion.
- [query](/B:/Documents/PyCharm/graduationProject/query)
  Retrieval context, target states, visual world state, and prompt-pack services.
- [services](/B:/Documents/PyCharm/graduationProject/services)
  Production orchestration and persistence workflows.
- [dashboard_app](/B:/Documents/PyCharm/graduationProject/dashboard_app)
  React + Tailwind local dashboard frontend.
- [dashboard_runtime](/B:/Documents/PyCharm/graduationProject/dashboard_runtime)
  Local web runtime for serving the dashboard.
- [dashboard_api](/B:/Documents/PyCharm/graduationProject/dashboard_api)
  Local FastAPI backend used by some dashboard/runtime flows.
- [redesign_lab](/B:/Documents/PyCharm/graduationProject/redesign_lab)
  Identity, evaluation, and experimental pipeline support code.
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
