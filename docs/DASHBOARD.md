# S.A.G.A. Dashboard Guide

## Current Dashboard Surface

The current local dashboard stack is:

- frontend: [apps/dashboard_web](/B:/Documents/PyCharm/graduationProject/apps/dashboard_web)
- runtime: [apps.dashboard_api/app.py](/B:/Documents/PyCharm/graduationProject/apps.dashboard_api/app.py)

## Recommended Launch Path

Windows:

```powershell
scripts\windows\run_dashboard.bat
```

This launcher:

1. installs frontend dependencies if needed
2. builds the React dashboard
3. starts the local runtime

Default local URL:

- `http://127.0.0.1:8675`

## Purpose

The dashboard is intended to help with:

- browsing encode runs and database-backed analyses
- validating persisted analysis data
- inspecting identity artifacts
- reviewing character states
- reviewing visual world state
- reviewing visual prompts and rendered outputs
- inspecting retrieval context
- inspecting Neo4j-backed outputs where configured

## Main Views

Typical main tabs or sections include:

- `Overview`
- `Encode Runs`
- `Analysis`
- `Prompt Inspector`
- `Retrieval Context`
- `Providers`
- `Reports`

Exact tab composition may vary as the frontend evolves.

## Analysis

The analysis view is meant to render structured sections from the SQLite store instead of raw JSON-first inspection.

Main sections include:

- scenes
- events
- entities
- timeline
- relationships
- states
- identity
- visuals

## Visual World State

The visual world state view is intended to surface structured cards for:

- character visual baselines
- clothing and condition changes
- object and creature state
- location atmosphere and physical state
- target-aware later-state inspection

Main supporting service:

- [query/visual_world_state_service.py](/B:/Documents/PyCharm/graduationProject/query/visual_world_state_service.py)

## Prompt And Visual Export Support

The dashboard can inspect or generate database-backed visual prompts via:

- [services/entity_visual_prompt_service.py](/B:/Documents/PyCharm/graduationProject/services/entity_visual_prompt_service.py)
- [services/comfyui_character_sheet_service.py](/B:/Documents/PyCharm/graduationProject/services/comfyui_character_sheet_service.py)

This is intended for:

- character sheets
- location concept prompts
- object/artifact prompts
- scene prompts
- curated prompt exports

## Run Inspection

The dashboard is also meant to help inspect:

- run status
- per-book progress
- persisted analysis presence
- scene counts
- failure reports
- validation outputs

## Notes

- the dashboard reads its core analysis content from SQLite
- some exported files still live in `analysis_outputs/`
- the dashboard is a local operator tool, not a hosted multi-user service
- the supported dashboard surface is the local React app plus the local Python runtime
