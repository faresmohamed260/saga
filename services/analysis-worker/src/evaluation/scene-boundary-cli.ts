import { readFile, writeFile, mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";

import {
  evaluateSceneBoundaries,
  type SceneBoundaryProviderResult,
  type SceneBoundaryReference,
} from "./scene-boundary-evaluation.js";

function parseArgs(argv: string[]) {
  let reference: string | null = null;
  let prediction: string | null = null;
  let output: string | null = null;
  let toleranceParagraphs = 1;

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === "--reference") reference = argv[++index] ?? null;
    else if (token === "--prediction") prediction = argv[++index] ?? null;
    else if (token === "--out") output = argv[++index] ?? null;
    else if (token === "--tolerance-paragraphs") toleranceParagraphs = Number(argv[++index]);
    else throw new Error(`unknown_argument:${token}`);
  }

  if (!reference || !prediction) {
    throw new Error(
      "usage: scene-boundary-cli --reference <reference.json> --prediction <prediction.json> [--tolerance-paragraphs 1] [--out <report.json>]",
    );
  }
  return {
    reference: resolve(reference),
    prediction: resolve(prediction),
    output: output ? resolve(output) : null,
    toleranceParagraphs,
  };
}

async function readJson<T>(path: string): Promise<T> {
  return JSON.parse(await readFile(path, "utf8")) as T;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const reference = await readJson<SceneBoundaryReference>(args.reference);
  const prediction = await readJson<SceneBoundaryProviderResult>(args.prediction);
  const report = evaluateSceneBoundaries({
    reference,
    prediction,
    toleranceParagraphs: args.toleranceParagraphs,
  });
  const rendered = `${JSON.stringify(report, null, 2)}\n`;
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
