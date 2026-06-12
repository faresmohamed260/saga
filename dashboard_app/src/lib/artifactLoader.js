import { parseJsonText } from "./jsonLoader";

export async function loadArtifactPayload(artifact) {
  let text = "";
  if (artifact.fileHandle) {
    const file = await artifact.fileHandle.getFile();
    text = await file.text();
  } else if (typeof window !== "undefined" && window.sagaDesktop?.readWorkspaceFile) {
    text = await window.sagaDesktop.readWorkspaceFile(artifact.rootPath || "", artifact.absolutePath || artifact.path);
  } else {
    throw new Error("Artifact file is unavailable.");
  }
  if (artifact.name.toLowerCase().endsWith(".json")) {
    return { contentType: "json", content: await parseJsonText(text), rawText: text };
  }
  return { contentType: "text", content: text, rawText: text };
}
