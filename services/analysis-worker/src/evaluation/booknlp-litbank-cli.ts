import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { basename, dirname, join, resolve } from "node:path";

import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import { resolveCharacterIdentity } from "../identity/resolver.js";
import { codePointLength, normalizeBookNlpOutput } from "../local-analysis/booknlp-output.js";
import { BOOKNLP_SMALL_PROVIDER } from "../local-analysis/booknlp-provider.js";
import {
  aggregateIdentityBenchmarkReports,
  evaluateIdentityBenchmarkCase,
} from "./identity-benchmark.js";
import { convertLitBankTsvDocument } from "./litbank-tsv.js";

const LITBANK_COMMIT = "3e50db0ffc033d7ccbb94f4d88f6b99210328ed8";

function parseArgs(argv: string[]) {
  let litbankRoot: string | null = null;
  let booknlpRoot: string | null = null;
  let out: string | null = null;
  let limit: number | null = null;

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === "--litbank-root") litbankRoot = argv[++index] ?? null;
    else if (token === "--booknlp-root") booknlpRoot = argv[++index] ?? null;
    else if (token === "--out") out = argv[++index] ?? null;
    else if (token === "--limit") {
      const parsed = Number(argv[++index]);
      if (!Number.isSafeInteger(parsed) || parsed <= 0) throw new Error("invalid --limit");
      limit = parsed;
    } else {
      throw new Error(`unknown argument: ${token}`);
    }
  }

  if (!litbankRoot || !booknlpRoot || !out) {
    throw new Error(
      "usage: booknlp-litbank-cli --litbank-root <litbank-root> --booknlp-root <outputs-root> --out <report.json> [--limit N]",
    );
  }
  return {
    litbankRoot: resolve(litbankRoot),
    booknlpRoot: resolve(booknlpRoot),
    out: resolve(out),
    limit,
  };
}

async function readBookNlpDocument(root: string, documentId: string) {
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
  const annotationDir = join(args.litbankRoot, "coref", "tsv");
  const annotationNames = (await readdir(annotationDir))
    .filter((name) => name.endsWith(".ann"))
    .sort()
    .slice(0, args.limit ?? undefined);

  if (annotationNames.length === 0) throw new Error("no LitBank coref/tsv annotations found");

  const completed = [];
  const failures: Array<{ documentId: string; code: string; message: string }> = [];

  for (const annotationName of annotationNames) {
    const documentId = basename(annotationName, ".ann");
    try {
      const [annotation, text, booknlp] = await Promise.all([
        readFile(join(annotationDir, annotationName), "utf8"),
        readFile(join(annotationDir, `${documentId}.txt`), "utf8"),
        readBookNlpDocument(args.booknlpRoot, documentId),
      ]);
      const converted = convertLitBankTsvDocument({ documentId, annotation, text });
      const normalizedText = converted.gold.text;
      const evidence = normalizeBookNlpOutput({
        normalizedInputFingerprint: sha256Hex(normalizedText),
        normalizedText,
        sections: [
          {
            stable_key: `litbank:${documentId}`,
            ordinal: 0,
            section_kind: "document",
            title: null,
            source_locator: `litbank:${documentId}`,
            start_offset: 0,
            end_offset: codePointLength(normalizedText),
            normalized_text: normalizedText,
          },
        ],
        provider: BOOKNLP_SMALL_PROVIDER,
        tokensTsv: booknlp.tokensTsv,
        entitiesTsv: booknlp.entitiesTsv,
        quotesTsv: booknlp.quotesTsv,
      });
      const result = resolveCharacterIdentity({ normalizedText, evidence: evidence.identityEvidence });
      const report = evaluateIdentityBenchmarkCase({
        gold: converted.gold,
        evidence: evidence.identityEvidence,
        result,
      });
      completed.push({
        documentId,
        outputFingerprint: result.outputFingerprint,
        evidenceCounts: {
          identityMentions: evidence.identityEvidence.mentions.length,
          entities: evidence.entities.length,
          quotes: evidence.quotes.length,
          eventTriggers: evidence.eventTriggers.length,
        },
        counts: report.counts,
        metrics: report.metrics,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      failures.push({
        documentId,
        code: message.split(":", 1)[0] || "unknown_error",
        message,
      });
    }
  }

  const aggregate = aggregateIdentityBenchmarkReports(
    completed.map((document) => ({ counts: document.counts, metrics: document.metrics })),
  );
  const aggregateOutputFingerprint = sha256Hex(canonicalJson(
    completed.map((document) => ({ documentId: document.documentId, outputFingerprint: document.outputFingerprint })),
  ));
  const output = {
    schemaVersion: "saga-booknlp-litbank-benchmark-v1",
    benchmark: "BookNLP small -> S.A.G.A. identity policy",
    benchmarkPurpose:
      "Measure real BookNLP-small provider evidence after S.A.G.A. normalization and deterministic identity resolution against the same pinned LitBank gold used by the oracle-policy baseline.",
    dataset: {
      repository: "dbamman/litbank",
      commit: LITBANK_COMMIT,
      license: "CC BY 4.0",
      annotationLayer: "coref/tsv",
      attemptedDocumentCount: annotationNames.length,
      completedDocumentCount: completed.length,
      failedDocumentCount: failures.length,
    },
    provider: BOOKNLP_SMALL_PROVIDER,
    providerCodeLicense: "MIT",
    providerModelWeightsLicense: "unverified",
    aggregateOutputFingerprint,
    aggregate,
    failures,
    perDocument: completed,
  };

  await mkdir(dirname(args.out), { recursive: true });
  await writeFile(args.out, `${JSON.stringify(output, null, 2)}\n`, "utf8");
  process.stdout.write(`${JSON.stringify({ dataset: output.dataset, aggregate: output.aggregate, failures }, null, 2)}\n`);

  if (completed.length === 0) process.exitCode = 2;
}

main().catch((error) => {
  console.error(error instanceof Error ? error.stack ?? error.message : String(error));
  process.exitCode = 1;
});
