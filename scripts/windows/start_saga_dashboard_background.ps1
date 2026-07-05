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
if (-not $env:SAGA_MONGODB_URI -and -not $env:MONGODB_URI) {
    $env:SAGA_MONGODB_URI = "mongodb://127.0.0.1:27017"
}
if (-not $env:SAGA_MONGODB_DATABASE) {
    $env:SAGA_MONGODB_DATABASE = "saga"
}
if (-not $env:SAGA_MONGODB_USERS_COLLECTION) {
    $env:SAGA_MONGODB_USERS_COLLECTION = "users"
}

$listeners = Get-NetTCPConnection -LocalPort ([int]$env:SAGA_DASHBOARD_PORT) -State Listen -ErrorAction SilentlyContinue
foreach ($listener in $listeners) {
    if ($listener.OwningProcess -gt 0) {
        Stop-Process -Id $listener.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}
if ($listeners) {
    Start-Sleep -Seconds 1
}

$process = Start-Process `
    -FilePath $python `
    -ArgumentList "-m", "apps.dashboard_api.app" `
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
