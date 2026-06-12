function quote(value) {
  return `"${String(value).replace(/"/g, '\\"')}"`;
}

export function buildEncodeStoreCommand(config) {
  const books = (config.books || []).map((book) => `--book ${quote(book)}`).join(" ");
  const parts = [
    ".\\venv\\Scripts\\python.exe saga_tools.py encode-store",
    books,
    `--series-id ${config.seriesId || "series-id"}`,
    `--series-title ${quote(config.seriesTitle || "Series Title")}`,
    `--book-index-base ${config.bookIndexBase || 1}`,
    `--analysis-model ${config.analysisModel || "gpt_oss"}`,
    `--identity-model ${config.identityModel || "gpt_oss"}`,
    `--analysis-provider-mode ${config.analysisProviderMode || "same_provider_rotating"}`,
    `--identity-provider ${config.identityProvider || "booknlp_clean"}`,
    config.seriesIdentityJson ? `--series-identity-json ${quote(config.seriesIdentityJson)}` : "",
    `--scene-failure-policy ${config.sceneFailurePolicy || "fail_fast"}`,
    `--max-failed-scenes-absolute ${config.maxFailedScenesAbsolute ?? 3}`,
    `--max-failed-scene-ratio ${config.maxFailedSceneRatio ?? 0.1}`,
    `--min-nonempty-scene-ratio ${config.minNonemptySceneRatio ?? 0.8}`,
    `--max-parallel-books ${config.maxParallelBooks ?? 1}`,
    config.skipIngest ? "--skip-ingest" : "",
    config.noProgress !== false ? "--no-progress" : "",
    config.outPath ? `--out ${quote(config.outPath)}` : "",
  ].filter(Boolean);
  return parts.join(" ");
}

export function buildValidateContractCommand(contractPath, config = {}) {
  return [
    ".\\venv\\Scripts\\python.exe saga_tools.py validate-encoder-artifacts",
    `--contract ${quote(contractPath)}`,
    `--identity-provider ${config.identityProvider || "booknlp_clean"}`,
    config.identityJson ? `--identity-json ${quote(config.identityJson)}` : "",
    config.outPath ? `--out ${quote(config.outPath)}` : "",
    config.reportPath ? `--report-md ${quote(config.reportPath)}` : "",
  ]
    .filter(Boolean)
    .join(" ");
}

export function buildCharacterSnapshotCommand(config) {
  const contracts = (config.contractPaths || []).map((item) => `--contract ${quote(item)}`).join(" ");
  return [
    ".\\venv\\Scripts\\python.exe saga_tools.py build-character-state-snapshot",
    contracts,
    `--identity-provider ${config.identityProvider || "booknlp_clean"}`,
    config.seriesIdentityJson ? `--series-identity-json ${quote(config.seriesIdentityJson)}` : "",
    `--target-mode ${config.targetMode || "post_series"}`,
    config.afterBookIndex ? `--after-book-index ${config.afterBookIndex}` : "",
    config.bookIndex ? `--book-index ${config.bookIndex}` : "",
    config.chapter ? `--chapter ${config.chapter}` : "",
    config.outPath ? `--out ${quote(config.outPath)}` : "",
    config.reportPath ? `--report-md ${quote(config.reportPath)}` : "",
  ]
    .filter(Boolean)
    .join(" ");
}

export function buildVisualWorldStateCommand(config) {
  const contracts = (config.contractPaths || []).map((item) => `--contract ${quote(item)}`).join(" ");
  return [
    ".\\venv\\Scripts\\python.exe saga_tools.py build-visual-world-state",
    contracts,
    `--identity-provider ${config.identityProvider || "booknlp_clean"}`,
    config.seriesIdentityJson ? `--series-identity-json ${quote(config.seriesIdentityJson)}` : "",
    `--target-mode ${config.targetMode || "post_series"}`,
    config.afterBookIndex ? `--after-book-index ${config.afterBookIndex}` : "",
    config.outPath ? `--out ${quote(config.outPath)}` : "",
    config.reportPath ? `--report-md ${quote(config.reportPath)}` : "",
  ]
    .filter(Boolean)
    .join(" ");
}

export function buildPromptPackCommand(config) {
  return [
    ".\\venv\\Scripts\\python.exe saga_tools.py build-comfyui-prompt-pack",
    `--visual-state ${quote(config.visualStatePath || "")}`,
    config.contractPath ? `--contract ${quote(config.contractPath)}` : "",
    `--mode ${config.promptMode || "full_prompt_pack"}`,
    config.outPath ? `--out ${quote(config.outPath)}` : "",
    config.reportPath ? `--report-md ${quote(config.reportPath)}` : "",
  ]
    .filter(Boolean)
    .join(" ");
}

export function buildValidateGenerationContextCommand(config) {
  const contracts = (config.contractPaths || []).map((item) => `--contract ${quote(item)}`).join(" ");
  return [
    ".\\venv\\Scripts\\python.exe saga_tools.py validate-generation-context",
    contracts,
    `--identity-provider ${config.identityProvider || "booknlp_clean"}`,
    config.seriesIdentityJson ? `--series-identity-json ${quote(config.seriesIdentityJson)}` : "",
    config.targetStatesPath ? `--target-states ${quote(config.targetStatesPath)}` : "",
    `--target-mode ${config.targetMode || "post_series"}`,
    config.afterBookIndex ? `--after-book-index ${config.afterBookIndex}` : "",
    `--prompt ${quote(config.prompt || "Prepare canon-aware context.")}`,
    config.outPath ? `--out ${quote(config.outPath)}` : "",
    config.reportPath ? `--report-md ${quote(config.reportPath)}` : "",
  ]
    .filter(Boolean)
    .join(" ");
}

export function buildNeo4jDeleteCypher(seriesId, bookTitle = "") {
  if (bookTitle) {
    return `MATCH (b:Book {series_id: "${seriesId}", title: "${bookTitle}"}) DETACH DELETE b;`;
  }
  return `MATCH (s:Series {series_id: "${seriesId}"}) DETACH DELETE s;`;
}
