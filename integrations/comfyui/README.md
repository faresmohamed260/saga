# Modal ComfyUI Integration

This folder vendors a project-local Modal + ComfyUI setup with token rotation for your team credits.

## Versions pinned here

- `Modal` local/client version: `1.4.2`
- `ComfyUI` server version: `v0.19.3`
- Remote Python version: `3.11`
- Default checkpoint: `stable-diffusion-v1-5/stable-diffusion-v1-5` → `v1-5-pruned-emaonly.safetensors`
- Default GPU: `L4` for lower cost on the bundled SD1.5 workflow
- Idle scale-down window: `60` seconds by default

## What this gives you

- `modal_app.py`: a Modal app that launches ComfyUI on GPU and exposes:
  - a ComfyUI web UI via `modal serve` / `modal deploy`
  - an API-style render method
  - a local entrypoint that saves a PNG to disk
- `modal_tokens.example.json`: the format for your team token pool
- `pool_cli.py`: retries Modal commands across multiple tokens
- `health_check.py`: validates tokens with a cheap non-GPU Modal call
- `render_client.py`: a convenience client that rotates generation runs across teammate credits
- `stop_app.py`: a quick way to terminate a deployed ComfyUI app if you opened the UI and want billing to stop immediately

## 1. Add your team tokens

Copy `modal_tokens.example.json` to `modal_tokens.json`, then paste the token pairs:

```json
{
  "tokens": [
    {
      "name": "member-1",
      "token_id": "ak-...",
      "token_secret": "as-..."
    }
  ]
}
```

`modal_tokens.json` is ignored by git.

## 2. Install the local tools

From the project root:

```powershell
venv\Scripts\python.exe -m pip install modal==1.4.2
```

If you want the exact local setup I used while wiring this folder:

```powershell
venv\Scripts\python.exe -m pip install modal==1.4.2 comfy-cli==1.7.2
```

## 3. Run a generation with token failover

This is the easiest path for actual usage because it automatically rotates to the next token when one account fails:

```powershell
venv\Scripts\python.exe integrations\comfyui\render_client.py --prompt "cinematic fantasy city at sunset"
```

The PNG is written to `integrations/comfyui/outputs/render.png` by default.

This path is the most credit-friendly option because `modal run` creates an ephemeral app and tears it down after the job finishes.

It also prefers tokens with a recent successful render first, so if one teammate already paid the image-build cold start, future runs try that warmed workspace before cold ones.

## 4. Cheap token health check

This does not start a GPU workload. It only validates that selected tokens can talk to Modal:

```powershell
venv\Scripts\python.exe integrations\comfyui\health_check.py --limit 10
```

Use `--limit 0` to test the entire pool.

## 5. Run raw Modal commands through the token pool

Examples:

```powershell
venv\Scripts\python.exe integrations\comfyui\pool_cli.py -- venv\Scripts\modal.exe serve integrations\comfyui\modal_app.py
venv\Scripts\python.exe integrations\comfyui\pool_cli.py -- venv\Scripts\modal.exe deploy integrations\comfyui\modal_app.py
venv\Scripts\python.exe integrations\comfyui\pool_cli.py -- venv\Scripts\modal.exe run integrations\comfyui\modal_app.py --prompt "robot portrait"
```

If you want the raw command path to prefer warmed teammates too:

```powershell
venv\Scripts\python.exe integrations\comfyui\pool_cli.py --prefer-warm --mark-render-success -- venv\Scripts\modal.exe run integrations\comfyui\modal_app.py --prompt "robot portrait"
```

If you deploy or serve the UI, stop it when you are done:

```powershell
venv\Scripts\python.exe integrations\comfyui\pool_cli.py -- venv\Scripts\python.exe integrations\comfyui\stop_app.py --app-name graduation-comfyui
```

## Notes

- The failover logic is local/orchestrated. Modal Starter workspaces do not expose a simple remaining-credit API, so failover is triggered by command failures rather than a clean balance check.
- For deployed web endpoints, the token that performed the deployment owns the running app and gets billed. The best failover path for repeated experiments is `render_client.py`, because each generation request can rotate across tokens.
- The default workflow is based on ComfyUI's API example workflow. You can replace `workflow_api.json` with your own exported API workflow later.
- Successful renders mark the winning token as warm for 6 hours in `pool_state.json`, and the render client prefers those warm tokens first on later runs.
- You can override cost/performance defaults with env vars before running:
  - `MODAL_COMFYUI_GPU`
  - `MODAL_COMFYUI_IDLE_SECONDS`
  - `MODAL_COMFYUI_TIMEOUT_SECONDS`
