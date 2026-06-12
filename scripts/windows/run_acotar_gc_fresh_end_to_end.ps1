$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

Set-Location "B:\Documents\PyCharm\graduationProject"
$env:PYTHONIOENCODING = "utf-8"

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$generationOutput = "analysis_outputs\generated_narratives\acotar_book6_gc_scene_inline_fresh_$timestamp"

$prompt = @'
Generate an original sequel to A Court of Silver Flames as a Book 6 continuing the established canon storyline of the ACOTAR series.

Main focus:
- Elain Archeron as the primary POV character
- political instability across Prythian and the human lands
- growing threat of Koschei
- exploration of Elain’s Seer powers
- emotional and political tension between Elain, Azriel, and Lucien

Core relationship expectations:
- Elain and Azriel develop a forbidden romantic relationship
- Lucien struggles with the rejected mating bond
- Lucien becomes increasingly important politically due to his connection to the Day Court and Autumn Court
- Nesta and Cassian remain together and help investigate ancient magical threats
- Feyre and Rhysand act as rulers and parents while preparing for possible war

Required canon continuity:
- Feyre and Rhys are married with Nyx
- Nesta lost most of her powers but still retains dangerous magical abilities
- Tamlin remains isolated and emotionally broken
- Azriel struggles with self-worth and emotional repression
- Elain remains quiet, observant, emotionally withdrawn, and uncomfortable with the mating bond
- Lucien is loyal but lonely and conflicted
- Koschei remains imprisoned but influential
- the human queens are still active threats
- the Prison, Dusk Court lore, and possible world-crossing magic remain unresolved mysteries

Expected plot progression:
1. Elain begins experiencing increasingly violent prophetic visions connected to Koschei, the Prison, and future wars.
2. Strange magical activity emerges near the human lands.
3. Azriel investigates Koschei-related threats while growing closer to Elain.
4. The mating bond between Lucien and Elain becomes emotionally and magically unstable.
5. Nesta, Gwyn, and the Valkyries uncover ancient information about Made Seers and hidden gates between worlds.
6. Political conflict grows in the Autumn Court and Day Court.
7. Koschei attempts to use Elain’s powers to locate or open interworld gateways.
8. Azriel is captured during the conflict.
9. Elain fully embraces her Seer abilities and plays a major role in the final battle.
10. Lucien ultimately releases Elain from the emotional expectation of the mating bond.
11. The story ends with hints of larger crossover-level threats connected to other worlds and ancient fae history.

Tone and style requirements:
- emotionally intense character-driven fantasy
- slow-burn romance
- strong interpersonal tension
- poetic and atmospheric descriptions
- political intrigue mixed with magical lore
- high emotional continuity with previous books
- preserve ACOTAR-style dialogue, pacing, and relationship dynamics

Important consistency requirements:
- maintain accurate character personalities and speech patterns
- preserve existing relationships and unresolved tensions from canon
- ensure long-term foreshadowing pays off logically
- keep court politics, magic systems, and power scaling internally consistent
- maintain continuity of emotional development across all major characters
'@

Write-Host ""
Write-Host "=== Fresh ACOTAR GC End-to-End Run ===" -ForegroundColor Cyan
Write-Host "Repo: B:\Documents\PyCharm\graduationProject"
Write-Host "Generation output: $generationOutput"
Write-Host ""

Write-Host "Step 1/2: Encoding and persisting ACOTAR from raw EPUBs (sequential GC, scene-inline identity)..." -ForegroundColor Yellow
& "venv\Scripts\python.exe" "saga_tools.py" "encode-store" `
  "--book" "D:\Books\Ebooks\Sarah J. Maas\A Court of Thorns and Roses\A Court of Thorns and Roses.epub" `
  "--book" "D:\Books\Ebooks\Sarah J. Maas\A Court of Mist and Fury\A Court of Mist and Fury.epub" `
  "--book" "D:\Books\Ebooks\Sarah J. Maas\A Court of Wings and Ruin\A Court of Wings and Ruin.epub" `
  "--book" "D:\Books\Ebooks\Sarah J. Maas\A Court of Frost and Starlight\A Court of Frost and Starlight.epub" `
  "--book" "D:\Books\Ebooks\Sarah J. Maas\A Court of Silver Flames\A Court of Silver Flames.epub" `
  "--series-id" "acotar" `
  "--series-title" "A Court of Thorns and Roses" `
  "--book-index-base" "1" `
  "--analysis-model" "general_compute" `
  "--identity-model" "general_compute" `
  "--identity-strategy" "scene_inline" `
  "--analysis-mode" "structured" `
  "--target-scene-words" "0" `
  "--max-parallel-books" "1"
if ($LASTEXITCODE -ne 0) {
  throw "encode-store failed with exit code $LASTEXITCODE"
}

Write-Host ""
Write-Host "Step 2/2: Generating fresh ACOTAR Book 6 on the newly rebuilt graph (GC path)..." -ForegroundColor Yellow
& "venv\Scripts\python.exe" "saga_tools.py" "generate-sequel-neo4j" `
  "--series-id" "acotar" `
  "--prompt" $prompt `
  "--output-dir" $generationOutput `
  "--chapters" "10" `
  "--canon-position" "post_canon" `
  "--primary-pov" "Elain Archeron" `
  "--new-plot" "A hidden magical convergence tied to Koschei, the Prison, and world-crossing gates destabilizes Prythian and the human lands." `
  "--relationship-direction" "Elain Archeron,Azriel|romance|develop a forbidden romantic relationship|slow-burn emotional intimacy under political pressure" `
  "--relationship-direction" "Elain Archeron,Lucien Vanserra|other|the bond becomes unstable and Lucien ultimately releases Elain from its emotional expectation|politically and emotionally consequential" `
  "--continuity-anchor" "Continue directly from the emotional and political aftermath of A Court of Silver Flames while preserving all major canon relationships and unresolved threats." `
  "--model-mode" "general_compute"
if ($LASTEXITCODE -ne 0) {
  throw "generate-sequel-neo4j failed with exit code $LASTEXITCODE"
}

Write-Host ""
Write-Host "=== Fresh ACOTAR GC Run Complete ===" -ForegroundColor Green
Write-Host "Generation output folder: $generationOutput"
