import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";

import type { NormalizedSection } from "../ingestion/types.js";
import type { IdentityProviderDescriptor } from "../identity/types.js";
import type {
  LocalLiteraryAnalysisInput,
  LocalLiteraryEvidenceBundle,
  LocalLiteraryEvidenceProvider,
  LocalLiteraryProviderHealth,
} from "./types.js";
import {
  sameProviderDescriptor,
  validateLocalLiteraryEvidenceBundle,
  validateProviderDescriptor,
} from "./validation.js";

export const LOCAL_LITERARY_SUBPROCESS_PROTOCOL_VERSION = "saga-local-literary-subprocess-v1";

export type LocalLiterarySectionDescriptor = Omit<NormalizedSection, "normalized_text">;

export type LocalLiteraryHealthRequest = {
  schemaVersion: "saga-local-literary-request-v1";
  kind: "health";
  requestId: string;
  protocolVersion: typeof LOCAL_LITERARY_SUBPROCESS_PROTOCOL_VERSION;
  configurationFingerprint: string;
};

export type LocalLiteraryAnalyzeRequest = {
  schemaVersion: "saga-local-literary-request-v1";
  kind: "analyze";
  requestId: string;
  protocolVersion: typeof LOCAL_LITERARY_SUBPROCESS_PROTOCOL_VERSION;
  configurationFingerprint: string;
  normalizedInputFingerprint: string;
  normalizedText: string;
  sections: LocalLiterarySectionDescriptor[];
};

export type LocalLiterarySubprocessRequest = LocalLiteraryHealthRequest | LocalLiteraryAnalyzeRequest;

export type LocalLiteraryHealthResponse = {
  schemaVersion: "saga-local-literary-response-v1";
  kind: "health";
  requestId: string;
  protocolVersion: typeof LOCAL_LITERARY_SUBPROCESS_PROTOCOL_VERSION;
  configurationFingerprint: string;
  provider: IdentityProviderDescriptor;
  status: "ok";
};

export type LocalLiteraryAnalyzeResponse = {
  schemaVersion: "saga-local-literary-response-v1";
  kind: "analyze";
  requestId: string;
  protocolVersion: typeof LOCAL_LITERARY_SUBPROCESS_PROTOCOL_VERSION;
  configurationFingerprint: string;
  provider: IdentityProviderDescriptor;
  normalizedInputFingerprint: string;
  evidence: unknown;
};

export type LocalLiteraryErrorResponse = {
  schemaVersion: "saga-local-literary-response-v1";
  kind: "error";
  requestId: string;
  protocolVersion: typeof LOCAL_LITERARY_SUBPROCESS_PROTOCOL_VERSION;
  configurationFingerprint: string;
  provider: IdentityProviderDescriptor;
  error: {
    code: string;
    retryable: boolean;
  };
};

export class LocalLiteraryProviderError extends Error {
  readonly code: string;
  readonly retryable: boolean;

  constructor(code: string, retryable: boolean) {
    super(code);
    this.name = "LocalLiteraryProviderError";
    this.code = code;
    this.retryable = retryable;
  }
}

const SAFE_INHERITED_ENVIRONMENT_KEYS = [
  "PATH",
  "Path",
  "HOME",
  "USERPROFILE",
  "TMP",
  "TEMP",
  "TMPDIR",
  "SystemRoot",
  "WINDIR",
  "COMSPEC",
  "PATHEXT",
  "LANG",
  "LC_ALL",
  "VIRTUAL_ENV",
] as const;

export function sanitizedSubprocessEnvironment(
  source: NodeJS.ProcessEnv = process.env,
  overrides: Record<string, string> = {},
) {
  const result: Record<string, string> = {};
  for (const key of SAFE_INHERITED_ENVIRONMENT_KEYS) {
    const value = source[key];
    if (value) result[key] = value;
  }
  for (const [key, value] of Object.entries(overrides)) {
    if (!key.trim() || key.includes("=") || key.includes("\u0000") || value.includes("\u0000")) {
      throw new Error("invalid_local_provider_environment_override");
    }
    result[key] = value;
  }
  return result;
}

