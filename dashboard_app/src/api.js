async function parseJson(response) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload?.detail || payload?.message || response.statusText;
    throw new Error(detail);
  }
  return payload;
}

function bridgeAvailable() {
  return typeof window !== "undefined" && !!window.pywebview?.api;
}

let bridgeReadyPromise = null;

async function waitForBridge(timeoutMs = 10000) {
  if (bridgeAvailable()) {
    return window.pywebview.api;
  }
  if (!bridgeReadyPromise) {
    bridgeReadyPromise = new Promise((resolve, reject) => {
      let settled = false;
      const finish = (result, isError = false) => {
        if (settled) return;
        settled = true;
        if (isError) reject(result);
        else resolve(result);
      };
      const timer = setTimeout(() => {
        if (bridgeAvailable()) {
          finish(window.pywebview.api);
        } else {
          finish(new Error("Local Python bridge is unavailable."), true);
        }
      }, timeoutMs);
      window.addEventListener(
        "pywebviewready",
        () => {
          clearTimeout(timer);
          finish(window.pywebview.api);
        },
        { once: true },
      );
    });
  }
  return bridgeReadyPromise;
}

async function callBridge(method, ...args) {
  const bridge = await waitForBridge();
  if (typeof bridge?.[method] !== "function") {
    throw new Error(`Local bridge method is unavailable: ${method}`);
  }
  return bridge[method](...args);
}

async function postJson(path, payload) {
  return parseJson(
    await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  );
}

export async function getHealth() {
  if (bridgeAvailable() || (typeof window !== "undefined" && window.location.protocol === "file:")) {
    return callBridge("getHealth");
  }
  throw new Error("Local Python bridge is unavailable.");
}

export async function getOverview() {
  if (bridgeAvailable() || (typeof window !== "undefined" && window.location.protocol === "file:")) {
    return callBridge("getOverview");
  }
  return parseJson(await fetch("/api/overview"));
}

export async function getRuns() {
  if (bridgeAvailable() || (typeof window !== "undefined" && window.location.protocol === "file:")) {
    return callBridge("getRuns");
  }
  return parseJson(await fetch("/api/runs"));
}

export async function getContracts() {
  if (bridgeAvailable() || (typeof window !== "undefined" && window.location.protocol === "file:")) {
    return callBridge("getContracts");
  }
  return parseJson(await fetch("/api/contracts"));
}

export async function getContract(contractId) {
  if (bridgeAvailable() || (typeof window !== "undefined" && window.location.protocol === "file:")) {
    return callBridge("getContract", contractId);
  }
  return parseJson(await fetch(`/api/contracts/${contractId}`));
}

export async function getReports() {
  if (bridgeAvailable() || (typeof window !== "undefined" && window.location.protocol === "file:")) {
    return callBridge("getReports");
  }
  return parseJson(await fetch("/api/reports"));
}

export async function getReport(reportId) {
  if (bridgeAvailable() || (typeof window !== "undefined" && window.location.protocol === "file:")) {
    return callBridge("getReport", reportId);
  }
  return parseJson(await fetch(`/api/reports/${reportId}`));
}

export async function getPresets() {
  if (bridgeAvailable() || (typeof window !== "undefined" && window.location.protocol === "file:")) {
    return callBridge("getPresets");
  }
  return parseJson(await fetch("/api/config/presets"));
}

export async function savePreset(payload) {
  if (bridgeAvailable() || (typeof window !== "undefined" && window.location.protocol === "file:")) {
    return callBridge("savePreset", payload);
  }
  return postJson("/api/config/presets", payload);
}

export async function getIdentities() {
  if (bridgeAvailable() || (typeof window !== "undefined" && window.location.protocol === "file:")) {
    return callBridge("getIdentities");
  }
  return parseJson(await fetch("/api/identities"));
}

export async function getStateSnapshots() {
  if (bridgeAvailable() || (typeof window !== "undefined" && window.location.protocol === "file:")) {
    return callBridge("getStateSnapshots");
  }
  return parseJson(await fetch("/api/state-snapshots"));
}

export async function getVisualWorldStates() {
  if (bridgeAvailable() || (typeof window !== "undefined" && window.location.protocol === "file:")) {
    return callBridge("getVisualWorldStates");
  }
  return parseJson(await fetch("/api/visual-world-states"));
}

export async function getPromptPacks() {
  if (bridgeAvailable() || (typeof window !== "undefined" && window.location.protocol === "file:")) {
    return callBridge("getPromptPacks");
  }
  return parseJson(await fetch("/api/prompt-packs"));
}

export async function getRetrievalContexts() {
  if (bridgeAvailable() || (typeof window !== "undefined" && window.location.protocol === "file:")) {
    return callBridge("getRetrievalContexts");
  }
  return parseJson(await fetch("/api/retrieval-contexts"));
}

