import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";

import type { NormalizationResult } from "../ingestion/types.js";
import {
  DEFAULT_SCENE_LEXICAL_CONFIG,
  predictLexicalSceneBoundaries,
  type SceneLexicalBaselineConfig,
} from "./scene-lexical-baseline.js";

function valueAfter(argv: string[], name: string) {
  const index = argv.indexOf(name);
  return index < 0 ? null : argv[index + 1] ?? null;
}

async function main() {
  const argv = process.argv.slice(2);
  const normalizationPath = valueAfter(argv, "--normalization");
  const output = valueAfter(argv, "--out");
  const configPath = valueAfter(argv, "--config");
  if (!normalizationPath) {
    throw new Error("usage: scene-lexical-cli --normalization <normalization.json> [--config <config.json>] [--out <prediction.json>]");
  }
  const normalization = JSON.parse(await readFile(resolve(normalizationPath), "utf8")) as NormalizationResult;
  const config = configPath
    ? JSON.parse(await readFile(resolve(configPath), "utf8")) as SceneLexicalBaselineConfig
    : DEFAULT_SCENE_LEXICAL_CONFIG;
  const prediction = predictLexicalSceneBoundaries({
    sections: normalization.sections,
    normalizedInputFingerprint: normalization.outputFingerprint,
    config,
  });
  const rendered = `${JSON.stringify(prediction, null, 2)}\n`;
  if (output) {
    const path = resolve(output);
    await mkdir(dirname(path), { recursive: true });
    await writeFile(path, rendered, "utf8");
  }
  process.stdout.write(rendered);
}

main().catch((error) => {
  console.error(error instanceof Error ? error.stack ?? error.message : String(error));
  process.exitCode = 1;
});
