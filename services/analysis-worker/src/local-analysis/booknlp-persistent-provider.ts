import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { randomUUID } from "node:crypto";

import { normalizeBookNlpOutput } from "./booknlp-output.js";
import {
  BOOKNLP_EXPECTED_PACKAGE_VERSION,
  BOOKNLP_PERSISTENT_RUNNER_PROTOCOL_VERSION,
  BOOKNLP_SMALL_PROVIDER,
  bookNlpPersistentRuntimeConfigurationFingerprint,
} from "./booknlp-provider.js";
import {
  LocalLiteraryProviderError,
  sanitizedSubprocessEnvironment,
} from "./subprocess-provider.js";
import type {
  LocalLiteraryAnalysisInput,
  LocalLiteraryEvidenceBundle,
  LocalLiteraryEvidenceProvider,
  LocalLiteraryProviderHealth,
} from "./types.js";
import { validateLocalLiteraryEvidenceBundle } from "./validation.js";

const REQUEST_SCHEMA_VERSION = "saga-booknlp-persistent-request-v1";
const RESPONSE_SCHEMA_VERSION = "saga-booknlp-persistent-response-v1";
const DEFAULT_TIMEOUT_MS = 900_000;
const DEFAULT_STDIN_BYTES = 64 * 1024 * 1024;
const DEFAULT_STDOUT_BYTES = 64 * 1024 * 1024;
const DEFAULT_STDERR_BYTES = 4 * 1024 * 1024;
const BOOK_ID = "saga";

type PersistentRequest =
  | {
      schemaVersion: typeof REQUEST_SCHEMA_VERSION;
      protocolVersion: typeof BOOKNLP_PERSISTENT_RUNNER_PROTOCOL_VERSION;
      kind: "health" | "shutdown";
      requestId: string;
      configurationFingerprint: string;
    }
  | {
      schemaVersion: typeof REQUEST_SCHEMA_VERSION;
      protocolVersion: typeof BOOKNLP_PERSISTENT_RUNNER_PROTOCOL_VERSION;
      kind: "analyze";
      requestId: string;
      configurationFingerprint: string;
      normalizedInputFingerprint: string;
      normalizedText: string;
      bookId: typeof BOOK_ID;
    };

type PendingRequest = {
  requestId: string;
  resolve: (payload: unknown) => void;
  reject: (error: LocalLiteraryProviderError) => void;
  timer: NodeJS.Timeout;
  stderrBytes: number;
};

function boundedInteger(value: number | undefined, fallback: number, min: number, max: number, code: string) {
  const selected = value ?? fallback;
  if (!Number.isSafeInteger(selected) || selected < min || selected > max) throw new Error(code);
  return selected;
}

function record(value: unknown, code: string) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new LocalLiteraryProviderError(code, false);
  }
  return value as Record<string, unknown>;
}

function validErrorResponse(row: Record<string, unknown>) {
  const error = record(row.error, "booknlp_persistent_invalid_error_response");
  if (
    typeof error.code !== "string" ||
    error.code.length === 0 ||
    error.code.length > 128 ||
    !/^[A-Za-z0-9_.:-]+$/u.test(error.code) ||
    typeof error.retryable !== "boolean"
  ) {
    throw new LocalLiteraryProviderError("booknlp_persistent_invalid_error_response", false);
  }
  throw new LocalLiteraryProviderError(`booknlp_persistent_reported:${error.code}`, error.retryable);
}

export class PersistentBookNlpEvidenceProvider implements LocalLiteraryEvidenceProvider {
  readonly descriptor = BOOKNLP_SMALL_PROVIDER;
  readonly configurationFingerprint: string;

  readonly #runnerExecutable: string;
  readonly #runnerArgs: string[];
  readonly #modelPath: string;
  readonly #environment: Record<string, string>;
  readonly #timeoutMs: number;
  readonly #maxStdinBytes: number;
  readonly #maxStdoutBytes: number;
  readonly #maxStderrBytes: number;

