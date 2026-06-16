$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$root = Split-Path -Parent $root
Set-Location $root

$python = Join-Path $root "venv\Scripts\python.exe"
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

$env:SAGA_DASHBOARD_NO_BROWSER = "1"
$env:SAGA_DASHBOARD_HOST = "127.0.0.1"
$env:SAGA_DASHBOARD_PORT = "8675"
$env:SAGA_DASHBOARD_LOG_LEVEL = "info"

$process = Start-Process `
    -FilePath $python `
    -ArgumentList "-m", "dashboard_runtime.app" `
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
