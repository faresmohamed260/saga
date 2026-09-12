"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import {
  completeSourceUploadAction,
  startSourceUploadAction,
  type SourceUploadActionError,
} from "./source-upload-actions";

const errorCopy: Record<SourceUploadActionError | "upload_failed", string> = {
  invalid_request: "Choose a valid UTF-8 .txt or .epub source and try again.",
  not_found: "That project or source is no longer available.",
  storage_unavailable: "Source storage is not configured for this environment yet.",
  upload_incomplete: "The source object was not found after upload. Try the upload again.",
  upload_mismatch: "The uploaded object did not match its declared metadata, so S.A.G.A. rejected it.",
  unavailable: "Source upload is temporarily unavailable.",
  upload_failed: "The object upload was not accepted by storage.",
};

type UploadStage = "idle" | "hashing" | "uploading" | "verifying" | "queued";

function inferFormat(filename: string): "txt" | "epub" | null {
  const lower = filename.toLowerCase();
  if (lower.endsWith(".txt")) return "txt";
  if (lower.endsWith(".epub")) return "epub";
  return null;
}

function defaultDisplayName(filename: string) {
  return filename.replace(/\.(txt|epub)$/i, "").trim() || filename;
}

async function sha256Hex(file: File) {
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, "0")).join("");
}

export function SourceUploadForm({ projectId }: Readonly<{ projectId: string }>) {
  const router = useRouter();
  const [stage, setStage] = useState<UploadStage>("idle");
  const [message, setMessage] = useState<string | null>(null);

  const busy = stage === "hashing" || stage === "uploading" || stage === "verifying";

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;

    setMessage(null);
    const form = event.currentTarget;
    const formData = new FormData(form);
    const file = formData.get("source");
    const displayNameValue = formData.get("displayName");

    if (!(file instanceof File) || file.size <= 0) {
      setMessage(errorCopy.invalid_request);
      return;
    }

    const format = inferFormat(file.name);
    if (!format) {
      setMessage(errorCopy.invalid_request);
      return;
    }

    const displayName =
      typeof displayNameValue === "string" && displayNameValue.trim()
        ? displayNameValue.trim()
        : defaultDisplayName(file.name);

    try {
      setStage("hashing");
      const contentSha256 = await sha256Hex(file);

      const intent = await startSourceUploadAction({
        projectId,
        originalFilename: file.name,
        displayName,
        format,
        byteSize: file.size,
        contentSha256,
      });

      if (!intent.ok) {
        setStage("idle");
        setMessage(errorCopy[intent.error]);
        return;
      }

      setStage("uploading");
      const uploadResponse = await fetch(intent.uploadUrl, {
        method: "PUT",
        body: file,
        headers: intent.requiredHeaders,
      });

      if (!uploadResponse.ok) {
        setStage("idle");
        setMessage(errorCopy.upload_failed);
        return;
      }

      setStage("verifying");
      const completion = await completeSourceUploadAction(projectId, intent.sourceId);
      if (!completion.ok) {
        setStage("idle");
        setMessage(errorCopy[completion.error]);
        return;
      }

      setStage("queued");
      setMessage(
        completion.jobId
          ? "Source verified. Deterministic ingestion is queued outside the web request."
          : "Source verified. Existing ingestion state was preserved.",
      );
      form.reset();
      router.refresh();
    } catch {
      setStage("idle");
      setMessage(errorCopy.unavailable);
    }
  }

  const stageCopy: Record<UploadStage, string> = {
    idle: "Upload source",
    hashing: "Fingerprinting…",
    uploading: "Uploading…",
    verifying: "Verifying…",
    queued: "Upload another",
  };

  return (
    <form onSubmit={onSubmit} className="grid gap-4 border-b border-[var(--app-separator)] py-6">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] lg:items-end">
        <label className="grid gap-1 text-xs font-medium text-[var(--app-muted)]">
          Story source
          <input
            required
            type="file"
            name="source"
            accept=".txt,.epub,text/plain,application/epub+zip"
            disabled={busy}
            className="min-h-11 rounded-lg border border-[var(--app-separator)] bg-[var(--app-surface)] px-3 py-2 text-sm text-[var(--app-text)] file:mr-3 file:rounded-md file:border-0 file:bg-[var(--app-text)] file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-[var(--app-canvas)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)] disabled:opacity-60"
          />
        </label>

        <label className="grid gap-1 text-xs font-medium text-[var(--app-muted)]">
          Display name
          <input
            type="text"
            name="displayName"
            maxLength={512}
            disabled={busy}
            placeholder="Defaults to the filename"
            className="min-h-11 rounded-lg border border-[var(--app-separator)] bg-[var(--app-surface)] px-3 text-sm text-[var(--app-text)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)] disabled:opacity-60"
          />
        </label>

        <button
          type="submit"
          disabled={busy}
          className="min-h-11 rounded-lg bg-[var(--app-text)] px-4 text-sm font-semibold text-[var(--app-canvas)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)] disabled:cursor-not-allowed disabled:opacity-60"
        >
          {stageCopy[stage]}
        </button>
      </div>

      <p className="text-xs leading-5 text-[var(--app-muted)]">
        Supported now: UTF-8 plain text and EPUB. Your browser fingerprints the file first, then uploads it directly to S.A.G.A.&apos;s private object store using a short-lived URL. The worker verifies the actual bytes again before normalization succeeds.
      </p>

      {message ? (
        <p role="status" className="text-sm leading-6 text-[var(--app-muted)]">
          {message}
        </p>
      ) : null}
    </form>
  );
}
