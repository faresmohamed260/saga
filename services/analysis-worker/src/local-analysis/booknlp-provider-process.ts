import { spawn } from "node:child_process";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import type { NormalizedSection } from "../ingestion/types.js";
import { codePointSlice, normalizeBookNlpOutput } from "./booknlp-output.js";
import {
  BOOKNLP_EXPECTED_PACKAGE_VERSION,
  BOOKNLP_SMALL_PROVIDER,
  bookNlpRuntimeConfigurationFingerprint,
} from "./booknlp-provider.js";
import {
  LOCAL_LITERARY_SUBPROCESS_PROTOCOL_VERSION,
  sanitizedSubprocessEnvironment,
  type LocalLiteraryAnalyzeRequest,
  type LocalLiterarySubprocessRequest,
} from "./subprocess-provider.js";

const REQUEST_SCHEMA_VERSION = "saga-local-literary-request-v1";
const RESPONSE_SCHEMA_VERSION = "saga-local-literary-response-v1";
const DEFAULT_RUNNER_TIMEOUT_MS = 900_000;
const DEFAULT_RUNNER_STDOUT_BYTES = 1024 * 1024;
const DEFAULT_RUNNER_STDERR_BYTES = 1024 * 1024;
const BOOK_ID = "saga";

class BookNlpProviderProcessError extends Error {
  readonly code: string;
  readonly retryable: boolean;

  constructor(code: string, retryable: boolean) {
    super(code);
    this.name = "BookNlpProviderProcessError";
    this.code = code;
    this.retryable = retryable;
  }
}

type RunnerConfiguration = {
  executable: string;
  args: string[];
  modelPath: string;
  configurationFingerprint: string;
  timeoutMs: number;
  maxStdoutBytes: number;
  maxStderrBytes: number;
};

function boundedInteger(name: string, fallback: number, min: number, max: number) {
  const raw = process.env[name]?.trim();
  if (!raw) return fallback;
  const value = Number(raw);
  if (!Number.isSafeInteger(value) || value < min || value > max) {
    throw new BookNlpProviderProcessError(`booknlp_invalid_configuration_${name.toLocaleLowerCase("en-US")}`, false);
  }
  return value;
}

function requiredRuntimeValue(name: string, errorCode: string) {
  const value = process.env[name]?.trim();
  if (!value || value.includes("\u0000")) {
    throw new BookNlpProviderProcessError(errorCode, false);
  }
  return value;
}

function parseRunnerConfiguration(): RunnerConfiguration {
  const executable = requiredRuntimeValue("SAGA_BOOKNLP_RUNNER_EXECUTABLE", "booknlp_runner_not_configured");
  const modelPath = requiredRuntimeValue("SAGA_BOOKNLP_MODEL_DIR", "booknlp_model_path_not_configured");

  let args: unknown = [];
  const rawArgs = process.env.SAGA_BOOKNLP_RUNNER_ARGS_JSON?.trim();
  if (rawArgs) {
    try {
      args = JSON.parse(rawArgs);
    } catch {
      throw new BookNlpProviderProcessError("booknlp_runner_args_invalid_json", false);
    }
  }
  if (!Array.isArray(args) || args.some((value) => typeof value !== "string" || value.includes("\u0000"))) {
    throw new BookNlpProviderProcessError("booknlp_runner_args_invalid", false);
  }

  return {
    executable,
    args: args as string[],
    modelPath,
    configurationFingerprint: bookNlpRuntimeConfigurationFingerprint({
      runnerExecutable: executable,
      runnerArgs: args as string[],
      modelPath,
    }),
    timeoutMs: boundedInteger("SAGA_BOOKNLP_RUNNER_TIMEOUT_MS", DEFAULT_RUNNER_TIMEOUT_MS, 1_000, 7_200_000),
    maxStdoutBytes: boundedInteger(
      "SAGA_BOOKNLP_RUNNER_STDOUT_BYTES",
      DEFAULT_RUNNER_STDOUT_BYTES,
      1_024,
      16 * 1024 * 1024,
    ),
    maxStderrBytes: boundedInteger(
      "SAGA_BOOKNLP_RUNNER_STDERR_BYTES",
      DEFAULT_RUNNER_STDERR_BYTES,
      1_024,
      16 * 1024 * 1024,
    ),
  };
}

function runnerEnvironment() {
  const overrides: Record<string, string> = {
    HF_HUB_OFFLINE: "1",
    TRANSFORMERS_OFFLINE: "1",
    TOKENIZERS_PARALLELISM: "false",
    CUDA_VISIBLE_DEVICES: "",
  };
  for (const key of ["HF_HOME", "TRANSFORMERS_CACHE", "TORCH_HOME", "XDG_CACHE_HOME"] as const) {
    const value = process.env[key]?.trim();
    if (value) overrides[key] = value;
  }
  return sanitizedSubprocessEnvironment(process.env, overrides);
}

