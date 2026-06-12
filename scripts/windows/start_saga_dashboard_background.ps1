$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$root = Split-Path -Parent $root
Set-Location $root

$runner = Join-Path $root "scripts\windows\run_saga_dashboard_service.cmd"
$logsDir = Join-Path $root "analysis_outputs\dashboard\logs"
$pidFile = Join-Path $logsDir "saga-dashboard.pid"

New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

if (Test-Path $pidFile) {
    $oldPid = Get-Content $pidFile | Select-Object -First 1
    if ($oldPid) {
        Stop-Process -Id ([int]$oldPid) -Force -ErrorAction SilentlyContinue
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

$process = Start-Process `
    -FilePath $runner `
    -WorkingDirectory $root `
    -WindowStyle Hidden `
    -PassThru

$process.Id | Set-Content -Path $pidFile -Encoding ASCII

$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8675/runtime/state" -TimeoutSec 5
        if ($response.StatusCode -eq 200) {
            $ready = $true
            break
        }
    } catch {}
}

if (-not $ready) {
    throw "SAGA dashboard did not become ready on http://127.0.0.1:8675"
}

Write-Host "SAGA dashboard started in the background." -ForegroundColor Green
Write-Host "Local origin: http://127.0.0.1:8675"
