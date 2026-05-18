$startup = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
$target = Join-Path $startup "start_gateway.cmd"
if (Test-Path $target) {
  Remove-Item $target -Force
  Write-Output "Removed $target"
}
