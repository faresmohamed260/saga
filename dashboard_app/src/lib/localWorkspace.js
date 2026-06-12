const DB_NAME = "saga-dashboard-local";
const STORE_NAME = "handles";
const WORKSPACE_KEY = "workspace";
const SETTINGS_KEY = "settings";

function desktopBridge() {
  return typeof window !== "undefined" ? window.sagaDesktop : null;
}

function openDb() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onerror = () => reject(request.error);
    request.onupgradeneeded = () => {
      request.result.createObjectStore(STORE_NAME);
    };
    request.onsuccess = () => resolve(request.result);
  });
}

async function withStore(mode, fn) {
  const db = await openDb();
  try {
    return await fn(db.transaction(STORE_NAME, mode).objectStore(STORE_NAME));
  } finally {
    db.close();
  }
}

export function fileSystemAccessSupported() {
  return !!desktopBridge() || (typeof window !== "undefined" && "showDirectoryPicker" in window);
}

export async function saveWorkspaceHandle(handle) {
  return withStore("readwrite", (store) => new Promise((resolve, reject) => {
    const request = store.put(handle, WORKSPACE_KEY);
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(true);
  }));
}

export async function loadWorkspaceHandle() {
  const desktop = desktopBridge();
  if (desktop?.getDefaultWorkspace) {
    return desktop.getDefaultWorkspace();
  }
  return withStore("readonly", (store) => new Promise((resolve, reject) => {
    const request = store.get(WORKSPACE_KEY);
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result || null);
  }));
}

export async function clearWorkspaceHandle() {
  if (desktopBridge()) {
    return true;
  }
  return withStore("readwrite", (store) => new Promise((resolve, reject) => {
    const request = store.delete(WORKSPACE_KEY);
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(true);
  }));
}

export async function pickWorkspaceDirectory() {
  const desktop = desktopBridge();
  if (desktop?.getDefaultWorkspace) {
    return desktop.getDefaultWorkspace();
  }
  const handle = await window.showDirectoryPicker({ mode: "readwrite" });
  await saveWorkspaceHandle(handle);
  return handle;
}

export async function verifyReadPermission(handle) {
  if (handle?.kind === "desktop-root") return true;
  if (!handle?.queryPermission) return false;
  const state = await handle.queryPermission({ mode: "read" });
  return state === "granted";
}

export async function requestReadPermission(handle) {
  if (handle?.kind === "desktop-root") return true;
  if (!handle?.requestPermission) return false;
  const state = await handle.requestPermission({ mode: "read" });
  return state === "granted";
}

export async function saveWorkspaceSettings(settings) {
  return withStore("readwrite", (store) => new Promise((resolve, reject) => {
    const request = store.put(settings, SETTINGS_KEY);
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(true);
  }));
}

export async function loadWorkspaceSettings() {
  return withStore("readonly", (store) => new Promise((resolve, reject) => {
    const request = store.get(SETTINGS_KEY);
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result || null);
  }));
}

export function defaultWorkspaceSettings() {
  return {
    workspacePathLabel: "",
    refreshIntervalMs: 4000,
    demoMode: false,
    neo4j: {
      uri: "bolt://localhost:7687",
      username: "neo4j",
      password: "",
      database: "neo4j",
      saveCredentials: false,
    },
  };
}
