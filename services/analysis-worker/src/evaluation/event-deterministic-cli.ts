import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";

import type { CharacterIdentityResult } from "../identity/types.js";
import type { NormalizationResult } from "../ingestion/types.js";
import { predictDeterministicEventCandidates } from "./event-deterministic-baseline.js";

function valueAfter(argv: string[], name: string) {
  const index = argv.indexOf(name);
  return index < 0 ? null : argv[index + 1] ?? null;
}

async function main() {
  const argv = process.argv.slice(2);
  const normalizationPath = valueAfter(argv, "--normalization");
  const identityPath = valueAfter(argv, "--identity");
  const output = valueAfter(argv, "--out");
  if (!normalizationPath || !identityPath) {
    throw new Error(
      "usage: event-deterministic-cli --normalization <normalization.json> --identity <identity-result.json> [--out <prediction.json>]",
    );
  }

  const normalization = JSON.parse(await readFile(resolve(normalizationPath), "utf8")) as NormalizationResult;
  const identity = JSON.parse(await readFile(resolve(identityPath), "utf8")) as CharacterIdentityResult;
  const prediction = predictDeterministicEventCandidates({
    sections: normalization.sections,
    normalizedInputFingerprint: normalization.outputFingerprint,
    identity,
  });
  const rendered = `${JSON.stringify(prediction, null, 2)}\n`;
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