function parseRequest(raw: string): LocalLiterarySubprocessRequest {
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    throw new BookNlpProviderProcessError("booknlp_invalid_request_json", false);
  }
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new BookNlpProviderProcessError("booknlp_invalid_request", false);
  }
  const request = value as Record<string, unknown>;
  if (
    request.schemaVersion !== REQUEST_SCHEMA_VERSION ||
    request.protocolVersion !== LOCAL_LITERARY_SUBPROCESS_PROTOCOL_VERSION ||
    typeof request.requestId !== "string" ||
    !request.requestId.trim() ||
    typeof request.configurationFingerprint !== "string" ||
    !/^[0-9a-f]{64}$/u.test(request.configurationFingerprint) ||
    (request.kind !== "health" && request.kind !== "analyze")
  ) {
    throw new BookNlpProviderProcessError("booknlp_invalid_request", false);
  }
  return value as LocalLiterarySubprocessRequest;
}

function validateAnalyzeRequest(request: LocalLiteraryAnalyzeRequest) {
  if (
    typeof request.normalizedInputFingerprint !== "string" ||
    !/^[0-9a-f]{64}$/u.test(request.normalizedInputFingerprint) ||
    typeof request.normalizedText !== "string" ||
    !Array.isArray(request.sections)
  ) {
    throw new BookNlpProviderProcessError("booknlp_invalid_analyze_request", false);
  }
}

function normalizedSections(request: LocalLiteraryAnalyzeRequest): NormalizedSection[] {
  const sourceLength = Array.from(request.normalizedText).length;
  return request.sections.map((section, index) => {
    if (
      !section ||
      typeof section !== "object" ||
      typeof section.stable_key !== "string" ||
      !section.stable_key ||
      !Number.isSafeInteger(section.ordinal) ||
      (section.section_kind !== "document" && section.section_kind !== "chapter" && section.section_kind !== "section") ||
      (section.title !== null && typeof section.title !== "string") ||
      typeof section.source_locator !== "string" ||
      !Number.isSafeInteger(section.start_offset) ||
      !Number.isSafeInteger(section.end_offset) ||
      section.start_offset < 0 ||
      section.end_offset < section.start_offset ||
      section.end_offset > sourceLength
    ) {
      throw new BookNlpProviderProcessError(`booknlp_invalid_section:${index}`, false);
    }
    return {
      stable_key: section.stable_key,
      ordinal: section.ordinal,
      section_kind: section.section_kind,
      title: section.title,
      source_locator: section.source_locator,
      start_offset: section.start_offset,
      end_offset: section.end_offset,
      normalized_text: codePointSlice(request.normalizedText, section.start_offset, section.end_offset),
    };
  });
}

type RunnerResult = { stdout: string };

function runBookNlpRunner(config: RunnerConfiguration, args: string[]): Promise<RunnerResult> {
  return new Promise((resolve, reject) => {
    let settled = false;
    let stdoutBytes = 0;
    let stderrBytes = 0;
    const stdoutChunks: Buffer[] = [];

    const child = spawn(config.executable, [...config.args, ...args], {
      shell: false,
      stdio: ["ignore", "pipe", "pipe"],
      env: runnerEnvironment(),
    });

    let timer: NodeJS.Timeout | null = null;
    const fail = (error: BookNlpProviderProcessError) => {
      if (settled) return;
      settled = true;
      if (timer) clearTimeout(timer);
      reject(error);
    };

    timer = setTimeout(() => {
      child.kill("SIGKILL");
      fail(new BookNlpProviderProcessError("booknlp_runner_timeout", true));
    }, config.timeoutMs);

    child.on("error", (error: NodeJS.ErrnoException) => {
      fail(new BookNlpProviderProcessError(
        "booknlp_runner_spawn_failed",
        error.code === "EAGAIN" || error.code === "ENOMEM",
      ));
    });

    child.stdout.on("data", (chunk: Buffer | string) => {
      const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
      stdoutBytes += buffer.length;
      if (stdoutBytes > config.maxStdoutBytes) {
        child.kill("SIGKILL");
        fail(new BookNlpProviderProcessError("booknlp_runner_stdout_limit_exceeded", false));
        return;
      }
      stdoutChunks.push(buffer);
    });

    child.stderr.on("data", (chunk: Buffer | string) => {
      const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
      stderrBytes += buffer.length;
      if (stderrBytes > config.maxStderrBytes) {
        child.kill("SIGKILL");
        fail(new BookNlpProviderProcessError("booknlp_runner_stderr_limit_exceeded", false));
      }
    });

    child.on("close", (code) => {
      if (settled) return;
      if (timer) clearTimeout(timer);
      if (code !== 0) {
        fail(new BookNlpProviderProcessError(`booknlp_runner_exit_${code ?? "signal"}`, false));
        return;
      }
      settled = true;
      resolve({ stdout: Buffer.concat(stdoutChunks).toString("utf8").trim() });
    });
  });
}

