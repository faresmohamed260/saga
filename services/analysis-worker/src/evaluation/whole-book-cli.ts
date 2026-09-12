import { createHash } from "node:crypto";
import { createWriteStream } from "node:fs";
import { mkdir, readFile, readdir, rm, stat, writeFile } from "node:fs/promises";
import { availableParallelism, cpus, platform, release } from "node:os";
import { dirname, join, relative, resolve } from "node:path";
import { finished } from "node:stream/promises";
import { spawn } from "node:child_process";

import {
  buildWholeBookBenchmarkReport,
  validateWholeBookSuite,
  type WholeBookExecutionRecord,
  type WholeBookProviderDescriptor,
  type WholeBookSuiteManifest,
} from "./whole-book-benchmark.js";

function parseArgs(argv: string[]) {
  const separator = argv.indexOf("--");
  if (separator < 0) throw new Error("whole_book_command_separator_required");
  const ownArgs = argv.slice(0, separator);
  const commandTemplate = argv.slice(separator + 1);
  let manifest: string | null = null;
  let sourcesRoot: string | null = null;
  let outputRoot: string | null = null;
  let reportOut: string | null = null;
  let providerName: string | null = null;
  let providerModel: string | null = null;
  let providerRevision: string | null = null;
  let providerLicense: string | null = null;

  for (let index = 0; index < ownArgs.length; index += 1) {
    const token = ownArgs[index];
    if (token === "--manifest") manifest = ownArgs[++index] ?? null;
    else if (token === "--sources-root") sourcesRoot = ownArgs[++index] ?? null;
    else if (token === "--output-root") outputRoot = ownArgs[++index] ?? null;
    else if (token === "--report-out") reportOut = ownArgs[++index] ?? null;
    else if (token === "--provider-name") providerName = ownArgs[++index] ?? null;
    else if (token === "--provider-model") providerModel = ownArgs[++index] ?? null;
    else if (token === "--provider-revision") providerRevision = ownArgs[++index] ?? null;
    else if (token === "--provider-license") providerLicense = ownArgs[++index] ?? null;
    else throw new Error(`unknown_argument:${token}`);
  }

  if (!manifest || !sourcesRoot || !outputRoot || !reportOut || !providerName || !providerRevision || !providerLicense) {
    throw new Error(
      "usage: whole-book-cli --manifest <suite.json> --sources-root <dir> --output-root <dir> --report-out <report.json> --provider-name <name> [--provider-model <model>] --provider-revision <revision> --provider-license <license> -- <command ... {source} ... {output} ...>",
    );
  }
  if (commandTemplate.length === 0) throw new Error("empty_whole_book_command");

  return {
    manifest: resolve(manifest),
    sourcesRoot: resolve(sourcesRoot),
    outputRoot: resolve(outputRoot),
    reportOut: resolve(reportOut),
    provider: {
      name: providerName,
      model: providerModel,
      revision: providerRevision,
      license: providerLicense,
    } satisfies WholeBookProviderDescriptor,
    commandTemplate,
  };
}

async function sha256File(path: string) {
  const bytes = await readFile(path);
  return { bytes: bytes.byteLength, sha256: createHash("sha256").update(bytes).digest("hex") };
}

async function listFilesRecursive(root: string, current = root): Promise<string[]> {
  const names = (await readdir(current)).sort();
  const result: string[] = [];
  for (const name of names) {
    const path = join(current, name);
    const info = await stat(path);
    if (info.isDirectory()) result.push(...await listFilesRecursive(root, path));
    else if (info.isFile()) result.push(path);
  }
  return result;
}

async function fingerprintOutput(root: string) {
  const files = (await listFilesRecursive(root)).filter((path) => {
    const name = relative(root, path).replaceAll("\\", "/");
    return name !== "benchmark.stdout.log" && name !== "benchmark.stderr.log";
  });
  const rows = [];
  let outputBytes = 0;
  for (const path of files) {
    const digest = await sha256File(path);
    outputBytes += digest.bytes;
    rows.push({
      path: relative(root, path).replaceAll("\\", "/"),
      bytes: digest.bytes,
      sha256: digest.sha256,
    });
  }
  const fingerprint = createHash("sha256").update(JSON.stringify(rows)).digest("hex");
  return { fileCount: rows.length, outputBytes, fingerprint };
}

