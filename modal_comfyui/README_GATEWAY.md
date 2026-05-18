# ComfyUI Domain Gateway

This gateway keeps `comfyui.faresuniform.uk` stable on your PC while the backend Modal workspace can rotate between teammate tokens.

## How it works

`Cloudflare Tunnel -> local gateway on 127.0.0.1:8031 -> active Modal ui URL`

The local gateway also serves:

- `/` as a chooser page for local vs cloud
- `/app` for whichever backend you selected
- `/status` for an HTML dashboard
- `/status.json` for machine-readable status

## What the dashboard shows

- active token/workspace
- latest known Modal UI URL
- token health
- month-to-date Modal spend per token
- estimated remaining free credit assuming `$30` per month per teammate
- warm-token preference state

## Local run

```powershell
venv\Scripts\python.exe modal_comfyui\run_gateway.py
```

Then open:

- `http://127.0.0.1:8031/`
- `http://127.0.0.1:8031/status`

## Windows service

After installing `pywin32`, you can register the gateway as a Windows service:

```powershell
venv\Scripts\python.exe modal_comfyui\gateway_service.py --startup auto install
venv\Scripts\python.exe modal_comfyui\gateway_service.py start
```

To remove it later:

```powershell
venv\Scripts\python.exe modal_comfyui\gateway_service.py stop
venv\Scripts\python.exe modal_comfyui\gateway_service.py remove
```

This requires an elevated PowerShell session.

## User-level auto start fallback

If you do not want to run as Administrator, use the included Scheduled Task installer:

```powershell
powershell -ExecutionPolicy Bypass -File modal_comfyui\install_gateway_task.ps1
```

Remove it with:

```powershell
powershell -ExecutionPolicy Bypass -File modal_comfyui\uninstall_gateway_task.ps1
```

If Scheduled Tasks are also blocked by policy on this PC, use the Startup-folder fallback:

```powershell
powershell -ExecutionPolicy Bypass -File modal_comfyui\install_gateway_startup.ps1
```

## Cloudflare tunnel

Point `comfyui.faresuniform.uk` at:

`http://127.0.0.1:8031`

The included config path in `gateway_config.json` is set to your existing tunnel config:

`B:\Documents\PyCharm\jarvis\infra\cloudflared\jarvis-phone.yml`
