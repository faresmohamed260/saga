import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { performance } from "node:perf_hooks";
import { fileURLToPath } from "node:url";

import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import { PersistentBookNlpEvidenceProvider } from "../local-analysis/booknlp-persistent-provider.js";
import type { LocalLiteraryEvidenceBundle } from "../local-analysis/types.js";
import { litBankDocumentSection } from "./litbank-component-benchmark.js";

const LITBANK_COMMIT = "3e50db0ffc033d7ccbb94f4d88f6b99210328ed8";
const DEFAULT_DOCUMENT_ID = "1023_bleak_house_brat";
const DIRECT_EVIDENCE_FINGERPRINT = "8be0f789a80ecf47c0b902b51e0492c17ef016023c3e215df6a4d57ff3e27add";
const EXPECTED_COUNTS = {
  identityMentions: 230,
  entities: 230,
  quotes: 5,
  eventTriggers: 20,
  syntaxTokens: 2319,
} as const;
const ONE_SHOT_BASELINE = {
  firstRunAnalyzeSeconds: 6.3136767240000005,
  secondRunHealthSeconds: 2.847315428,
  secondRunAnalyzeSeconds: 8.930336711,
  secondRunPeakProcessTreeRssMiB: 1040.53125,
} as const;
const defaultRunnerPath = fileURLToPath(new URL("../../providers/booknlp_persistent_runner.py", import.meta.url));