async function verifyRunner(config: RunnerConfiguration) {
  const result = await runBookNlpRunner(config, ["--health", "--model-path", config.modelPath]);
  let payload: unknown;
  try {
    payload = JSON.parse(result.stdout);
  } catch {
    throw new BookNlpProviderProcessError("booknlp_runner_health_invalid_json", false);
  }
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new BookNlpProviderProcessError("booknlp_runner_health_invalid_payload", false);
  }
  const version = (payload as Record<string, unknown>).booknlpVersion;
  if (version !== BOOKNLP_EXPECTED_PACKAGE_VERSION) {
    throw new BookNlpProviderProcessError("booknlp_runner_version_mismatch", false);
  }
}

async function analyze(request: LocalLiteraryAnalyzeRequest, config: RunnerConfiguration) {
  validateAnalyzeRequest(request);
  const sections = normalizedSections(request);
  const workspace = await mkdtemp(join(tmpdir(), "saga-booknlp-"));
  const inputPath = join(workspace, "input.txt");
  const outputDir = join(workspace, "output");
  try {
    await mkdir(outputDir, { recursive: true });
    await writeFile(inputPath, request.normalizedText, "utf8");
    await runBookNlpRunner(config, [
      "--input",
      inputPath,
      "--output",
      outputDir,
      "--book-id",
      BOOK_ID,
      "--model-path",
      config.modelPath,
    ]);
    const [tokensTsv, entitiesTsv, quotesTsv] = await Promise.all([
      readFile(join(outputDir, `${BOOK_ID}.tokens`), "utf8"),
      readFile(join(outputDir, `${BOOK_ID}.entities`), "utf8"),
      readFile(join(outputDir, `${BOOK_ID}.quotes`), "utf8"),
    ]).catch(() => {
      throw new BookNlpProviderProcessError("booknlp_runner_missing_outputs", false);
    });

    return normalizeBookNlpOutput({
      normalizedInputFingerprint: request.normalizedInputFingerprint,
      normalizedText: request.normalizedText,
      sections,
      provider: BOOKNLP_SMALL_PROVIDER,
      tokensTsv,
      entitiesTsv,
      quotesTsv,
    });
  } finally {
    await rm(workspace, { recursive: true, force: true });
  }
}

function writeResponse(value: unknown) {
  process.stdout.write(`${JSON.stringify(value)}\n`);
}

function errorCode(error: unknown) {
  if (error instanceof BookNlpProviderProcessError) return error;
  if (error instanceof Error && /^booknlp_[A-Za-z0-9_.:-]+$/u.test(error.message)) {
    return new BookNlpProviderProcessError(error.message, false);
  }
  return new BookNlpProviderProcessError("booknlp_provider_internal_error", false);
}

async function main() {
  let request: LocalLiterarySubprocessRequest | null = null;
  let raw = "";
  for await (const chunk of process.stdin) raw += chunk;

  try {
    request = parseRequest(raw);
    const config = parseRunnerConfiguration();
    if (request.configurationFingerprint !== config.configurationFingerprint) {
      throw new BookNlpProviderProcessError("booknlp_configuration_fingerprint_mismatch", false);
    }

    if (request.kind === "health") {
      await verifyRunner(config);
      writeResponse({
        schemaVersion: RESPONSE_SCHEMA_VERSION,
        kind: "health",
        requestId: request.requestId,
        protocolVersion: LOCAL_LITERARY_SUBPROCESS_PROTOCOL_VERSION,
        configurationFingerprint: request.configurationFingerprint,
        provider: BOOKNLP_SMALL_PROVIDER,
        status: "ok",
      });
      return;
    }

    const evidence = await analyze(request, config);
    writeResponse({
      schemaVersion: RESPONSE_SCHEMA_VERSION,
      kind: "analyze",
      requestId: request.requestId,
      protocolVersion: LOCAL_LITERARY_SUBPROCESS_PROTOCOL_VERSION,
      configurationFingerprint: request.configurationFingerprint,
      provider: BOOKNLP_SMALL_PROVIDER,
      normalizedInputFingerprint: request.normalizedInputFingerprint,
      evidence,
    });
  } catch (caught) {
    const failure = errorCode(caught);
    if (!request) throw failure;
    writeResponse({
      schemaVersion: RESPONSE_SCHEMA_VERSION,
      kind: "error",
      requestId: request.requestId,
      protocolVersion: LOCAL_LITERARY_SUBPROCESS_PROTOCOL_VERSION,
      configurationFingerprint: request.configurationFingerprint,
      provider: BOOKNLP_SMALL_PROVIDER,
      error: { code: failure.code, retryable: failure.retryable },
    });
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
