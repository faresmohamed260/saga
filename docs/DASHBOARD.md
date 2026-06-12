# S.A.G.A. Dashboard Guide

## Current Dashboard Surface

The current local dashboard stack is:

- frontend: [dashboard_app](/B:/Documents/PyCharm/graduationProject/dashboard_app)
- runtime: [dashboard_runtime/app.py](/B:/Documents/PyCharm/graduationProject/dashboard_runtime/app.py)
- optional local API/backend helpers: [dashboard_api/app.py](/B:/Documents/PyCharm/graduationProject/dashboard_api/app.py)

The older Streamlit dashboard in [story_dashboard.py](/B:/Documents/PyCharm/graduationProject/story_dashboard.py) still exists, but it is no longer the only UI surface in the repo.

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

- browsing encode runs and contracts
- validating contract artifacts
- inspecting identity artifacts
- reviewing character states
- reviewing visual world state
- reviewing ComfyUI prompt packs
- inspecting retrieval context
- inspecting Neo4j-backed outputs where configured

## Main Views

Typical main tabs or sections include:

- `Overview`
- `Encode Runs`
- `Contract Viewer`
- `Identity Viewer`
- `Character States`
- `Visual World State`
- `ComfyUI Prompts`
- `Retrieval Context`
- `Neo4j`
- `Prompt Inspector`
- `Providers`
- `Reports`

Exact tab composition may vary as the frontend evolves.

## Contract Viewer

The contract viewer is meant to render structured sections instead of raw JSON-first inspection.

Main contract-oriented sections include:

- scenes
- events
- entities
- timeline
- profiles
- relationships
- states
- identity

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

The dashboard can inspect or generate ComfyUI prompt-pack artifacts via:

- [query/comfyui_prompt_pack_service.py](/B:/Documents/PyCharm/graduationProject/query/comfyui_prompt_pack_service.py)

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
- contract presence
- scene counts
- failure reports
- validation outputs

The main artifact discovery logic lives in:

- [services/dashboard_artifact_service.py](/B:/Documents/PyCharm/graduationProject/services/dashboard_artifact_service.py)

## Notes

- generated artifacts still live in `analysis_outputs/`
- the dashboard is a local operator tool, not a hosted multi-user service
- some backend-assisted dashboard paths still exist in the repo, but the runtime remains local-first
