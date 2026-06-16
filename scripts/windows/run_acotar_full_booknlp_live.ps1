$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$root = Split-Path -Parent $root
Set-Location $root

$python = Join-Path $root "venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
  throw "Missing Python virtual environment at $python"
}

$seriesId = "acotar-full-booknlp-clean-live"
$seriesTitle = "ACOTAR Full BookNLP Clean Live"
$seriesIdentity = "analysis_outputs\identity_series\acotar\acotar_series_pipeline_identity.json"
$statusOut = "analysis_outputs\dashboard\acotar_full_booknlp_clean_live_status.json"
$visualOut = "analysis_outputs\visual_state\acotar_full_booknlp_clean_live_visual_world_state.json"
$visualReport = "analysis_outputs\visual_state\acotar_full_booknlp_clean_live_visual_world_state_report.md"

$books = @(
  "D:\Books\Ebooks\Sarah J. Maas\A Court of Thorns and Roses\A Court of Thorns and Roses.epub",
  "D:\Books\Ebooks\Sarah J. Maas\A Court of Mist and Fury\A Court of Mist and Fury.epub",
  "D:\Books\Ebooks\Sarah J. Maas\A Court of Wings and Ruin\A Court of Wings and Ruin.epub",
  "D:\Books\Ebooks\Sarah J. Maas\A Court of Frost and Starlight\A Court of Frost and Starlight.epub",
  "D:\Books\Ebooks\Sarah J. Maas\A Court of Silver Flames\A Court of Silver Flames.epub"
)

$encodeArgs = @("saga_tools.py", "encode-store")
foreach ($book in $books) {
  $encodeArgs += @("--book", $book)
}
$encodeArgs += @(
  "--series-id", $seriesId,
  "--series-title", $seriesTitle,
  "--book-index-base", "1",
  "--analysis-model", "gpt_oss",
  "--identity-model", "gpt_oss",
  "--analysis-provider-mode", "same_provider_rotating",
  "--identity-provider", "booknlp_clean",
  "--series-identity-json", $seriesIdentity,
  "--scene-failure-policy", "fail_fast",
  "--max-failed-scenes-absolute", "3",
  "--max-failed-scene-ratio", "0.10",
  "--min-nonempty-scene-ratio", "0.80",
  "--max-parallel-books", "1",
  "--no-progress",
  "--out", $statusOut
)

& $python @encodeArgs
if ($LASTEXITCODE -ne 0) {
  throw "encode-store failed with exit code $LASTEXITCODE"
}

$seriesDir = Join-Path $root ("analysis_outputs\contract_exports\" + $seriesId)
$runDir = Get-ChildItem $seriesDir -Directory | Where-Object { $_.Name -match '^\d{8}T' } | Sort-Object Name -Descending | Select-Object -First 1
if (-not $runDir) {
  throw "Could not find run directory for $seriesId"
}

$contractArgs = @("saga_tools.py", "build-visual-world-state")
Get-ChildItem (Join-Path $runDir.FullName "contracts") -Filter "*.json" | Sort-Object Name | ForEach-Object {
  $contractArgs += @("--contract", $_.FullName)
}
$contractArgs += @(
  "--identity-provider", "booknlp_clean",
  "--series-identity-json", $seriesIdentity,
  "--target-mode", "post_series",
  "--after-book-index", "5",
  "--out", $visualOut,
  "--report-md", $visualReport
)

& $python @contractArgs
if ($LASTEXITCODE -ne 0) {
  throw "build-visual-world-state failed with exit code $LASTEXITCODE"
}
