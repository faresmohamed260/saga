import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { performance } from "node:perf_hooks";
import { fileURLToPath } from "node:url";

import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import { normalizeBookNlpOutput } from "../local-analysis/booknlp-output.js";
import {
  BOOKNLP_EXPECTED_PACKAGE_VERSION,
  BOOKNLP_SMALL_MODEL_FILES,
  BOOKNLP_SMALL_PROVIDER,
  bookNlpRuntimeConfigurationFingerprint,
} from "../local-analysis/booknlp-provider.js";
import { SubprocessLocalLiteraryEvidenceProvider } from "../local-analysis/subprocess-provider.js";
import type { LocalLiteraryEvidenceBundle } from "../local-analysis/types.js";
import { litBankDocumentSection } from "./litbank-component-benchmark.js";

const LITBANK_COMMIT = "3e50db0ffc033d7ccbb94f4d88f6b99210328ed8";
const DIRECT_BOOKNLP_SOURCE_RUN_ID = 34727310506;
const DIRECT_BOOKNLP_SOURCE_HEAD = "f77af8bcab488fd1069e9c6e8ed4970842c78692";
const DIRECT_BOOKNLP_ARTIFACT_SHA256 = "006875873bd58ec53cc976a46d000313107228f4d4dbf6c5dc450cf9b7ba4f6a";
const DEFAULT_DOCUMENT_ID = "1023_bleak_house_brat";
const EXPECTED_TRANSFORMER_MODELS = [
  "google/bert_uncased_L-4_H-256_A-4",
  "google/bert_uncased_L-2_H-256_A-4",
  "google/bert_uncased_L-8_H-256_A-4",
] as const;

const providerProcessPath = fileURLToPath(
  new URL("../local-analysis/booknlp-provider-process.ts", import.meta.url),
);
const defaultRunnerPath = fileURLToPath(new URL("../../providers/booknlp_runner.py", import.meta.url));

type PreparedArtifact = {
  name: string;
  sourceUrl: string;
  bytes: number;
  sha256: string;
};

type PreparedRuntimeManifest = {
  schemaVersion: "saga-booknlp-runtime-manifest-v1";
  model: "small";
  packages: {
    booknlp: string | null;
    spacy: string | null;
    spacyModel: string | null;
    torch: string | null;
    transformers: string | null;
  };
  booknlpArtifacts: PreparedArtifact[];
  booknlpArtifactBytes: number;
  transformerModels: Array<{
    modelId: string;
    tokenizerClass: string;
    modelClass: string;
  }>;
  transformerCache: {
    fileCount: number;
    bytes: number;
    manifestSha256: string;
  };
  spacyModel: {
    name: string;
    fileCount: number;
    bytes: number;
    manifestSha256: string;
  };
  totalPreparedArtifactBytes: number;
};

function parseArgs(argv: string[]) {
  let litbankRoot: string | null = null;
  let directOutputRoot: string | null = null;
  let modelDir: string | null = null;
  let hfHome: string | null = null;
  let runtimeManifest: string | null = null;
  let out: string | null = null;
  let runnerExecutable: string | null = null;
  let runnerPath = defaultRunnerPath;
  let documentId = DEFAULT_DOCUMENT_ID;

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === "--litbank-root") litbankRoot = argv[++index] ?? null;
    else if (token === "--direct-output-root") directOutputRoot = argv[++index] ?? null;
    else if (token === "--model-dir") modelDir = argv[++index] ?? null;
    else if (token === "--hf-home") hfHome = argv[++index] ?? null;
    else if (token === "--runtime-manifest") runtimeManifest = argv[++index] ?? null;
    else if (token === "--out") out = argv[++index] ?? null;
    else if (token === "--runner-executable") runnerExecutable = argv[++index] ?? null;
    else if (token === "--runner-path") runnerPath = argv[++index] ?? runnerPath;
    else if (token === "--document-id") documentId = argv[++index] ?? documentId;
    else throw new Error(`unknown argument: ${token}`);
  }

  if (!litbankRoot || !directOutputRoot || !modelDir || !hfHome || !runtimeManifest || !out || !runnerExecutable) {
    throw new Error(
      "usage: booknlp-subprocess-proof-cli --litbank-root <root> --direct-output-root <root> --model-dir <dir> --hf-home <dir> --runtime-manifest <manifest.json> --runner-executable <python> --out <report.json> [--runner-path <path>] [--document-id <id>]",
    );
  }

  return {
    litbankRoot: resolve(litbankRoot),
    directOutputRoot: resolve(directOutputRoot),
    modelDir: resolve(modelDir),
    hfHome: resolve(hfHome),
    runtimeManifest: resolve(runtimeManifest),
    out: resolve(out),
    runnerExecutable: resolve(runnerExecutable),
    runnerPath: resolve(runnerPath),
    documentId,
  };
}

