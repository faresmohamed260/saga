$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$root = Split-Path -Parent $root
Set-Location $root

$nssm = "C:\tools\NSSM\nssm.exe"
if (-not (Test-Path $nssm)) {
    throw "NSSM was not found at $nssm"
}

$serviceName = "SagaDashboard"
$serviceDisplayName = "SAGA Dashboard"
$python = Join-Path $root "venv\Scripts\python.exe"
$logsDir = Join-Path $root "analysis_outputs\dashboard\logs"
$stdoutLog = Join-Path $logsDir "saga-dashboard.out.log"
$stderrLog = Join-Path $logsDir "saga-dashboard.err.log"

New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

if (-not (Test-Path $python)) {
    throw "Python runtime was not found at $python"
}

try {
    & $nssm status $serviceName | Out-Null
    $serviceExists = $true
} catch {
    $serviceExists = $false
}

if (-not $serviceExists) {
    & $nssm install $serviceName $python | Out-Null
}

& $nssm set $serviceName Application $python | Out-Null
& $nssm set $serviceName AppParameters "-m dashboard_runtime.app" | Out-Null
& $nssm set $serviceName AppDirectory $root | Out-Null
& $nssm set $serviceName DisplayName $serviceDisplayName | Out-Null
& $nssm set $serviceName Description "SAGA local dashboard runtime hosted in the background." | Out-Null
& $nssm set $serviceName Start SERVICE_AUTO_START | Out-Null
& $nssm set $serviceName AppStdout $stdoutLog | Out-Null
& $nssm set $serviceName AppStderr $stderrLog | Out-Null
& $nssm set $serviceName AppRotateFiles 1 | Out-Null
& $nssm set $serviceName AppRotateOnline 1 | Out-Null
& $nssm set $serviceName AppRotateBytes 1048576 | Out-Null
& $nssm set $serviceName AppStopMethodSkip 6 | Out-Null
& $nssm set $serviceName AppEnvironmentExtra "SAGA_DASHBOARD_NO_BROWSER=1" "SAGA_DASHBOARD_HOST=127.0.0.1" "SAGA_DASHBOARD_PORT=8675" "SAGA_DASHBOARD_LOG_LEVEL=info" | Out-Null

Start-Service $serviceName
Start-Sleep -Seconds 3

$status = Get-Service $serviceName
Write-Host "Installed and started $serviceDisplayName ($($status.Status))." -ForegroundColor Green
Write-Host "Local origin: http://127.0.0.1:8675"
