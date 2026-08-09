# Modal ComfyUI Integration

This folder vendors a project-local Modal + ComfyUI setup behind the DB-backed inference provider layer.

## Versions pinned here

- `Modal` local/client version: `1.4.2`
- `ComfyUI` server version: `v0.19.3`
- Remote Python version: `3.11`
- Default workflow model set: `Comfy-Org/z_image_turbo` + `alibaba-pai/Z-Image-Turbo-Fun-Controlnet-Union`
- Default GPU: `A10` unless overridden by `MODAL_COMFYUI_GPU`
- Idle scale-down window: `600` seconds by default

## What this gives you

- `modal_app.py`: a Modal app that launches ComfyUI on GPU and exposes:
  - a direct web render endpoint
  - a cheap control-plane health endpoint
  - a local debug entrypoint that prints response metadata without creating durable local artifacts
- active workflows are stored at runtime in the shared Modal volume under `/cache/workflows`
- provider config/runtime state is stored in the unified persistence runtime
- `scripts/validate_real_supabase_runtime.py`: validate the unified persistence runtime against the live Supabase deployment
- `scripts/validate_real_runtime_stack.py`: validate the active clean runtime stack end to end against live services

## 1. Add your Modal accounts

Add Modal account entries through the runtime inference-provider config surface. The runtime no longer reads token files from this folder.

## 2. Install the local tools

From the project root:

```powershell
venv\Scripts\python.exe -m pip install modal==1.4.2
```

If you want the exact local setup I used while wiring this folder:

```powershell
venv\Scripts\python.exe -m pip install modal==1.4.2 comfy-cli==1.7.2
```

## 3. Run the live runtime validators

```powershell
venv\Scripts\python.exe scripts\validate_real_supabase_runtime.py
venv\Scripts\python.exe scripts\validate_real_runtime_stack.py
```

## Notes

- The failover logic is still local/orchestrated inside the Modal provider adapter. Modal Starter workspaces do not expose a simple remaining-credit API, so failover is triggered by command failures rather than a clean balance check.
- Deployed web endpoints are still billed to whichever Modal account owns the active app.
- The active render modes are `character_sheet` and `entity_generation`. The Modal runtime executes exported ComfyUI workflow JSONs behind the shared provider abstraction.
- Workflow JSONs are bundled into the active runtime image in the current tree. If workflow delivery is split back into a separate control-plane sync surface later, document that new active path here rather than referencing removed scripts.
- Local endpoint routing state is generation-validated in unified persistence; rollouts invalidate stale provider runtime state automatically.
- You can override cost/performance defaults with env vars before running:
  - `MODAL_COMFYUI_GPU`
  - `MODAL_COMFYUI_IDLE_SECONDS`
  - `MODAL_COMFYUI_TIMEOUT_SECONDS`