function normalizeNewlines(value: string) {
  return value.replace(/\r\n?/gu, "\n");
}

function evidenceFingerprint(evidence: LocalLiteraryEvidenceBundle) {
  return sha256Hex(canonicalJson(evidence));
}

function evidenceCounts(evidence: LocalLiteraryEvidenceBundle) {
  return {
    identityMentions: evidence.identityEvidence.mentions.length,
    entities: evidence.entities.length,
    quotes: evidence.quotes.length,
    eventTriggers: evidence.eventTriggers.length,
    syntaxTokens: evidence.syntaxTokens?.length ?? 0,
  };
}

function requireNonNegativeInteger(value: unknown, code: string) {
  if (!Number.isSafeInteger(value) || (value as number) < 0) throw new Error(code);
  return value as number;
}

function requireDigest(value: unknown, code: string) {
  if (typeof value !== "string" || !/^[0-9a-f]{64}$/u.test(value)) throw new Error(code);
  return value;
}

function requireOptionalString(value: unknown, code: string): string | null {
  if (value === null) return null;
  if (typeof value !== "string" || !value) throw new Error(code);
  return value;
}

function requireCacheDescriptor(value: unknown, code: string) {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(code);
  const row = value as Record<string, unknown>;
  return {
    fileCount: requireNonNegativeInteger(row.fileCount, code),
    bytes: requireNonNegativeInteger(row.bytes, code),
    manifestSha256: requireDigest(row.manifestSha256, code),
  };
}

function requireRuntimeManifest(value: unknown): PreparedRuntimeManifest {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("invalid_booknlp_runtime_manifest");
  }
  const manifest = value as Record<string, unknown>;
  if (
    manifest.schemaVersion !== "saga-booknlp-runtime-manifest-v1" ||
    manifest.model !== "small" ||
    !manifest.packages ||
    typeof manifest.packages !== "object" ||
    Array.isArray(manifest.packages) ||
    !Array.isArray(manifest.booknlpArtifacts) ||
    !Array.isArray(manifest.transformerModels) ||
    !manifest.spacyModel ||
    typeof manifest.spacyModel !== "object" ||
    Array.isArray(manifest.spacyModel)
  ) {
    throw new Error("invalid_booknlp_runtime_manifest");
  }

  const packages = manifest.packages as Record<string, unknown>;
  const parsedPackages = {
    booknlp: requireOptionalString(packages.booknlp, "invalid_booknlp_runtime_package"),
    spacy: requireOptionalString(packages.spacy, "invalid_booknlp_runtime_package"),
    spacyModel: requireOptionalString(packages.spacyModel, "invalid_booknlp_runtime_package"),
    torch: requireOptionalString(packages.torch, "invalid_booknlp_runtime_package"),
    transformers: requireOptionalString(packages.transformers, "invalid_booknlp_runtime_package"),
  };
  if (parsedPackages.booknlp !== BOOKNLP_EXPECTED_PACKAGE_VERSION) {
    throw new Error("booknlp_runtime_manifest_package_version_mismatch");
  }

  const artifacts = manifest.booknlpArtifacts.map((item) => {
    if (!item || typeof item !== "object" || Array.isArray(item)) {
      throw new Error("invalid_booknlp_runtime_manifest_artifact");
    }
    const row = item as Record<string, unknown>;
    if (typeof row.name !== "string" || typeof row.sourceUrl !== "string") {
      throw new Error("invalid_booknlp_runtime_manifest_artifact");
    }
    return {
      name: row.name,
      sourceUrl: row.sourceUrl,
      bytes: requireNonNegativeInteger(row.bytes, "invalid_booknlp_runtime_manifest_artifact"),
      sha256: requireDigest(row.sha256, "invalid_booknlp_runtime_manifest_artifact"),
    };
  });

  const names = new Set(artifacts.map((artifact) => artifact.name));
  for (const required of BOOKNLP_SMALL_MODEL_FILES) {
    if (!names.has(required)) throw new Error(`booknlp_runtime_manifest_missing:${required}`);
  }
  if (artifacts.length !== BOOKNLP_SMALL_MODEL_FILES.length) {
    throw new Error("booknlp_runtime_manifest_unexpected_artifact_count");
  }
  const artifactBytes = artifacts.reduce((sum, artifact) => sum + artifact.bytes, 0);
  if (artifactBytes !== requireNonNegativeInteger(manifest.booknlpArtifactBytes, "booknlp_runtime_manifest_size_mismatch")) {
    throw new Error("booknlp_runtime_manifest_size_mismatch");
  }

  const transformerModels = manifest.transformerModels.map((item) => {
    if (!item || typeof item !== "object" || Array.isArray(item)) {
      throw new Error("invalid_booknlp_runtime_transformer_model");
    }
    const row = item as Record<string, unknown>;
    if (
      typeof row.modelId !== "string" ||
      typeof row.tokenizerClass !== "string" ||
      typeof row.modelClass !== "string"
    ) {
      throw new Error("invalid_booknlp_runtime_transformer_model");
    }
    return { modelId: row.modelId, tokenizerClass: row.tokenizerClass, modelClass: row.modelClass };
  });
  if (
    transformerModels.length !== EXPECTED_TRANSFORMER_MODELS.length ||
    EXPECTED_TRANSFORMER_MODELS.some((modelId) => !transformerModels.some((row) => row.modelId === modelId))
  ) {
    throw new Error("booknlp_runtime_transformer_set_mismatch");
  }

  const transformerCache = requireCacheDescriptor(manifest.transformerCache, "invalid_booknlp_runtime_transformer_cache");
  const spacyRow = manifest.spacyModel as Record<string, unknown>;
  if (spacyRow.name !== "en_core_web_sm") throw new Error("booknlp_runtime_spacy_model_mismatch");
  const spacyModel = {
    name: "en_core_web_sm",
    ...requireCacheDescriptor(spacyRow, "invalid_booknlp_runtime_spacy_model"),
  };
  const totalPreparedArtifactBytes = requireNonNegativeInteger(
    manifest.totalPreparedArtifactBytes,
    "invalid_booknlp_runtime_total_size",
  );
  if (totalPreparedArtifactBytes !== artifactBytes + transformerCache.bytes + spacyModel.bytes) {
    throw new Error("booknlp_runtime_total_size_mismatch");
  }

  return {
    schemaVersion: "saga-booknlp-runtime-manifest-v1",
    model: "small",
    packages: parsedPackages,
    booknlpArtifacts: artifacts,
    booknlpArtifactBytes: artifactBytes,
    transformerModels,
    transformerCache,
    spacyModel,
    totalPreparedArtifactBytes,
  };
}

