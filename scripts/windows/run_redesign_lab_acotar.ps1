$ErrorActionPreference = "Stop"

$repoRoot = "B:\Documents\PyCharm\graduationProject"
Set-Location $repoRoot

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$reportRoot = "redesign_lab\reports\run_$timestamp"
$outputRoot = "redesign_lab\outputs\run_$timestamp"
$benchmarkLog = Join-Path $reportRoot "benchmark_console.log"
$e2eLog = Join-Path $outputRoot "end_to_end_console.log"
$comparePath = Join-Path $reportRoot "comparison_report.json"

New-Item -ItemType Directory -Force -Path $reportRoot | Out-Null
New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null

$prompt = "Generate an original sequel to A Court of Silver Flames as a Book 6 continuing the established canon storyline of the ACOTAR series with Elain Archeron as primary POV."
$generationControls = '{"chapter_count": 10, "primary_pov_character": "Elain Archeron"}'

Write-Host ""
Write-Host "=== Redesign Lab ACOTAR Run ===" -ForegroundColor Cyan
Write-Host "Repo: $repoRoot"
Write-Host "Reports: $reportRoot"
Write-Host "Outputs: $outputRoot"
Write-Host ""

Write-Progress -Activity "Redesign Lab ACOTAR" -Status "Benchmarking subtasks" -PercentComplete 5
Write-Host "Step 1/3: Running redesign benchmarks..." -ForegroundColor Yellow
cmd /c """$repoRoot\venv\Scripts\python.exe"" ""$repoRoot\redesign_lab_cli.py"" benchmark-all --output-root ""$reportRoot"" 2>&1" | Tee-Object -FilePath $benchmarkLog
if ($LASTEXITCODE -ne 0) {
    Write-Progress -Activity "Redesign Lab ACOTAR" -Completed
    Write-Host ""
    Write-Host "Benchmark phase failed. See: $benchmarkLog" -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit $LASTEXITCODE
}

Write-Progress -Activity "Redesign Lab ACOTAR" -Status "Running redesign end-to-end" -PercentComplete 55
Write-Host ""
Write-Host "Step 2/3: Running redesign end-to-end ACOTAR pass..." -ForegroundColor Yellow
cmd /c """$repoRoot\venv\Scripts\python.exe"" ""$repoRoot\redesign_lab_cli.py"" run-end-to-end --output-root ""$outputRoot"" --prompt ""$prompt"" --generation-controls ""$generationControls"" 2>&1" | Tee-Object -FilePath $e2eLog
if ($LASTEXITCODE -ne 0) {
    Write-Progress -Activity "Redesign Lab ACOTAR" -Completed
    Write-Host ""
    Write-Host "End-to-end phase failed. See: $e2eLog" -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit $LASTEXITCODE
}

Write-Progress -Activity "Redesign Lab ACOTAR" -Status "Building comparison report" -PercentComplete 92
Write-Host ""
Write-Host "Step 3/3: Building baseline vs redesign comparison report..." -ForegroundColor Yellow
& "$repoRoot\venv\Scripts\python.exe" "$repoRoot\redesign_lab_cli.py" compare --baseline-root "analysis_outputs" --redesign-root $outputRoot --output-path $comparePath

Write-Progress -Activity "Redesign Lab ACOTAR" -Completed
Write-Host ""
Write-Host "Redesign lab run finished." -ForegroundColor Green
Write-Host "Benchmark log: $benchmarkLog"
Write-Host "End-to-end log: $e2eLog"
Write-Host "Comparison report: $comparePath"
Write-Host ""
Read-Host "Press Enter to close"