function requireFingerprint(value: string, code: string) {
  if (!/^[0-9a-f]{64}$/u.test(value)) throw new Error(code);
}

function sectionDescriptor(section: NormalizedSection): LocalLiterarySectionDescriptor {
  return {
    stable_key: section.stable_key,
    ordinal: section.ordinal,
    section_kind: section.section_kind,
    title: section.title,
    source_locator: section.source_locator,
    start_offset: section.start_offset,
    end_offset: section.end_offset,
  };
}

function responseRecord(value: unknown) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new LocalLiteraryProviderError("local_provider_invalid_response", false);
  }
  return value as Record<string, unknown>;
}

function providerReportedError(row: Record<string, unknown>) {
  if (!row.error || typeof row.error !== "object" || Array.isArray(row.error)) {
    throw new LocalLiteraryProviderError("local_provider_invalid_error_response", false);
  }
  const error = row.error as Record<string, unknown>;
  if (
    typeof error.code !== "string" ||
    error.code.length === 0 ||
    error.code.length > 128 ||
    !/^[A-Za-z0-9_.:-]+$/u.test(error.code) ||
    typeof error.retryable !== "boolean"
  ) {
    throw new LocalLiteraryProviderError("local_provider_invalid_error_response", false);
  }
  throw new LocalLiteraryProviderError(`local_provider_reported:${error.code}`, error.retryable);
}

export class SubprocessLocalLiteraryEvidenceProvider implements LocalLiteraryEvidenceProvider {
  readonly descriptor: IdentityProviderDescriptor;
  readonly configurationFingerprint: string;
  readonly #executable: string;
  readonly #args: string[];
  readonly #cwd: string | null;
  readonly #environment: Record<string, string>;
  readonly #timeoutMs: number;
  readonly #maxStdinBytes: number;
  readonly #maxStdoutBytes: number;
  readonly #maxStderrBytes: number;

  constructor(input: {
    executable: string;
    args?: string[];
    cwd?: string | null;
    descriptor: IdentityProviderDescriptor;
    configurationFingerprint: string;
    environment?: Record<string, string>;
    timeoutMs?: number;
    maxStdinBytes?: number;
    maxStdoutBytes?: number;
    maxStderrBytes?: number;
  }) {
    if (!input.executable.trim() || input.executable.includes("\u0000")) {
      throw new Error("local_provider_executable_required");
    }
    const descriptor = validateProviderDescriptor(input.descriptor);
    requireFingerprint(input.configurationFingerprint, "invalid_local_provider_configuration_fingerprint");
    const args = [...(input.args ?? [])];
    if (args.some((value) => value.includes("\u0000"))) throw new Error("invalid_local_provider_argument");
    if (input.cwd?.includes("\u0000")) throw new Error("invalid_local_provider_cwd");

    const timeoutMs = input.timeoutMs ?? 900_000;
    const maxStdinBytes = input.maxStdinBytes ?? 64 * 1024 * 1024;
    const maxStdoutBytes = input.maxStdoutBytes ?? 64 * 1024 * 1024;
    const maxStderrBytes = input.maxStderrBytes ?? 1024 * 1024;
    if (!Number.isSafeInteger(timeoutMs) || timeoutMs < 1_000 || timeoutMs > 7_200_000) {
      throw new Error("invalid_local_provider_timeout");
    }
    if (!Number.isSafeInteger(maxStdinBytes) || maxStdinBytes < 1_024 || maxStdinBytes > 512 * 1024 * 1024) {
      throw new Error("invalid_local_provider_stdin_limit");
    }
    if (!Number.isSafeInteger(maxStdoutBytes) || maxStdoutBytes < 1_024 || maxStdoutBytes > 256 * 1024 * 1024) {
      throw new Error("invalid_local_provider_stdout_limit");
    }
    if (!Number.isSafeInteger(maxStderrBytes) || maxStderrBytes < 1_024 || maxStderrBytes > 16 * 1024 * 1024) {
      throw new Error("invalid_local_provider_stderr_limit");
    }

    this.#executable = input.executable;
    this.#args = args;
    this.#cwd = input.cwd ?? null;
    this.descriptor = descriptor;
    this.configurationFingerprint = input.configurationFingerprint;
    this.#environment = sanitizedSubprocessEnvironment(process.env, input.environment ?? {});
    this.#timeoutMs = timeoutMs;
    this.#maxStdinBytes = maxStdinBytes;
    this.#maxStdoutBytes = maxStdoutBytes;
    this.#maxStderrBytes = maxStderrBytes;
  }

