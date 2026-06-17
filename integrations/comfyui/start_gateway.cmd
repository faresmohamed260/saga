@echo off
cd /d B:\Documents\PyCharm\graduationProject
for /f %%i in ('powershell -NoProfile -Command "if (Test-Path ''B:\Documents\PyCharm\graduationProject\integrations\comfyui\gateway-watchdog.lock'') { try { Get-Process -Id ([int](Get-Content ''B:\Documents\PyCharm\graduationProject\integrations\comfyui\gateway-watchdog.lock'' | Select-Object -First 1)) -ErrorAction Stop ^| Out-Null; Write-Output 1 } catch { Write-Output 0 } } else { Write-Output 0 }"') do set WATCHDOG_RUNNING=%%i
if "%WATCHDOG_RUNNING%"=="1" exit /b 0
start "" /min powershell.exe -NoProfile -ExecutionPolicy Bypass -File "B:\Documents\PyCharm\graduationProject\integrations\comfyui\gateway_watchdog.ps1"
