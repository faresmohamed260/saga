const { contextBridge } = require("electron");
const fs = require("fs/promises");
const path = require("path");

const ROOT = path.resolve(__dirname, "..", "..");

async function walk(dirPath, prefix, results) {
  let entries = [];
  try {
    entries = await fs.readdir(dirPath, { withFileTypes: true });
  } catch {
    return;
  }
  for (const entry of entries) {
    const absPath = path.join(dirPath, entry.name);
    const relPath = prefix ? `${prefix}/${entry.name}` : entry.name;
    if (entry.isDirectory()) {
      await walk(absPath, relPath, results);
      continue;
    }
    if (!entry.isFile()) continue;
    const stats = await fs.stat(absPath);
    results.push({
      kind: "file",
      name: entry.name,
      path: relPath.replace(/\\/g, "/"),
      absolutePath: absPath,
      modifiedTime: stats.mtimeMs,
      fileSize: stats.size,
      source: "desktop",
    });
  }
}

async function listWorkspaceFiles(rootPath, scanRoots) {
  const results = [];
  const seen = new Set();
  for (const root of scanRoots || []) {
    const absRoot = path.join(rootPath, root);
    const before = results.length;
    await walk(absRoot, root.replace(/\\/g, "/"), results);
    for (let index = results.length - 1; index >= before; index -= 1) {
      const key = results[index].path;
      if (seen.has(key)) {
        results.splice(index, 1);
      } else {
        seen.add(key);
      }
    }
  }
  return results;
}

async function readWorkspaceFile(_rootPath, relativePathOrAbsolutePath) {
  const absPath = path.isAbsolute(relativePathOrAbsolutePath)
    ? relativePathOrAbsolutePath
    : path.join(ROOT, relativePathOrAbsolutePath);
  return fs.readFile(absPath, "utf-8");
}

contextBridge.exposeInMainWorld("sagaDesktop", {
  getDefaultWorkspace: async () => ({
    kind: "desktop-root",
    desktopPath: ROOT,
    name: path.basename(ROOT),
    label: ROOT,
    source: "electron",
  }),
  listWorkspaceFiles,
  readWorkspaceFile,
});
