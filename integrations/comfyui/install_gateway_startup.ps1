$startup = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
$source = "B:\Documents\PyCharm\graduationProject\integrations\comfyui\start_gateway.cmd"
$target = Join-Path $startup "start_gateway.cmd"
Copy-Item -Path $source -Destination $target -Force
Write-Output "Installed startup launcher at $target"
