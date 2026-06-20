$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$root = Split-Path -Parent $root
Set-Location $root

$taskName = "NarraverseWebsite"
$startScript = Join-Path $root "scripts\windows\start_narraverse_background.ps1"
$powershellExe = (Get-Command powershell.exe).Source

$taskAction = New-ScheduledTaskAction `
    -Execute $powershellExe `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$startScript`""

$taskTrigger = New-ScheduledTaskTrigger -AtLogOn
$taskSettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

try {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue | Out-Null
} catch {}

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $taskAction `
    -Trigger $taskTrigger `
    -Settings $taskSettings `
    -Principal $principal `
    -Description "Run the Narraverse website in the background without leaving a terminal open." | Out-Null

Start-ScheduledTask -TaskName $taskName
Start-Sleep -Seconds 3

Write-Host "Registered and started scheduled task: $taskName" -ForegroundColor Green
