$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$root = Split-Path -Parent $root
Set-Location $root

$startupDir = [Environment]::GetFolderPath("Startup")
$launcherPath = Join-Path $startupDir "SagaDashboardLauncher.vbs"
$startScript = Join-Path $root "scripts\windows\start_saga_dashboard_background.ps1"

$vbs = @"
Set shell = CreateObject("WScript.Shell")
shell.Run "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File ""$startScript""", 0, False
"@

Set-Content -Path $launcherPath -Value $vbs -Encoding ASCII

Write-Host "Installed startup launcher: $launcherPath" -ForegroundColor Green
