export const TAB_NAMES = [
  "Overview",
  "Encode Runs",
  "Contract Viewer",
  "Identity Viewer",
  "Character States",
  "Visual World State",
  "ComfyUI Prompts",
  "Retrieval Context",
  "Neo4j",
  "Analysis Config",
  "Decoder Workspace",
  "Reports",
  "Command Center",
];

export const WORKSPACE_SCAN_ROOTS = [
  "analysis_outputs",
  "analysis_outputs/encode_runs",
  "analysis_outputs/encoder_validation",
  "analysis_outputs/identity_series",
  "analysis_outputs/state_snapshots",
  "analysis_outputs/visual_state",
  "analysis_outputs/retrieval_validation",
  "analysis_outputs/dashboard",
];

export const ARTIFACT_TYPES = {
  RUN_STATUS: "run_status",
  CONTRACT: "contract",
  VALIDATION: "validation",
  IDENTITY: "identity",
  CHARACTER_STATE: "character_state",
  VISUAL_WORLD_STATE: "visual_world_state",
  PROMPT_PACK: "prompt_pack",
  RETRIEVAL_CONTEXT: "retrieval_context",
  REPORT: "report",
  OTHER_JSON: "other_json",
};

export const ARTIFACT_TYPE_LABELS = {
  [ARTIFACT_TYPES.RUN_STATUS]: "Encode run",
  [ARTIFACT_TYPES.CONTRACT]: "Contract",
  [ARTIFACT_TYPES.VALIDATION]: "Validation",
  [ARTIFACT_TYPES.IDENTITY]: "Identity",
  [ARTIFACT_TYPES.CHARACTER_STATE]: "Character state",
  [ARTIFACT_TYPES.VISUAL_WORLD_STATE]: "Visual world state",
  [ARTIFACT_TYPES.PROMPT_PACK]: "ComfyUI prompt pack",
  [ARTIFACT_TYPES.RETRIEVAL_CONTEXT]: "Retrieval context",
  [ARTIFACT_TYPES.REPORT]: "Report",
  [ARTIFACT_TYPES.OTHER_JSON]: "JSON",
};

export function normalizePath(path) {
  return String(path || "").replace(/\\/g, "/");
}

export function classifyArtifactPath(path) {
  const normalized = normalizePath(path).toLowerCase();
  const name = normalized.split("/").pop() || "";
  if (name === "latest_status.json" || normalized.includes("/encode_runs/") && name.endsWith(".status.json")) {
    return ARTIFACT_TYPES.RUN_STATUS;
  }
  if (name.endsWith(".contract.json")) {
    return ARTIFACT_TYPES.CONTRACT;
  }
  if (normalized.includes("/identity_series/")) {
    return ARTIFACT_TYPES.IDENTITY;
  }
  if (normalized.includes("/state_snapshots/") && name.endsWith(".json")) {
    return ARTIFACT_TYPES.CHARACTER_STATE;
  }
  if (normalized.includes("/visual_state/") && name.endsWith(".json") && name.includes("prompt_pack")) {
    return ARTIFACT_TYPES.PROMPT_PACK;
  }
  if (normalized.includes("/visual_state/") && name.endsWith(".json")) {
    return ARTIFACT_TYPES.VISUAL_WORLD_STATE;
  }
  if (normalized.includes("/retrieval_validation/") && name.endsWith(".json")) {
    return ARTIFACT_TYPES.RETRIEVAL_CONTEXT;
  }
  if (normalized.includes("/encoder_validation/") && name.endsWith(".json")) {
    return ARTIFACT_TYPES.VALIDATION;
  }
  if (name.endsWith(".md")) {
    return ARTIFACT_TYPES.REPORT;
  }
  if (name.endsWith(".json")) {
    return ARTIFACT_TYPES.OTHER_JSON;
  }
  return null;
}

export function detectSeriesId(path) {
  const normalized = normalizePath(path);
  const match = normalized.match(/analysis_outputs\/encode_runs\/([^/]+)/i);
  if (match) return match[1];
  if (normalized.includes("/identity_series/acotar/")) return "acotar";
  return "";
}

export function detectRunId(path) {
  const normalized = normalizePath(path);
  const match = normalized.match(/analysis_outputs\/encode_runs\/[^/]+\/([^/]+)/i);
  return match ? match[1] : "";
}

export function detectBookIndex(path) {
  const normalized = normalizePath(path);
  const match = normalized.match(/(?:^|\/)(\d{2})_/);
  if (match) return Number(match[1]);
  const bookMatch = normalized.match(/book_(\d{2})_/);
  return bookMatch ? Number(bookMatch[1]) : null;
}