function renderCommand(template: string[], input: { source: string; output: string; bookId: string }) {
  return template.map((token) => token
    .replaceAll("{source}", input.source)
    .replaceAll("{output}", input.output)
    .replaceAll("{book_id}", input.bookId));
}

function delay(milliseconds: number) {
  return new Promise((resolveDelay) => setTimeout(resolveDelay, milliseconds));
}

async function capture(command: string, args: string[]) {
  return new Promise<string>((resolveCapture, rejectCapture) => {
    const child = spawn(command, args, { stdio: ["ignore", "pipe", "ignore"] });
    let stdout = "";
    child.stdout.setEncoding("utf8");
    child.stdout.on("data", (chunk) => { stdout += chunk; });
    child.once("error", rejectCapture);
    child.once("exit", (code) => {
      if (code === 0) resolveCapture(stdout);
      else rejectCapture(new Error(`${command}_exit_${code ?? "null"}`));
    });
  });
}

async function processGroupSnapshot(pgid: number) {
  if (process.platform === "win32") return { pids: new Set<number>(), rssMb: null as number | null };
  try {
    const output = await capture("ps", ["-eo", "pid=,pgid=,rss="]);
    const pids = new Set<number>();
    let rssKb = 0;
    for (const line of output.split("\n")) {
      const [pidRaw, pgidRaw, rssRaw] = line.trim().split(/\s+/);
      const pid = Number(pidRaw);
      const rowPgid = Number(pgidRaw);
      const rss = Number(rssRaw);
      if (Number.isSafeInteger(pid) && rowPgid === pgid && Number.isFinite(rss)) {
        pids.add(pid);
        rssKb += rss;
      }
    }
    return { pids, rssMb: rssKb / 1024 };
  } catch {
    return { pids: new Set<number>(), rssMb: null };
  }
}

async function gpuName() {
  try {
    const output = await capture("nvidia-smi", ["--query-gpu=name", "--format=csv,noheader"]);
    const first = output.split("\n").map((value) => value.trim()).find(Boolean);
    return first ?? null;
  } catch {
    return null;
  }
}

async function processVramMb(pids: Set<number>) {
  if (pids.size === 0) return null;
  try {
    const output = await capture("nvidia-smi", [
      "--query-compute-apps=pid,used_gpu_memory",
      "--format=csv,noheader,nounits",
    ]);
    let total = 0;
    let observed = false;
    for (const line of output.split("\n")) {
      const [pidRaw, memoryRaw] = line.split(",").map((value) => value.trim());
      const pid = Number(pidRaw);
      const memory = Number(memoryRaw);
      if (pids.has(pid) && Number.isFinite(memory)) {
        total += memory;
        observed = true;
      }
    }
    return observed ? total : null;
  } catch {
    return null;
  }
}

