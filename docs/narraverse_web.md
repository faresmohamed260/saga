# Narraverse Website

`apps/narraverse_web` is the public-facing Narraverse website copied from the external Narraverse repo and hosted inside this repository as a dedicated Next.js service.

## Local Development

```powershell
npm --prefix apps\narraverse_web install
npm --prefix apps\narraverse_web run dev
```

## Production Build

```powershell
npm --prefix apps\narraverse_web install
npm --prefix apps\narraverse_web run build
```

## Windows Service Deployment

Install or refresh the background service from an elevated PowerShell:

```powershell
Set-Location "B:\Documents\PyCharm\graduationProject"
powershell -ExecutionPolicy Bypass -File ".\scripts\windows\install_narraverse_service.ps1"
```

Restart it later with:

```powershell
Restart-Service NarraverseWebsite
```

Check service status with:

```powershell
Get-Service NarraverseWebsite
```

The service is intended to be the normal persistent hosting path. The fallback scripts below are recovery options only if an elevated install is not available.

If the machine does not allow service creation from your current shell, use the non-admin background task fallback:

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\windows\install_narraverse_background_task.ps1"
```

If scheduled task registration is also blocked, install the Startup-folder launcher:

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\windows\install_narraverse_startup_launcher.ps1"
```

## Hosting

`narraverse.faresuniform.uk` should map through the same Cloudflare Tunnel as the rest of the `faresuniform.uk` services. Refresh the managed ingress rules with:

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\windows\sync_faresuniform_tunnel_config.ps1"
```

## Verify

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8676
Invoke-WebRequest -UseBasicParsing https://narraverse.faresuniform.uk
Get-Service NarraverseWebsite
```
