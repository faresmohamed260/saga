import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";

import {
  evaluateDialogue,
  type DialogueProviderResult,
  type DialogueReference,
} from "./dialogue-evaluation.js";

function valueAfter(argv: string[], name: string) {
  const index = argv.indexOf(name);
  return index < 0 ? null : argv[index + 1] ?? null;
}

async function main() {
  const argv = process.argv.slice(2);
  const referencePath = valueAfter(argv, "--reference");
  const predictionPath = valueAfter(argv, "--prediction");
  const output = valueAfter(argv, "--out");
  if (!referencePath || !predictionPath) {
    throw new Error(
      "usage: dialogue-score-cli --reference <reference.json> --prediction <prediction.json> [--out <report.json>]",
    );
  }

  const reference = JSON.parse(await readFile(resolve(referencePath), "utf8")) as DialogueReference;
  const prediction = JSON.parse(await readFile(resolve(predictionPath), "utf8")) as DialogueProviderResult;
  const report = evaluateDialogue({ reference, prediction });
  const rendered = `${JSON.stringify(report, null, 2)}\n`;
  if (output) {
    const outputPath = resolve(output);
    await mkdir(dirname(outputPath), { recursive: true });
    await writeFile(outputPath, rendered, "utf8");
  }
  process.stdout.write(rendered);
}

main().catch((error) => {
  console.error(error instanceof Error ? error.stack ?? error.message : String(error));
  process.exitCode = 1;
});