function parseArgs(argv: string[]) {
  let litbankRoot: string | null = null;
  let modelDir: string | null = null;
  let hfHome: string | null = null;
  let runtimeManifest: string | null = null;
  let runnerExecutable: string | null = null;
  let runnerPath = defaultRunnerPath;
  let documentId = DEFAULT_DOCUMENT_ID;
  let out: string | null = null;
  let repeats = 3;

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === "--litbank-root") litbankRoot = argv[++index] ?? null;
    else if (token === "--model-dir") modelDir = argv[++index] ?? null;
    else if (token === "--hf-home") hfHome = argv[++index] ?? null;
    else if (token === "--runtime-manifest") runtimeManifest = argv[++index] ?? null;
    else if (token === "--runner-executable") runnerExecutable = argv[++index] ?? null;
    else if (token === "--runner-path") runnerPath = argv[++index] ?? runnerPath;
    else if (token === "--document-id") documentId = argv[++index] ?? documentId;
    else if (token === "--out") out = argv[++index] ?? null;
    else if (token === "--repeats") repeats = Number(argv[++index] ?? "NaN");
    else throw new Error(`unknown argument: ${token}`);
  }

  if (!litbankRoot || !modelDir || !hfHome || !runtimeManifest || !runnerExecutable || !out) {
    throw new Error("missing required persistent BookNLP proof argument");
  }
  if (!Number.isSafeInteger(repeats) || repeats < 2 || repeats > 10) {
    throw new Error("persistent BookNLP proof repeats must be between 2 and 10");
  }

  return {
    litbankRoot: resolve(litbankRoot),
    modelDir: resolve(modelDir),
    hfHome: resolve(hfHome),
    runtimeManifest: resolve(runtimeManifest),
    runnerExecutable: resolve(runnerExecutable),
    runnerPath: resolve(runnerPath),
    documentId,
    out: resolve(out),
    repeats,
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

function runtimeFootprint(value: unknown) {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("invalid_runtime_manifest");
  const row = value as Record<string, unknown>;
  if (row.schemaVersion !== "saga-booknlp-runtime-manifest-v1") throw new Error("invalid_runtime_manifest");
  for (const key of ["booknlpArtifactBytes", "totalPreparedArtifactBytes"] as const) {
    if (!Number.isSafeInteger(row[key]) || (row[key] as number) < 0) throw new Error("invalid_runtime_manifest");
  }
  if (!row.transformerCache || typeof row.transformerCache !== "object" || Array.isArray(row.transformerCache)) {
    throw new Error("invalid_runtime_manifest");
  }
  if (!row.spacyModel || typeof row.spacyModel !== "object" || Array.isArray(row.spacyModel)) {
    throw new Error("invalid_runtime_manifest");
  }
  const transformerBytes = (row.transformerCache as Record<string, unknown>).bytes;
  const spacyBytes = (row.spacyModel as Record<string, unknown>).bytes;
  if (!Number.isSafeInteger(transformerBytes) || !Number.isSafeInteger(spacyBytes)) {
    throw new Error("invalid_runtime_manifest");
  }
  return {
    booknlpArtifactBytes: row.booknlpArtifactBytes as number,
    transformerCacheBytes: transformerBytes as number,
    spacyModelBytes: spacyBytes as number,
    totalPreparedArtifactBytes: row.totalPreparedArtifactBytes as number,
  };
}

function median(values: number[]) {
  const sorted = [...values].sort((left, right) => left - right);
  const middle = Math.floor(sorted.length / 2);
  if (sorted.length % 2 === 1) return sorted[middle]!;
  return (sorted[middle - 1]! + sorted[middle]!) / 2;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const textPath = join(args.litbankRoot, "coref", "tsv", `${args.documentId}.txt`);
  const [rawText, rawManifest] = await Promise.all([
    readFile(textPath, "utf8"),
    readFile(args.runtimeManifest, "utf8"),
  ]);
  const text = normalizeNewlines(rawText);
  const normalizedInputFingerprint = sha256Hex(text);
  const section = litBankDocumentSection(args.documentId, text);
  const footprint = runtimeFootprint(JSON.parse(rawManifest));

  const provider = new PersistentBookNlpEvidenceProvider({
    runnerExecutable: args.runnerExecutable,
    runnerArgs: [args.runnerPath],
    modelPath: args.modelDir,
    environment: {
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

  const passes: Array<{
    repeat: number;
    wallClockSeconds: number;
    evidenceFingerprint: string;
    counts: ReturnType<typeof evidenceCounts>;
  }> = [];

  try {
    for (let repeat = 1; repeat <= args.repeats; repeat += 1) {
      const started = performance.now();
      const evidence = await provider.analyze({
        normalizedInputFingerprint,
        normalizedText: text,
        sections: [section],
      });
      const wallClockSeconds = (performance.now() - started) / 1000;
      const fingerprint = evidenceFingerprint(evidence);
      const counts = evidenceCounts(evidence);
      if (fingerprint !== DIRECT_EVIDENCE_FINGERPRINT) {
        throw new Error(`persistent_semantic_fingerprint_mismatch:${repeat}`);
      }
      if (canonicalJson(counts) !== canonicalJson(EXPECTED_COUNTS)) {
        throw new Error(`persistent_evidence_count_mismatch:${repeat}`);
      }
      passes.push({ repeat, wallClockSeconds, evidenceFingerprint: fingerprint, counts });
    }
  } finally {
    await provider.close();
  }

  const latencies = passes.map((row) => row.wallClockSeconds);
  const medianAnalyzeSeconds = median(latencies);
  const semanticStable = new Set(passes.map((row) => row.evidenceFingerprint)).size === 1;
  const reportWithoutFingerprint = {
    schemaVersion: "saga-booknlp-persistent-runtime-proof-v1",
    dataset: {
      repository: "dbamman/litbank",
      commit: LITBANK_COMMIT,
      documentId: args.documentId,
      sourceBytes: Buffer.byteLength(text, "utf8"),
      sourceCodePoints: Array.from(text).length,
      normalizedInputFingerprint,
    },
    provider: {
      descriptor: provider.descriptor,
      protocolVersion: health.protocolVersion,
      configurationFingerprint: provider.configurationFingerprint,
      runnerExecutable: args.runnerExecutable,
      runnerPath: args.runnerPath,
      offlineTransformerRuntime: true,
    },
    semanticComparison: {
      validatedOneShotDirectEvidenceFingerprint: DIRECT_EVIDENCE_FINGERPRINT,
      expectedCounts: EXPECTED_COUNTS,
      persistentPasses: passes,
      semanticStable,
      allPassesEqualValidatedOneShot: passes.every((row) => row.evidenceFingerprint === DIRECT_EVIDENCE_FINGERPRINT),
    },
    runtime: {
      healthWallClockSeconds,
      analyzeMedianWallClockSeconds: medianAnalyzeSeconds,
      analyzePassSeconds: latencies,
      speedupVsOneShotFirstRun: ONE_SHOT_BASELINE.firstRunAnalyzeSeconds / medianAnalyzeSeconds,
      speedupVsOneShotSecondRun: ONE_SHOT_BASELINE.secondRunAnalyzeSeconds / medianAnalyzeSeconds,
    },
    oneShotBaseline: ONE_SHOT_BASELINE,
    preparedRuntime: footprint,
    adoption: {
      qualityMetricsChanged: false,
      productionProviderAdopted: false,
      transportAdopted: false,
      modelWeightLicenseVerified: false,
      privateProductGateSatisfied: false,
    },
  };
  const report = {
    ...reportWithoutFingerprint,
    semanticComparisonFingerprint: sha256Hex(canonicalJson({
      dataset: reportWithoutFingerprint.dataset,
      semanticComparison: {
        validatedOneShotDirectEvidenceFingerprint: DIRECT_EVIDENCE_FINGERPRINT,
        expectedCounts: EXPECTED_COUNTS,
        fingerprints: passes.map((row) => row.evidenceFingerprint),
        counts: passes.map((row) => row.counts),
      },
    })),
    reportFingerprint: sha256Hex(canonicalJson(reportWithoutFingerprint)),
  };

  await mkdir(dirname(args.out), { recursive: true });
  await writeFile(args.out, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  console.log(JSON.stringify(report, null, 2));
}

await main();