  async health(): Promise<LocalLiteraryProviderHealth> {
    const request: LocalLiteraryHealthRequest = {
      schemaVersion: "saga-local-literary-request-v1",
      kind: "health",
      requestId: randomUUID(),
      protocolVersion: LOCAL_LITERARY_SUBPROCESS_PROTOCOL_VERSION,
      configurationFingerprint: this.configurationFingerprint,
    };
    const response = this.#validateResponse(await this.#run(request), request, "health");
    if (response.status !== "ok") {
      throw new LocalLiteraryProviderError("local_provider_health_not_ok", false);
    }
    return {
      status: "ok",
      provider: this.descriptor,
      protocolVersion: LOCAL_LITERARY_SUBPROCESS_PROTOCOL_VERSION,
      configurationFingerprint: this.configurationFingerprint,
    };
  }

  async analyze(input: LocalLiteraryAnalysisInput): Promise<LocalLiteraryEvidenceBundle> {
    requireFingerprint(input.normalizedInputFingerprint, "invalid_local_analysis_input_fingerprint");
    const request: LocalLiteraryAnalyzeRequest = {
      schemaVersion: "saga-local-literary-request-v1",
      kind: "analyze",
      requestId: randomUUID(),
      protocolVersion: LOCAL_LITERARY_SUBPROCESS_PROTOCOL_VERSION,
      configurationFingerprint: this.configurationFingerprint,
      normalizedInputFingerprint: input.normalizedInputFingerprint,
      normalizedText: input.normalizedText,
      sections: input.sections.map(sectionDescriptor),
    };
    const response = this.#validateResponse(await this.#run(request), request, "analyze");
    if (response.normalizedInputFingerprint !== input.normalizedInputFingerprint) {
      throw new LocalLiteraryProviderError("local_provider_input_fingerprint_mismatch", false);
    }
    try {
      return validateLocalLiteraryEvidenceBundle({
        evidence: response.evidence,
        source: input,
        expectedProvider: this.descriptor,
      });
    } catch (error) {
      const code = error instanceof Error ? error.message : "unknown";
      throw new LocalLiteraryProviderError(`local_provider_invalid_evidence:${code}`, false);
    }
  }