async function runBook(input: {
  bookId: string;
  title: string;
  tags: string[];
  source: string;
  sourceRelativePath: string;
  output: string;
  commandTemplate: string[];
}): Promise<WholeBookExecutionRecord> {
  await rm(input.output, { recursive: true, force: true });
  await mkdir(input.output, { recursive: true });
  const source = await sha256File(input.source);
  const command = renderCommand(input.commandTemplate, {
    source: input.source,
    output: input.output,
    bookId: input.bookId,
  });
  const stdout = createWriteStream(join(input.output, "benchmark.stdout.log"));
  const stderr = createWriteStream(join(input.output, "benchmark.stderr.log"));
  const started = performance.now();
  const detached = process.platform !== "win32";
  const child = spawn(command[0]!, command.slice(1), {
    stdio: ["ignore", "pipe", "pipe"],
    detached,
  });
  child.stdout.pipe(stdout);
  child.stderr.pipe(stderr);

  let settled = false;
  let exitCode: number | null = null;
  let signal: NodeJS.Signals | null = null;
  let peakRssMb: number | null = null;
  let peakVramMb: number | null = null;
  const exitPromise = new Promise<void>((resolveExit, rejectExit) => {
    child.once("error", (error) => {
      settled = true;
      rejectExit(error);
    });
    child.once("exit", (code, exitSignal) => {
      exitCode = code;
      signal = exitSignal;
      settled = true;
      resolveExit();
    });
  });

  while (!settled) {
    const pgid = child.pid ?? -1;
    if (pgid > 0) {
      const snapshot = await processGroupSnapshot(pgid);
      if (snapshot.rssMb !== null) peakRssMb = Math.max(peakRssMb ?? 0, snapshot.rssMb);
      const vram = await processVramMb(snapshot.pids);
      if (vram !== null) peakVramMb = Math.max(peakVramMb ?? 0, vram);
    }
    if (!settled) await delay(200);
  }
  await exitPromise;
  await Promise.all([finished(stdout), finished(stderr)]);
  const wallClockSeconds = (performance.now() - started) / 1000;
  const output = await fingerprintOutput(input.output);

  return {
    bookId: input.bookId,
    title: input.title,
    tags: input.tags,
    source: {
      relativePath: input.sourceRelativePath.replaceAll("\\", "/"),
      bytes: source.bytes,
      sha256: source.sha256,
    },
    status: exitCode === 0 ? "completed" : "failed",
    exitCode,
    signal,
    wallClockSeconds,
    peakResidentMemoryMb: peakRssMb,
    peakVramMb,
    outputBytes: output.outputBytes,
    outputFileCount: output.fileCount,
    outputFingerprint: output.fingerprint,
  };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const manifest = JSON.parse(await readFile(args.manifest, "utf8")) as WholeBookSuiteManifest;
  validateWholeBookSuite(manifest);
  if (!args.commandTemplate.some((token) => token.includes("{source}"))) {
    throw new Error("whole_book_command_missing_source_placeholder");
  }
  if (!args.commandTemplate.some((token) => token.includes("{output}"))) {
    throw new Error("whole_book_command_missing_output_placeholder");
  }

  await mkdir(args.outputRoot, { recursive: true });
  await mkdir(dirname(args.reportOut), { recursive: true });
  const records: WholeBookExecutionRecord[] = [];

  for (const book of manifest.books) {
    const source = resolve(args.sourcesRoot, book.sourceFile);
    const relativeSource = relative(args.sourcesRoot, source);
    if (relativeSource.startsWith("..") || relativeSource === "") {
      throw new Error(`whole_book_source_outside_root:${book.id}`);
    }
    const info = await stat(source).catch(() => null);
    if (!info?.isFile()) throw new Error(`whole_book_source_missing:${book.id}:${book.sourceFile}`);
    const output = join(args.outputRoot, book.id);
    records.push(await runBook({
      bookId: book.id,
      title: book.title,
      tags: book.tags,
      source,
      sourceRelativePath: relativeSource,
      output,
      commandTemplate: args.commandTemplate,
    }));
  }

  const report = buildWholeBookBenchmarkReport({
    manifest,
    provider: args.provider,
    commandTemplate: args.commandTemplate,
    platform: `${platform()} ${release()}`,
    cpuCount: typeof availableParallelism === "function" ? availableParallelism() : cpus().length,
    gpu: await gpuName(),
    records,
  });
  await writeFile(args.reportOut, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  process.stdout.write(`${JSON.stringify({
    suite: report.suite,
    provider: report.provider,
    aggregate: report.aggregate,
    sourceFingerprint: report.sourceFingerprint,
    semanticResultFingerprint: report.semanticResultFingerprint,
  }, null, 2)}\n`);
  if (report.aggregate.failedBookCount > 0) process.exitCode = 2;
}

main().catch((error) => {
  console.error(error instanceof Error ? error.stack ?? error.message : String(error));
  process.exitCode = 1;
});
