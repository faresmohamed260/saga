import { readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { mkdir } from "node:fs/promises";

import type { CharacterIdentityResult } from "../identity/types.js";
import {
  evaluatePrimaryFictionRegression,
  validatePrimaryFictionRegressionManifest,
  type PrimaryFictionRegressionManifest,
} from "./primary-fiction-regression.js";

function parseArgs(argv: string[]) {
  let expectations: string | null = null;
  let caseId: string | null = null;
  let result: string | null = null;
  let output: string | null = null;

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === "--expectations") expectations = argv[++index] ?? null;
    else if (token === "--case") caseId = argv[++index] ?? null;
    else if (token === "--result") result = argv[++index] ?? null;
    else if (token === "--out") output = argv[++index] ?? null;
    else throw new Error(`unknown_argument:${token}`);
  }

  if (!expectations || !caseId || !result) {
    throw new Error(
      "usage: primary-fiction-regression-cli --expectations <manifest.json> --case <case-id> --result <identity-result.json> [--out <report.json>]",
    );
  }

  return {
    expectations: resolve(expectations),
    caseId,
    result: resolve(result),
    output: output ? resolve(output) : null,
  };
}

async function readJson<T>(path: string): Promise<T> {
  return JSON.parse(await readFile(path, "utf8")) as T;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const manifest = await readJson<PrimaryFictionRegressionManifest>(args.expectations);
  validatePrimaryFictionRegressionManifest(manifest);
  const regressionCase = manifest.cases.find((candidate) => candidate.caseId === args.caseId);
  if (!regressionCase) throw new Error(`primary_fiction_case_not_found:${args.caseId}`);

  const result = await readJson<CharacterIdentityResult>(args.result);
  const report = evaluatePrimaryFictionRegression({ regressionCase, result });
  const rendered = `${JSON.stringify(report, null, 2)}\n`;
  if (args.output) {
    await mkdir(dirname(args.output), { recursive: true });
    await writeFile(args.output, rendered, "utf8");
  }
  process.stdout.write(rendered);
  if (!report.passed) process.exitCode = 2;
}

main().catch((error) => {
  console.error(error instanceof Error ? error.stack ?? error.message : String(error));
  process.exitCode = 1;
});
