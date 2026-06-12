let worker = null;
let nextId = 1;
const pending = new Map();

function getWorker() {
  if (!worker) {
    worker = new Worker(new URL("../workers/jsonLoaderWorker.js", import.meta.url), { type: "module" });
    worker.onmessage = (event) => {
      const { id, ok, payload, summary, error } = event.data;
      const callback = pending.get(id);
      if (!callback) return;
      pending.delete(id);
      if (ok) {
        callback.resolve(payload ?? summary);
      } else {
        callback.reject(new Error(error || "Worker parse failed"));
      }
    };
  }
  return worker;
}

function runWorker(action, text, artifactType) {
  return new Promise((resolve, reject) => {
    const id = nextId++;
    pending.set(id, { resolve, reject });
    getWorker().postMessage({ id, action, text, artifactType });
  });
}

export async function parseJsonText(text) {
  return runWorker("parse", text, "");
}

export async function summarizeJsonText(text, artifactType) {
  return runWorker("summarize", text, artifactType);
}
