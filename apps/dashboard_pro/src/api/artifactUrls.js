import { toQuery } from "./client";

function stringValue(value) {
  return typeof value === "string" ? value.trim() : "";
}

function objectValue(value) {
  return value && typeof value === "object" ? value : null;
}

export function artifactUrl(reference) {
  const ref = objectValue(reference);
  if (!ref) return "";

  const explicitUrl = stringValue(ref.runtime_url || ref.download_url || ref.public_url || ref.url);
  if (explicitUrl) return explicitUrl;

  const bucketName = stringValue(ref.bucket_name);
  const objectPath = stringValue(ref.object_path);
  if (bucketName && objectPath) {
    return `/runtime/artifacts/object${toQuery({ bucket_name: bucketName, object_path: objectPath })}`;
  }

  return "";
}

export function audiobookRunBundleUrl(runOrId, fallbackId = "") {
  const ref = objectValue(runOrId);
  if (ref) {
    const explicit = artifactUrl(ref.bundle_artifact || ref.bundle || ref.bundle_file || ref.bundle_url);
    if (explicit) return explicit;
    const runId = stringValue(ref.id || ref.run_id || fallbackId);
    if (runId) {
      return `/runtime/audiobook/runs/${encodeURIComponent(runId)}/audio`;
    }
    return "";
  }

  const runId = stringValue(runOrId || fallbackId);
  if (!runId) return "";
  return `/runtime/audiobook/runs/${encodeURIComponent(runId)}/audio`;
}
