import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";

const cli = resolve("src/evaluation/whole-book-cli.ts");

async function executeFixture(root: string, reportName: string) {
  const sources = join(root, "sources");
  const outputs = join(root, "outputs");
  const manifest = join(root, "suite.json");
  const provider = join(root, "provider.mjs");
  const report = join(root, reportName);

  await mkdir(sources, { recursive: true });
  await writeFile(join(sources, "fixture.txt"), "Alice met Bob. Alice waved.\n", "utf8");
  await writeFile(manifest, JSON.stringify({
    schemaVersion: "saga-whole-book-suite-v1",
    suiteId: "cli-fixture",
    purpose: "exercise the benchmark CLI",
    sourcePolicy: "ephemeral test fixture",
    books: [
      {
        id: "fixture-book",
        title: "Fixture Book",
        sourceFile: "fixture.txt",
        sourceLocator: "fixture:local",
        tags: ["fixture"],
        licenseNote: "generated test text",
      },
    ],
  }), "utf8");
  await writeFile(provider, `
    import { mkdir, readFile, writeFile } from "node:fs/promises";
    import { join } from "node:path";
    const [source, output] = process.argv.slice(2);
    await mkdir(output, { recursive: true });
    const text = await readFile(source, "utf8");
    await new Promise((resolve) => setTimeout(resolve, 300));
    await writeFile(join(output, "result.json"), JSON.stringify({ length: [...text].length, names: ["Alice", "Bob"] }) + "\\n", "utf8");
  `, "utf8");

  const result = spawnSync(process.execPath, [
    "--import", "tsx",
    cli,
    "--manifest", manifest,
    "--sources-root", sources,
    "--output-root", outputs,
    "--report-out", report,
    "--provider-name", "fixture-provider",
    "--provider-model", "fixture-model",
    "--provider-revision", "fixture-r1",
    "--provider-license", "fixture",
    "--",
    process.execPath,
    provider,
    "{source}",
    "{output}",
  ], { encoding: "utf8", timeout: 20_000 });

  assert.equal(result.status, 0, result.stderr || result.stdout);
  return {
    outputs,
    report: JSON.parse(await readFile(report, "utf8")) as {
      semanticResultFingerprint: string;
      sourceFingerprint: string;
      aggregate: { completedBookCount: number; failedBookCount: number };
      books: Array<{ outputFileCount: number; outputFingerprint: string }>;
    },
  };
}

test("whole-book CLI runs a provider and removes stale output before a repeat", async () => {
  const root = await mkdtemp(join(tmpdir(), "saga-whole-book-"));
  const first = await executeFixture(root, "first.json");
  await writeFile(join(first.outputs, "fixture-book", "stale.txt"), "must disappear", "utf8");
  const second = await executeFixture(root, "second.json");

  assert.equal(first.report.aggregate.completedBookCount, 1);
  assert.equal(first.report.aggregate.failedBookCount, 0);
  assert.equal(first.report.books[0]!.outputFileCount, 1);
  assert.equal(second.report.books[0]!.outputFileCount, 1);
  assert.equal(first.report.sourceFingerprint, second.report.sourceFingerprint);
  assert.equal(first.report.semanticResultFingerprint, second.report.semanticResultFingerprint);
  assert.equal(first.report.books[0]!.outputFingerprint, second.report.books[0]!.outputFingerprint);
  assert.equal(first.report.semanticResultFingerprint.length, 64);
});