  #child: ChildProcessWithoutNullStreams | null = null;
  #pending: PendingRequest | null = null;
  #stdoutBuffer = Buffer.alloc(0);
  #sequence: Promise<void> = Promise.resolve();
  #closing = false;
  #closed = false;
  #closePromise: Promise<void> | null = null;

  constructor(input: {
    runnerExecutable: string;
    runnerArgs?: string[];
    modelPath: string;
    environment?: Record<string, string>;
    timeoutMs?: number;
    maxStdinBytes?: number;
    maxStdoutBytes?: number;
    maxStderrBytes?: number;
  }) {
    if (!input.runnerExecutable.trim() || input.runnerExecutable.includes("\u0000")) {
      throw new Error("booknlp_persistent_runner_executable_required");
    }
    if (!input.modelPath.trim() || input.modelPath.includes("\u0000")) {
      throw new Error("booknlp_persistent_model_path_required");
    }
    const runnerArgs = [...(input.runnerArgs ?? [])];
    if (runnerArgs.some((value) => value.includes("\u0000"))) {
      throw new Error("booknlp_persistent_invalid_runner_argument");
    }

    this.#runnerExecutable = input.runnerExecutable;
    this.#runnerArgs = runnerArgs;
    this.#modelPath = input.modelPath;
    this.configurationFingerprint = bookNlpPersistentRuntimeConfigurationFingerprint({
      runnerExecutable: input.runnerExecutable,
      runnerArgs,
      modelPath: input.modelPath,
    });
    this.#environment = sanitizedSubprocessEnvironment(process.env, {
      ...(input.environment ?? {}),
      HF_HUB_OFFLINE: "1",
      TRANSFORMERS_OFFLINE: "1",
      TOKENIZERS_PARALLELISM: "false",
      CUDA_VISIBLE_DEVICES: "",
    });
    this.#timeoutMs = boundedInteger(input.timeoutMs, DEFAULT_TIMEOUT_MS, 1_000, 7_200_000, "booknlp_persistent_invalid_timeout");
    this.#maxStdinBytes = boundedInteger(
      input.maxStdinBytes,
      DEFAULT_STDIN_BYTES,
      1_024,
      512 * 1024 * 1024,
      "booknlp_persistent_invalid_stdin_limit",
    );
    this.#maxStdoutBytes = boundedInteger(
      input.maxStdoutBytes,
      DEFAULT_STDOUT_BYTES,
      1_024,
      256 * 1024 * 1024,
      "booknlp_persistent_invalid_stdout_limit",
    );
    this.#maxStderrBytes = boundedInteger(
      input.maxStderrBytes,
      DEFAULT_STDERR_BYTES,
      1_024,
      16 * 1024 * 1024,
      "booknlp_persistent_invalid_stderr_limit",
    );
  }

  async health(): Promise<LocalLiteraryProviderHealth> {
    this.#assertOpen();
    return this.#enqueue(async () => {
      const request = this.#baseRequest("health");
      const response = this.#validateCommon(await this.#request(request), request.requestId);
      if (response.kind === "error") validErrorResponse(response);
      if (
        response.kind !== "health" ||
        response.status !== "ok" ||
        response.booknlpVersion !== BOOKNLP_EXPECTED_PACKAGE_VERSION
      ) {
        throw new LocalLiteraryProviderError("booknlp_persistent_invalid_health_response", false);
      }
      return {
        status: "ok",
        provider: this.descriptor,
        protocolVersion: BOOKNLP_PERSISTENT_RUNNER_PROTOCOL_VERSION,
        configurationFingerprint: this.configurationFingerprint,
      };
    });
  }

  async analyze(input: LocalLiteraryAnalysisInput): Promise<LocalLiteraryEvidenceBundle> {
    this.#assertOpen();
    if (!/^[0-9a-f]{64}$/u.test(input.normalizedInputFingerprint)) {
      throw new LocalLiteraryProviderError("invalid_local_analysis_input_fingerprint", false);
    }
    return this.#enqueue(async () => {
      const request: PersistentRequest = {
        ...this.#baseRequest("analyze"),
        normalizedInputFingerprint: input.normalizedInputFingerprint,
        normalizedText: input.normalizedText,
        bookId: BOOK_ID,
      };
      const response = this.#validateCommon(await this.#request(request), request.requestId);
      if (response.kind === "error") validErrorResponse(response);
      if (
        response.kind !== "analyze" ||
        response.booknlpVersion !== BOOKNLP_EXPECTED_PACKAGE_VERSION ||
        response.normalizedInputFingerprint !== input.normalizedInputFingerprint ||
        typeof response.tokensTsv !== "string" ||
        typeof response.entitiesTsv !== "string" ||
        typeof response.quotesTsv !== "string"
      ) {
        throw new LocalLiteraryProviderError("booknlp_persistent_invalid_analyze_response", false);
      }

      const evidence = normalizeBookNlpOutput({
        normalizedInputFingerprint: input.normalizedInputFingerprint,
        normalizedText: input.normalizedText,
        sections: input.sections,
        provider: BOOKNLP_SMALL_PROVIDER,
        tokensTsv: response.tokensTsv,
        entitiesTsv: response.entitiesTsv,
        quotesTsv: response.quotesTsv,
      });
      try {
        return validateLocalLiteraryEvidenceBundle({
          evidence,
          source: input,
          expectedProvider: this.descriptor,
        });
      } catch (error) {
        const code = error instanceof Error ? error.message : "unknown";
        throw new LocalLiteraryProviderError(`booknlp_persistent_invalid_evidence:${code}`, false);
      }
    });
  }

  close(): Promise<void> {
    if (this.#closePromise) return this.#closePromise;
    this.#closing = true;
    this.#closePromise = this.#enqueue(async () => {
      const child = this.#child;
      if (!child) {
        this.#closed = true;
        return;
      }
      try {
        const request = this.#baseRequest("shutdown");
        const response = this.#validateCommon(await this.#request(request), request.requestId);
        if (response.kind === "error") validErrorResponse(response);
        if (
          response.kind !== "shutdown" ||
          response.status !== "ok" ||
          response.booknlpVersion !== BOOKNLP_EXPECTED_PACKAGE_VERSION
        ) {
          throw new LocalLiteraryProviderError("booknlp_persistent_invalid_shutdown_response", false);
        }
      } finally {
        this.#closed = true;
        child.stdin.end();
        if (!child.killed) child.kill("SIGTERM");
        if (this.#child === child) this.#child = null;
        this.#stdoutBuffer = Buffer.alloc(0);
      }
    }).finally(() => {
      this.#closed = true;
      this.#closing = false;
    });
    return this.#closePromise;
  }

  #assertOpen() {
    if (this.#closing || this.#closed) {
      throw new LocalLiteraryProviderError("booknlp_persistent_provider_closed", false);
    }
  }

  #baseRequest<K extends "health" | "analyze" | "shutdown">(kind: K) {
    return {
      schemaVersion: REQUEST_SCHEMA_VERSION,
      protocolVersion: BOOKNLP_PERSISTENT_RUNNER_PROTOCOL_VERSION,
      kind,
      requestId: randomUUID(),
      configurationFingerprint: this.configurationFingerprint,
    } as const;
  }

  #enqueue<T>(operation: () => Promise<T>): Promise<T> {
    const result = this.#sequence.then(operation, operation);
    this.#sequence = result.then(() => undefined, () => undefined);
    return result;
  }

  #ensureChild() {
    if (this.#child) return this.#child;
    this.#stdoutBuffer = Buffer.alloc(0);
    const child = spawn(
      this.#runnerExecutable,
      [
        ...this.#runnerArgs,
        "--model-path",
        this.#modelPath,
        "--configuration-fingerprint",
        this.configurationFingerprint,
      ],
      {
        shell: false,
        stdio: ["pipe", "pipe", "pipe"],
        env: this.#environment,
      },
    );
    this.#child = child;

    child.stdout.on("data", (chunk: Buffer | string) => this.#consumeStdout(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk)));
    child.stderr.on("data", (chunk: Buffer | string) => {
      const pending = this.#pending;
      if (!pending) return;
      pending.stderrBytes += Buffer.byteLength(chunk);
      if (pending.stderrBytes > this.#maxStderrBytes) {
        this.#failPending(new LocalLiteraryProviderError("booknlp_persistent_stderr_limit_exceeded", false));
        child.kill("SIGKILL");
      }
    });
    child.stdin.on("error", () => {
      this.#failPending(new LocalLiteraryProviderError("booknlp_persistent_stdin_failed", true));
    });
    child.on("error", (error: NodeJS.ErrnoException) => {
      this.#child = null;
      this.#failPending(new LocalLiteraryProviderError(
        "booknlp_persistent_spawn_failed",
        error.code === "EAGAIN" || error.code === "ENOMEM",
      ));
    });
    child.on("close", (code, signal) => {
      if (this.#child === child) this.#child = null;
      this.#stdoutBuffer = Buffer.alloc(0);
      if (this.#pending) {
        this.#failPending(new LocalLiteraryProviderError(
          `booknlp_persistent_exit:${code === null ? signal ?? "unknown" : String(code)}`,
          true,
        ));
      }
    });
    return child;
  }

  #request(request: PersistentRequest): Promise<unknown> {
    const serialized = `${JSON.stringify(request)}\n`;
    if (Buffer.byteLength(serialized, "utf8") > this.#maxStdinBytes) {
      return Promise.reject(new LocalLiteraryProviderError("booknlp_persistent_stdin_limit_exceeded", false));
    }
    if (this.#pending) {
      return Promise.reject(new LocalLiteraryProviderError("booknlp_persistent_concurrent_request", false));
    }

    const child = this.#ensureChild();
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.#failPending(new LocalLiteraryProviderError("booknlp_persistent_timeout", true));
        if (!child.killed) child.kill("SIGKILL");
      }, this.#timeoutMs);
      this.#pending = {
        requestId: request.requestId,
        resolve,
        reject,
        timer,
        stderrBytes: 0,
      };
      child.stdin.write(serialized, "utf8");
    });
  }

  #consumeStdout(chunk: Buffer) {
    this.#stdoutBuffer = Buffer.concat([this.#stdoutBuffer, chunk]);
    if (this.#stdoutBuffer.length > this.#maxStdoutBytes) {
      this.#failPending(new LocalLiteraryProviderError("booknlp_persistent_stdout_limit_exceeded", false));
      this.#child?.kill("SIGKILL");
      return;
    }

    while (true) {
      const newline = this.#stdoutBuffer.indexOf(0x0a);
      if (newline < 0) return;
      const line = this.#stdoutBuffer.subarray(0, newline).toString("utf8").trim();
      this.#stdoutBuffer = this.#stdoutBuffer.subarray(newline + 1);
      const pending = this.#pending;
      if (!pending) {
        this.#child?.kill("SIGKILL");
        return;
      }
      let payload: unknown;
      try {
        payload = JSON.parse(line);
      } catch {
        this.#failPending(new LocalLiteraryProviderError("booknlp_persistent_invalid_json", false));
        this.#child?.kill("SIGKILL");
        return;
      }
      clearTimeout(pending.timer);
      this.#pending = null;
      pending.resolve(payload);
      if (this.#stdoutBuffer.length > 0) this.#child?.kill("SIGKILL");
      return;
    }
  }

  #failPending(error: LocalLiteraryProviderError) {
    const pending = this.#pending;
    if (!pending) return;
    clearTimeout(pending.timer);
    this.#pending = null;
    pending.reject(error);
  }

  #validateCommon(payload: unknown, requestId: string) {
    const row = record(payload, "booknlp_persistent_invalid_response");
    if (
      row.schemaVersion !== RESPONSE_SCHEMA_VERSION ||
      row.protocolVersion !== BOOKNLP_PERSISTENT_RUNNER_PROTOCOL_VERSION ||
      row.requestId !== requestId ||
      row.configurationFingerprint !== this.configurationFingerprint ||
      typeof row.kind !== "string"
    ) {
      throw new LocalLiteraryProviderError("booknlp_persistent_protocol_mismatch", false);
    }
    return row;
  }
}
