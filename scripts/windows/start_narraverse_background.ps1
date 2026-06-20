$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$root = Split-Path -Parent $root
Set-Location $root

$runner = Join-Path $root "scripts\windows\run_narraverse_service.cmd"
$logsDir = Join-Path $root "analysis_outputs\narraverse\logs"
$pidFile = Join-Path $logsDir "narraverse-website.pid"

New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

if (Test-Path $pidFile) {
    $oldPid = Get-Content $pidFile | Select-Object -First 1
    if ($oldPid) {
        Stop-Process -Id ([int]$oldPid) -Force -ErrorAction SilentlyContinue
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

$env:HOSTNAME = "127.0.0.1"
$env:PORT = "8676"

$process = Start-Process `
    -FilePath "cmd.exe" `
    -ArgumentList "/c", "`"$runner`"" `
    -WorkingDirectory $root `
    -WindowStyle Hidden `
    -PassThru

$process.Id | Set-Content -Path $pidFile -Encoding ASCII

$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8676" -TimeoutSec 5
        if ($response.StatusCode -eq 200) {
            $ready = $true
            break
        }
    } catch {}
}

if (-not $ready) {
    throw "Narraverse website did not become ready on http://127.0.0.1:8676"
}

Write-Host "Narraverse website started in the background." -ForegroundColor Green
Write-Host "Local origin: http://127.0.0.1:8676"