async function readNativeOutput(root: string, documentId: string) {
  const documentRoot = join(root, documentId);
  const [tokensTsv, entitiesTsv, quotesTsv] = await Promise.all([
    readFile(join(documentRoot, `${documentId}.tokens`), "utf8"),
    readFile(join(documentRoot, `${documentId}.entities`), "utf8"),
    readFile(join(documentRoot, `${documentId}.quotes`), "utf8"),
  ]);
  return { tokensTsv, entitiesTsv, quotesTsv };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const textPath = join(args.litbankRoot, "coref", "tsv", `${args.documentId}.txt`);
  const [rawText, rawManifest, nativeOutput] = await Promise.all([
    readFile(textPath, "utf8"),
    readFile(args.runtimeManifest, "utf8"),
    readNativeOutput(args.directOutputRoot, args.documentId),
  ]);
  const text = normalizeNewlines(rawText);
  const normalizedInputFingerprint = sha256Hex(text);
  const section = litBankDocumentSection(args.documentId, text);
  const runtimeManifest = requireRuntimeManifest(JSON.parse(rawManifest));

  const configurationFingerprint = bookNlpRuntimeConfigurationFingerprint({
    runnerExecutable: args.runnerExecutable,
    runnerArgs: [args.runnerPath],
    modelPath: args.modelDir,
  });
  const provider = new SubprocessLocalLiteraryEvidenceProvider({
    executable: process.execPath,
    args: ["--import", "tsx", providerProcessPath],
    descriptor: BOOKNLP_SMALL_PROVIDER,
    configurationFingerprint,
    environment: {
      SAGA_BOOKNLP_RUNNER_EXECUTABLE: args.runnerExecutable,
      SAGA_BOOKNLP_RUNNER_ARGS_JSON: JSON.stringify([args.runnerPath]),
      SAGA_BOOKNLP_MODEL_DIR: args.modelDir,
      SAGA_BOOKNLP_RUNNER_TIMEOUT_MS: "900000",
      SAGA_BOOKNLP_RUNNER_STDOUT_BYTES: String(1024 * 1024),
      SAGA_BOOKNLP_RUNNER_STDERR_BYTES: String(4 * 1024 * 1024),
      HF_HOME: args.hfHome,
      TRANSFORMERS_CACHE: args.hfHome,
    },
    timeoutMs: 1_000_000,
    maxStdoutBytes: 128 * 1024 * 1024,
    maxStderrBytes: 4 * 1024 * 1024,
  });

  const healthStarted = performance.now();
  const health = await provider.health();
  const healthWallClockSeconds = (performance.now() - healthStarted) / 1000;

  const analyzeStarted = performance.now();
  const subprocessEvidence = await provider.analyze({
    normalizedInputFingerprint,
    normalizedText: text,
    sections: [section],
  });
  const analyzeWallClockSeconds = (performance.now() - analyzeStarted) / 1000;

  const directEvidence = normalizeBookNlpOutput({
    normalizedInputFingerprint,
    normalizedText: text,
    sections: [section],
    provider: BOOKNLP_SMALL_PROVIDER,
    ...nativeOutput,
  });
  const subprocessEvidenceFingerprint = evidenceFingerprint(subprocessEvidence);
  const directEvidenceFingerprint = evidenceFingerprint(directEvidence);
  const semanticEvidenceEqual = subprocessEvidenceFingerprint === directEvidenceFingerprint;
  const subprocessCounts = evidenceCounts(subprocessEvidence);
  const directCounts = evidenceCounts(directEvidence);
  const countsEqual = canonicalJson(subprocessCounts) === canonicalJson(directCounts);

  const comparison = {
    sourceRunId: DIRECT_BOOKNLP_SOURCE_RUN_ID,
    sourceHeadSha: DIRECT_BOOKNLP_SOURCE_HEAD,
    sourceArtifactSha256: DIRECT_BOOKNLP_ARTIFACT_SHA256,
    directEvidenceFingerprint,
    subprocessEvidenceFingerprint,
    semanticEvidenceEqual,
    directCounts,
    subprocessCounts,
    countsEqual,
  };
  const semanticComparisonFingerprint = sha256Hex(canonicalJson({
    datasetCommit: LITBANK_COMMIT,
    documentId: args.documentId,
    normalizedInputFingerprint,
    provider: BOOKNLP_SMALL_PROVIDER,
    comparison,
  }));

  const semantic = {
    schemaVersion: "saga-booknlp-subprocess-proof-v1",
    dataset: {
      repository: "dbamman/litbank",
      commit: LITBANK_COMMIT,
      documentId: args.documentId,
      sourceBytes: Buffer.byteLength(text, "utf8"),
      sourceCodePoints: Array.from(text).length,
      normalizedInputFingerprint,
    },
    provider: {
      descriptor: BOOKNLP_SMALL_PROVIDER,
      expectedPackageVersion: BOOKNLP_EXPECTED_PACKAGE_VERSION,
      protocolVersion: health.protocolVersion,
      configurationFingerprint,
      runnerPath: args.runnerPath,
      runnerExecutable: args.runnerExecutable,
      offlineTransformerRuntime: true,
    },
    preparedRuntime: {
      manifestFingerprint: sha256Hex(canonicalJson(runtimeManifest)),
      packages: runtimeManifest.packages,
      booknlpArtifactBytes: runtimeManifest.booknlpArtifactBytes,
      booknlpArtifacts: runtimeManifest.booknlpArtifacts.map(({ name, bytes, sha256 }) => ({ name, bytes, sha256 })),
      transformerModels: runtimeManifest.transformerModels.map(({ modelId }) => modelId),
      transformerCache: runtimeManifest.transformerCache,
      spacyModel: runtimeManifest.spacyModel,
      totalPreparedArtifactBytes: runtimeManifest.totalPreparedArtifactBytes,
    },
    directComparison: comparison,
    semanticComparisonFingerprint,
    runtime: {
      healthWallClockSeconds,
      analyzeWallClockSeconds,
    },
    adoption: {
      qualityMetricsChanged: false,
      productionProviderAdopted: false,
      modelWeightLicenseVerified: false,
      privateProductGateSatisfied: false,
    },
  };
  const report = { ...semantic, reportFingerprint: sha256Hex(canonicalJson(semantic)) };

  await mkdir(dirname(args.out), { recursive: true });
  await writeFile(args.out, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);

  if (!semanticEvidenceEqual || !countsEqual) process.exitCode = 2;
}

main().catch((error) => {
  console.error(error instanceof Error ? error.stack ?? error.message : String(error));
  process.exitCode = 1;
});
