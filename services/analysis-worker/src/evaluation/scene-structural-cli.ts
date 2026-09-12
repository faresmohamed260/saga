import { readFile, writeFile, mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";

import type { NormalizationResult } from "../ingestion/types.js";
import { predictStructuralSceneBoundaries } from "./scene-structural-baseline.js";

function parseArgs(argv: string[]) {
  let normalization: string | null = null;
  let output: string | null = null;
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === "--normalization") normalization = argv[++index] ?? null;
    else if (token === "--out") output = argv[++index] ?? null;
    else throw new Error(`unknown_argument:${token}`);
  }
  if (!normalization) throw new Error("usage: scene-structural-cli --normalization <normalization.json> [--out <prediction.json>]");
  return { normalization: resolve(normalization), output: output ? resolve(output) : null };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const normalization = JSON.parse(await readFile(args.normalization, "utf8")) as NormalizationResult;
  const prediction = predictStructuralSceneBoundaries({
    sections: normalization.sections,
    normalizedInputFingerprint: normalization.outputFingerprint,
  });
  const rendered = `${JSON.stringify(prediction, null, 2)}\n`;
  if (args.output) {
    await mkdir(dirname(args.output), { recursive: true });
    await writeFile(args.output, rendered, "utf8");
  }
  process.stdout.write(rendered);
}

main().catch((error) => {
  console.error(error instanceof Error ? error.stack ?? error.message : String(error));
  process.exitCode = 1;
});
