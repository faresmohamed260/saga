import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { basename, dirname, join, resolve } from "node:path";

import { resolveCharacterIdentity } from "../identity/resolver.js";
import {
  aggregateIdentityBenchmarkReports,
  evaluateIdentityBenchmarkCase,
} from "./identity-benchmark.js";
import { convertLitBankTsvDocument, LITBANK_ORACLE_PROVIDER } from "./litbank-tsv.js";

const LITBANK_COMMIT = "3e50db0ffc033d7ccbb94f4d88f6b99210328ed8";

function parseArgs(argv: string[]) {
  let root: string | null = null;
  let out: string | null = null;
  let limit: number | null = null;

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === "--root") root = argv[++index] ?? null;
    else if (token === "--out") out = argv[++index] ?? null;
    else if (token === "--limit") {
      const parsed = Number(argv[++index]);
      if (!Number.isSafeInteger(parsed) || parsed <= 0) throw new Error("invalid --limit");
      limit = parsed;
    } else {
      throw new Error(`unknown argument: ${token}`);
    }
  }

  if (!root || !out) {
    throw new Error("usage: litbank-oracle-cli --root <litbank-root> --out <report.json> [--limit N]");
  }
  return { root: resolve(root), out: resolve(out), limit };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const annotationDir = join(args.root, "coref", "tsv");
  const annotationNames = (await readdir(annotationDir))
    .filter((name) => name.endsWith(".ann"))
    .sort()
    .slice(0, args.limit ?? undefined);

  if (annotationNames.length === 0) throw new Error("no LitBank coref/tsv annotations found");

  const perDocument = [];
  for (const annotationName of annotationNames) {
    const documentId = basename(annotationName, ".ann");
    const annotationPath = join(annotationDir, annotationName);
    const textPath = join(annotationDir, `${documentId}.txt`);
    const [annotation, text] = await Promise.all([
      readFile(annotationPath, "utf8"),
      readFile(textPath, "utf8"),
    ]);

    const converted = convertLitBankTsvDocument({ documentId, annotation, text });
    const result = resolveCharacterIdentity({
      normalizedText: converted.gold.text,
      evidence: converted.evidence,
    });
    const report = evaluateIdentityBenchmarkCase({
      gold: converted.gold,
      evidence: converted.evidence,
      result,
    });
    perDocument.push({
      documentId,
      outputFingerprint: result.outputFingerprint,
      counts: report.counts,
      metrics: report.metrics,
    });
  }

  const aggregate = aggregateIdentityBenchmarkReports(
    perDocument.map((document) => ({ counts: document.counts, metrics: document.metrics })),
  );
  const output = {
    schemaVersion: "saga-identity-benchmark-v1",
    benchmark: "LitBank oracle-evidence policy baseline",
    benchmarkPurpose:
      "Measure S.A.G.A. deterministic canonical admission/attachment policy with LitBank gold entity/coreference evidence, isolating resolver policy from model/provider recall.",
    dataset: {
      repository: "dbamman/litbank",
      commit: LITBANK_COMMIT,
      license: "CC BY 4.0",
      annotationLayer: "coref/tsv",
      documentCount: perDocument.length,
    },
    provider: LITBANK_ORACLE_PROVIDER,
    aggregate,
    perDocument,
  };

  await mkdir(dirname(args.out), { recursive: true });
  await writeFile(args.out, `${JSON.stringify(output, null, 2)}\n`, "utf8");
  process.stdout.write(`${JSON.stringify(output.aggregate, null, 2)}\n`);
}

main().catch((error) => {
  console.error(error instanceof Error ? error.stack ?? error.message : String(error));
  process.exitCode = 1;
});