export async function exportJson(payload, fileName) {
  if (bridgeAvailable() || (typeof window !== "undefined" && window.location.protocol === "file:")) {
    return callBridge("exportJson", payload, fileName);
  }
  return postJson("/api/export/json", { payload, file_name: fileName });
}

export async function validateContract(payload) {
  if (bridgeAvailable() || (typeof window !== "undefined" && window.location.protocol === "file:")) {
    return callBridge("validateContract", payload);
  }
  return postJson("/api/validate-contract", payload);
}

export async function buildCharacterStateSnapshot(payload) {
  if (bridgeAvailable() || (typeof window !== "undefined" && window.location.protocol === "file:")) {
    return callBridge("buildCharacterStateSnapshot", payload);
  }
  return postJson("/api/build-character-state-snapshot", payload);
}

export async function buildVisualWorldState(payload) {
  if (bridgeAvailable() || (typeof window !== "undefined" && window.location.protocol === "file:")) {
    return callBridge("buildVisualWorldState", payload);
  }
  return postJson("/api/build-visual-world-state", payload);
}

export async function buildComfyuiPromptPack(payload) {
  if (bridgeAvailable() || (typeof window !== "undefined" && window.location.protocol === "file:")) {
    return callBridge("buildComfyuiPromptPack", payload);
  }
  return postJson("/api/build-comfyui-prompt-pack", payload);
}

export async function validateGenerationContext(payload) {
  if (bridgeAvailable() || (typeof window !== "undefined" && window.location.protocol === "file:")) {
    return callBridge("validateGenerationContext", payload);
  }
  return postJson("/api/validate-generation-context", payload);
}

export async function getNeo4jStatus() {
  if (bridgeAvailable() || (typeof window !== "undefined" && window.location.protocol === "file:")) {
    return callBridge("getNeo4jStatus");
  }
  return parseJson(await fetch("/api/neo4j/status"));
}

export async function getNeo4jSeries() {
  if (bridgeAvailable() || (typeof window !== "undefined" && window.location.protocol === "file:")) {
    return callBridge("getNeo4jSeries");
  }
  return parseJson(await fetch("/api/neo4j/series"));
}

export async function getNeo4jBooks(seriesId = "") {
  if (bridgeAvailable() || (typeof window !== "undefined" && window.location.protocol === "file:")) {
    return callBridge("getNeo4jBooks", seriesId);
  }
  const suffix = seriesId ? `?series_id=${encodeURIComponent(seriesId)}` : "";
  return parseJson(await fetch(`/api/neo4j/books${suffix}`));
}

export async function getNeo4jSummary(seriesId = "", bookTitle = "") {
  if (bridgeAvailable() || (typeof window !== "undefined" && window.location.protocol === "file:")) {
    return callBridge("getNeo4jSummary", seriesId, bookTitle);
  }
  const params = new URLSearchParams();
  if (seriesId) params.set("series_id", seriesId);
  if (bookTitle) params.set("book_title", bookTitle);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return parseJson(await fetch(`/api/neo4j/summary${suffix}`));
}

export async function neo4jDeleteDryRun(payload) {
  if (bridgeAvailable() || (typeof window !== "undefined" && window.location.protocol === "file:")) {
    return callBridge("neo4jDeleteDryRun", payload);
  }
  return postJson("/api/neo4j/delete/dry-run", payload);
}

export async function neo4jDeleteConfirm(payload) {
  if (bridgeAvailable() || (typeof window !== "undefined" && window.location.protocol === "file:")) {
    return callBridge("neo4jDeleteConfirm", payload);
  }
  return postJson("/api/neo4j/delete/confirm", payload);
}

export async function neo4jIngest(payload) {
  if (bridgeAvailable() || (typeof window !== "undefined" && window.location.protocol === "file:")) {
    return callBridge("neo4jIngest", payload);
  }
  return postJson("/api/neo4j/ingest", payload);
}

export async function buildContext(payload) {
  if (bridgeAvailable() || (typeof window !== "undefined" && window.location.protocol === "file:")) {
    return callBridge("buildContext", payload);
  }
  return postJson("/api/build-context", payload);
}

export async function generateBlueprint(payload) {
  if (bridgeAvailable() || (typeof window !== "undefined" && window.location.protocol === "file:")) {
    return callBridge("generateBlueprint", payload);
  }
  return postJson("/api/generate-blueprint", payload);
}

export async function generateOutline(payload) {
  if (bridgeAvailable() || (typeof window !== "undefined" && window.location.protocol === "file:")) {
    return callBridge("generateOutline", payload);
  }
  return postJson("/api/generate-outline", payload);
}

export async function generateScene(payload) {
  if (bridgeAvailable() || (typeof window !== "undefined" && window.location.protocol === "file:")) {
    return callBridge("generateScene", payload);
  }
  return postJson("/api/generate-scene", payload);
}

export async function generateProse(payload) {
  if (bridgeAvailable() || (typeof window !== "undefined" && window.location.protocol === "file:")) {
    return callBridge("generateProse", payload);
  }
  return postJson("/api/generate-prose", payload);
}
