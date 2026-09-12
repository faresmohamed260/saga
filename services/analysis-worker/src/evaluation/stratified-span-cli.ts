import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";

import type { NovelDiversityManifest } from "./stratified-identity-benchmark.js";
import {
  buildStratifiedSpanBenchmark,
  type StratifiedSpanSourceReport,
} from "./stratified-span-benchmark.js";

function parseArgs(argv: string[]) {
  let report: string | null = null;
  let manifest: string | null = null;
  let out: string | null = null;

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === "--report") report = argv[++index] ?? null;
    else if (token === "--manifest") manifest = argv[++index] ?? null;
    else if (token === "--out") out = argv[++index] ?? null;
    else throw new Error(`unknown argument: ${token}`);
  }

  if (!report || !manifest || !out) {
    throw new Error(
      "usage: stratified-span-cli --report <span-report.json> --manifest <diversity-manifest.json> --out <report.json>",
    );
  }
  return { report: resolve(report), manifest: resolve(manifest), out: resolve(out) };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const [rawReport, rawManifest] = await Promise.all([
    readFile(args.report, "utf8"),
    readFile(args.manifest, "utf8"),
  ]);
  const output = buildStratifiedSpanBenchmark({
    report: JSON.parse(rawReport) as StratifiedSpanSourceReport,
    manifest: JSON.parse(rawManifest) as NovelDiversityManifest,
  });

  await mkdir(dirname(args.out), { recursive: true });
  await writeFile(args.out, `${JSON.stringify(output, null, 2)}\n`, "utf8");
  process.stdout.write(`${JSON.stringify({
    provider: output.provider,
    coverage: output.coverage,
    strata: output.strata.map((stratum) => ({
      id: stratum.id,
      documentCount: stratum.documentCount,
      metrics: stratum.aggregate.metrics,
    })),
    reportFingerprint: output.reportFingerprint,
  }, null, 2)}\n`);
}

main().catch((error) => {
  console.error(error instanceof Error ? error.stack ?? error.message : String(error));
  process.exitCode = 1;
});