  #validateResponse(
    payload: unknown,
    request: LocalLiterarySubprocessRequest,
    expectedKind: "health",
  ): LocalLiteraryHealthResponse;
  #validateResponse(
    payload: unknown,
    request: LocalLiterarySubprocessRequest,
    expectedKind: "analyze",
  ): LocalLiteraryAnalyzeResponse;
  #validateResponse(
    payload: unknown,
    request: LocalLiterarySubprocessRequest,
    expectedKind: "health" | "analyze",
  ): LocalLiteraryHealthResponse | LocalLiteraryAnalyzeResponse {
    const row = responseRecord(payload);
    if (
      row.schemaVersion !== "saga-local-literary-response-v1" ||
      row.requestId !== request.requestId ||
      row.protocolVersion !== LOCAL_LITERARY_SUBPROCESS_PROTOCOL_VERSION ||
      row.configurationFingerprint !== this.configurationFingerprint
    ) {
      throw new LocalLiteraryProviderError("local_provider_protocol_mismatch", false);
    }
    const provider = validateProviderDescriptor(row.provider);
    if (!sameProviderDescriptor(provider, this.descriptor)) {
      throw new LocalLiteraryProviderError("local_provider_descriptor_mismatch", false);
    }
    if (row.kind === "error") providerReportedError(row);
    if (row.kind !== expectedKind) {
      throw new LocalLiteraryProviderError("local_provider_protocol_mismatch", false);
    }
    if (expectedKind === "health") {
      if (row.status !== "ok") throw new LocalLiteraryProviderError("local_provider_health_not_ok", false);
      return payload as LocalLiteraryHealthResponse;
    }
    if (typeof row.normalizedInputFingerprint !== "string") {
      throw new LocalLiteraryProviderError("local_provider_missing_input_fingerprint", false);
    }
    if (!("evidence" in row)) {
      throw new LocalLiteraryProviderError("local_provider_missing_evidence", false);
    }
    return payload as LocalLiteraryAnalyzeResponse;
  }

  #run(request: LocalLiterarySubprocessRequest): Promise<unknown> {
    const serializedRequest = `${JSON.stringify(request)}\n`;
    if (Buffer.byteLength(serializedRequest, "utf8") > this.#maxStdinBytes) {
      return Promise.reject(new LocalLiteraryProviderError("local_provider_stdin_limit_exceeded", false));
    }

    return new Promise((resolve, reject) => {
      let settled = false;
      let stdoutBytes = 0;
      let stderrBytes = 0;
      const stdoutChunks: Buffer[] = [];

      const child = spawn(this.#executable, this.#args, {
        shell: false,
        stdio: ["pipe", "pipe", "pipe"],
        env: this.#environment,
        ...(this.#cwd ? { cwd: this.#cwd } : {}),
      });

      let timer: NodeJS.Timeout | null = null;
      const finishReject = (error: LocalLiteraryProviderError) => {
        if (settled) return;
        settled = true;
        if (timer) clearTimeout(timer);
        reject(error);
      };

      timer = setTimeout(() => {
        child.kill("SIGKILL");
        finishReject(new LocalLiteraryProviderError("local_provider_timeout", true));
      }, this.#timeoutMs);

      child.on("error", (error: NodeJS.ErrnoException) => {
        const retryable = error.code === "EAGAIN" || error.code === "ENOMEM";
        finishReject(new LocalLiteraryProviderError("local_provider_spawn_failed", retryable));
      });

      child.stdout.on("data", (chunk: Buffer | string) => {
        const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
        stdoutBytes += buffer.length;
        if (stdoutBytes > this.#maxStdoutBytes) {
          child.kill("SIGKILL");
          finishReject(new LocalLiteraryProviderError("local_provider_stdout_limit_exceeded", false));
          return;
        }
        stdoutChunks.push(buffer);
      });

      child.stderr.on("data", (chunk: Buffer | string) => {
        const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
        stderrBytes += buffer.length;
        if (stderrBytes > this.#maxStderrBytes) {
          child.kill("SIGKILL");
          finishReject(new LocalLiteraryProviderError("local_provider_stderr_limit_exceeded", false));
        }
      });

      child.stdin.on("error", () => {
        finishReject(new LocalLiteraryProviderError("local_provider_stdin_failed", true));
      });

      child.on("close", (code, signal) => {
        if (settled) return;
        if (timer) clearTimeout(timer);
        if (code !== 0) {
          finishReject(
            new LocalLiteraryProviderError(
              `local_provider_exit:${code === null ? signal ?? "unknown" : String(code)}`,
              true,
            ),
          );
          return;
        }
        let payload: unknown;
        try {
          payload = JSON.parse(Buffer.concat(stdoutChunks).toString("utf8").trim());
        } catch {
          finishReject(new LocalLiteraryProviderError("local_provider_invalid_json", false));
          return;
        }
        settled = true;
        resolve(payload);
      });

      child.stdin.end(serializedRequest, "utf8");
    });
  }
}
