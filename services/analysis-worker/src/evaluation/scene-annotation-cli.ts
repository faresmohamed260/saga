import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";

import type { NormalizationResult } from "../ingestion/types.js";
import {
  createSceneAnnotationWorkspace,
  finalizeSceneAnnotationWorkspace,
  type SceneAnnotationWorkspace,
} from "./scene-annotation-workspace.js";

function valueAfter(argv: string[], name: string) {
  const index = argv.indexOf(name);
  return index < 0 ? null : argv[index + 1] ?? null;
}

async function writeJson(path: string, value: unknown) {
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

async function createWorkspace(argv: string[]) {
  const normalizationPath = valueAfter(argv, "--normalization");
  const bookId = valueAfter(argv, "--book-id");
  const sourceSha256 = valueAfter(argv, "--source-sha256");
  const output = valueAfter(argv, "--out");
  const sectionsRaw = valueAfter(argv, "--sections");
  if (!normalizationPath || !bookId || !sourceSha256 || !output) {
    throw new Error(
      "usage: scene-annotation-cli create --normalization <normalization.json> --book-id <id> --source-sha256 <sha256> --out <PRIVATE-workspace.json> [--sections key1,key2]",
    );
  }
  const normalization = JSON.parse(await readFile(resolve(normalizationPath), "utf8")) as NormalizationResult;
  const workspace = createSceneAnnotationWorkspace({
    bookId,
    sourceSha256,
    normalization,
    annotationProtocolVersion: "saga-scene-annotation-v1",
    sectionKeys: sectionsRaw ? sectionsRaw.split(",").map((value) => value.trim()).filter(Boolean) : undefined,
  });
  await writeJson(resolve(output), workspace);
  process.stderr.write("PRIVATE annotation workspace contains copyrighted source text. Do not commit or upload it.\n");
}

async function finalizeWorkspace(argv: string[]) {
  const workspacePath = valueAfter(argv, "--workspace");
  const output = valueAfter(argv, "--out");
  if (!workspacePath || !output) {
    throw new Error("usage: scene-annotation-cli finalize --workspace <PRIVATE-workspace.json> --out <reference.json>");
  }
  const workspace = JSON.parse(await readFile(resolve(workspacePath), "utf8")) as SceneAnnotationWorkspace;
  const reference = finalizeSceneAnnotationWorkspace(workspace);
  await writeJson(resolve(output), reference);
}

async function main() {
  const [command, ...argv] = process.argv.slice(2);
  if (command === "create") await createWorkspace(argv);
  else if (command === "finalize") await finalizeWorkspace(argv);
  else throw new Error("scene-annotation-cli requires create or finalize");
}

main().catch((error) => {
  console.error(error instanceof Error ? error.stack ?? error.message : String(error));
  process.exitCode = 1;
});
