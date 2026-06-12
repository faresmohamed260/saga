import { classifyArtifactPath, detectBookIndex, detectRunId, detectSeriesId, normalizePath, WORKSPACE_SCAN_ROOTS } from "./artifactTypes";
import { summarizeJsonText } from "./jsonLoader";
import { summarizeMarkdown } from "./reportLoader";

async function getDirectoryByPath(rootHandle, pathText) {
  if (rootHandle?.kind === "desktop-root") {
    return { kind: "desktop-root", desktopPath: rootHandle.desktopPath, subPath: pathText };
  }
  const segments = normalizePath(pathText).split("/").filter(Boolean);
  let current = rootHandle;
  for (const segment of segments) {
    try {
      current = await current.getDirectoryHandle(segment);
    } catch {
      return null;
    }
  }
  return current;
}

async function collectFilesRecursive(dirHandle, prefix, results) {
  if (dirHandle?.kind === "desktop-root") {
    const desktop = typeof window !== "undefined" ? window.sagaDesktop : null;
    if (!desktop?.listWorkspaceFiles) return;
    const files = await desktop.listWorkspaceFiles(dirHandle.desktopPath, [dirHandle.subPath || prefix || ""]);
    results.push(...files);
    return;
  }
  for await (const entry of dirHandle.values()) {
    const nextPath = prefix ? `${prefix}/${entry.name}` : entry.name;
    if (entry.kind === "directory") {
      await collectFilesRecursive(entry, nextPath, results);
    } else {
      results.push({ handle: entry, path: nextPath });
    }
  }
}

export async function scanWorkspaceFiles(rootHandle) {
  const results = [];
  const seen = new Set();
  for (const root of WORKSPACE_SCAN_ROOTS) {
    const dirHandle = await getDirectoryByPath(rootHandle, root);
    if (!dirHandle) continue;
    const before = results.length;
    await collectFilesRecursive(dirHandle, root, results);
    for (let index = results.length - 1; index >= before; index -= 1) {
      const key = normalizePath(results[index].path);
      if (seen.has(key)) {
        results.splice(index, 1);
      } else {
        seen.add(key);
      }
    }
  }
  return results;
}

async function summarizeFile(fileRecord, summaryCache) {
  const { handle, path } = fileRecord;
  const entryName = handle?.name || fileRecord.name || normalizePath(path).split("/").pop() || "";
  const file = handle
    ? await handle.getFile()
    : {
        size: fileRecord.fileSize || 0,
        lastModified: fileRecord.modifiedTime || 0,
        async text() {
          const desktop = typeof window !== "undefined" ? window.sagaDesktop : null;
          return desktop.readWorkspaceFile(fileRecord.rootPath || "", fileRecord.absolutePath || fileRecord.path);
        },
      };
  const artifactType = classifyArtifactPath(path);
  if (!artifactType) return null;
  const cacheKey = `${normalizePath(path)}::${file.size}::${file.lastModified}`;
  if (summaryCache.has(cacheKey)) {
    return { ...summaryCache.get(cacheKey), fileHandle: handle };
  }
  const record = {
    id: normalizePath(path),
    artifactType,
    name: entryName,
    displayName: entryName,
    path: normalizePath(path),
    modifiedTime: file.lastModified,
    modifiedIso: new Date(file.lastModified).toISOString(),
    fileSize: file.size,
    seriesId: detectSeriesId(path),
    bookIndex: detectBookIndex(path),
    runId: detectRunId(path),
    status: "",
    summary: {},
  };
  if (entryName.endsWith(".json")) {
    const text = await file.text();
    const summary = await summarizeJsonText(text, artifactType);
    record.summary = summary;
    record.status = summary.runStatus || summary.targetStatus || summary.defaultStatus || summary.validationMode || "";
  } else if (entryName.endsWith(".md")) {
    const text = await file.text();
    record.summary = summarizeMarkdown(text);
  }
  summaryCache.set(cacheKey, record);
  return { ...record, fileHandle: handle || null, absolutePath: fileRecord.absolutePath || "", rootPath: fileRecord.rootPath || "" };
}

export async function buildArtifactIndex(rootHandle, options = {}) {
  const summaryCache = options.summaryCache || new Map();
  const previousByPath = options.previousByPath || new Map();
  const files = await scanWorkspaceFiles(rootHandle);
  const items = [];
  let changedCount = 0;
  for (const fileRecord of files) {
    const artifact = await summarizeFile(fileRecord, summaryCache);
    if (!artifact) continue;
    const previous = previousByPath.get(artifact.path);
    const changed =
      !previous ||
      previous.modifiedTime !== artifact.modifiedTime ||
      previous.fileSize !== artifact.fileSize;
    if (changed) changedCount += 1;
    items.push({ ...artifact, changed, newArtifact: !previous });
  }
  items.sort((left, right) => right.modifiedTime - left.modifiedTime);
  const counts = items.reduce((acc, item) => {
    acc[item.artifactType] = (acc[item.artifactType] || 0) + 1;
    return acc;
  }, {});
  return {
    items,
    counts,
    changedCount,
    lastRefreshIso: new Date().toISOString(),
    byPath: new Map(items.map((item) => [item.path, item])),
  };
}
