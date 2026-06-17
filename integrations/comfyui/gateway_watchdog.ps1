$ErrorActionPreference = "Stop"

$projectRoot = "B:\Documents\PyCharm\graduationProject"
$pythonExe = Join-Path $projectRoot "venv\Scripts\python.exe"
$gatewayScript = Join-Path $projectRoot "integrations\comfyui\run_gateway.py"
$stateDir = Join-Path $projectRoot "integrations\comfyui"
$stdoutLog = Join-Path $stateDir "gateway-watchdog.stdout.log"
$stderrLog = Join-Path $stateDir "gateway-watchdog.stderr.log"
$watchdogLog = Join-Path $stateDir "gateway-watchdog.log"
$lockPath = Join-Path $stateDir "gateway-watchdog.lock"
$port = 8031

function Write-WatchdogLog {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $watchdogLog -Value "$timestamp $Message"
}

function Get-GatewayProcesses {
    Get-CimInstance Win32_Process |
        Where-Object {
            $_.CommandLine -like '*integrations\comfyui\run_gateway.py*' -and
            $_.ExecutablePath -notlike '*powershell.exe'
        }
}

function Get-ListenerProcessId {
    $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($listener) {
        return [int]$listener.OwningProcess
    }
    return $null
}

function Start-GatewayProcess {
    if (!(Test-Path $pythonExe)) {
        throw "Python launcher not found: $pythonExe"
    }
    if (!(Test-Path $gatewayScript)) {
        throw "Gateway script not found: $gatewayScript"
    }
    Start-Process `
        -FilePath $pythonExe `
        -ArgumentList $gatewayScript `
        -WorkingDirectory $projectRoot `
        -RedirectStandardOutput $stdoutLog `
        -RedirectStandardError $stderrLog `
        -WindowStyle Hidden | Out-Null
    Write-WatchdogLog "Started gateway process."
}

function Ensure-SingleGateway {
    $listenerPid = Get-ListenerProcessId
    if ($listenerPid) {
        return
    }

    $gatewayProcesses = @(Get-GatewayProcesses)
    foreach ($process in $gatewayProcesses) {
        try {
            Stop-Process -Id $process.ProcessId -Force -ErrorAction Stop
            Write-WatchdogLog "Stopped stale gateway process $($process.ProcessId)."
        } catch {
            Write-WatchdogLog "Failed to stop stale gateway process $($process.ProcessId): $($_.Exception.Message)"
        }
    }

    if (-not $listenerPid) {
        Start-GatewayProcess
        Start-Sleep -Seconds 3
        $listenerPid = Get-ListenerProcessId
        if ($listenerPid) {
            Write-WatchdogLog "Gateway is listening on port $port with PID $listenerPid."
        } else {
            Write-WatchdogLog "Gateway failed to bind on port $port."
        }
    }
}

function Test-WatchdogLock {
    if (!(Test-Path $lockPath)) {
        return $false
    }
    try {
        $pidText = (Get-Content $lockPath -ErrorAction Stop | Select-Object -First 1).Trim()
        if (-not $pidText) {
            return $false
        }
        $existing = Get-Process -Id ([int]$pidText) -ErrorAction SilentlyContinue
        return [bool]$existing
    } catch {
        return $false
    }
}

if (Test-WatchdogLock) {
    exit 0
}

Set-Content -Path $lockPath -Value $PID
Write-WatchdogLog "Watchdog started with PID $PID."

try {
    while ($true) {
        Ensure-SingleGateway
        Start-Sleep -Seconds 15
    }
} finally {
    Remove-Item $lockPath -Force -ErrorAction SilentlyContinue
    Write-WatchdogLog "Watchdog stopped."
}
