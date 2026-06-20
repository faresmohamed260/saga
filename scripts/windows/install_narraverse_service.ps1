$ErrorActionPreference = "Stop"

$currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "install_narraverse_service.ps1 must be run from an elevated PowerShell session."
}

$root = Split-Path -Parent $PSScriptRoot
$root = Split-Path -Parent $root
Set-Location $root

$nssm = "C:\tools\NSSM\nssm.exe"
if (-not (Test-Path $nssm)) {
    throw "NSSM was not found at $nssm"
}

$serviceName = "NarraverseWebsite"
$serviceDisplayName = "Narraverse Website"
$runner = Join-Path $root "scripts\windows\run_narraverse_service.cmd"
$appDir = Join-Path $root "apps\narraverse_web"
$logsDir = Join-Path $root "analysis_outputs\narraverse\logs"
$stdoutLog = Join-Path $logsDir "narraverse-website.out.log"
$stderrLog = Join-Path $logsDir "narraverse-website.err.log"

New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

if (-not (Test-Path $runner)) {
    throw "Narraverse runner was not found at $runner"
}

$serviceExists = $null -ne (Get-Service -Name $serviceName -ErrorAction SilentlyContinue)

if (-not $serviceExists) {
    & $nssm install $serviceName $runner | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "NSSM failed to install service '$serviceName' (exit code $LASTEXITCODE)."
    }
}

& $nssm set $serviceName Application $runner | Out-Null
& $nssm set $serviceName AppDirectory $appDir | Out-Null
& $nssm set $serviceName DisplayName $serviceDisplayName | Out-Null
& $nssm set $serviceName Description "Narraverse public website hosted as a local Next.js service." | Out-Null
& $nssm set $serviceName Start SERVICE_AUTO_START | Out-Null
& $nssm set $serviceName AppStdout $stdoutLog | Out-Null
& $nssm set $serviceName AppStderr $stderrLog | Out-Null
& $nssm set $serviceName AppRotateFiles 1 | Out-Null
& $nssm set $serviceName AppRotateOnline 1 | Out-Null
& $nssm set $serviceName AppRotateBytes 1048576 | Out-Null
& $nssm set $serviceName AppStopMethodSkip 6 | Out-Null
& $nssm set $serviceName AppEnvironmentExtra "HOSTNAME=127.0.0.1" "PORT=8676" | Out-Null

if ($LASTEXITCODE -ne 0) {
    throw "NSSM failed while configuring service '$serviceName' (exit code $LASTEXITCODE)."
}

Start-Service $serviceName
Start-Sleep -Seconds 5

$status = Get-Service $serviceName
Write-Host "Installed and started $serviceDisplayName ($($status.Status))." -ForegroundColor Green
Write-Host "Local origin: http://127.0.0.1:8676"
