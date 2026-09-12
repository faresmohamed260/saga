import assert from "node:assert/strict";
import test from "node:test";

import {
  buildWholeBookBenchmarkReport,
  validateWholeBookSuite,
  wholeBookCommandFingerprint,
  type WholeBookSuiteManifest,
} from "../src/evaluation/whole-book-benchmark.js";

function manifest(): WholeBookSuiteManifest {
  return {
    schemaVersion: "saga-whole-book-suite-v1",
    suiteId: "test-suite",
    purpose: "exercise diverse complete books",
    sourcePolicy: "sources are provisioned outside the repo and hashed at execution time",
    books: [
      {
        id: "book-a",
        title: "Book A",
        sourceFile: "a.txt",
        sourceLocator: "test:a",
        tags: ["first-person"],
        licenseNote: "test fixture",
      },
      {
        id: "book-b",
        title: "Book B",
        sourceFile: "nested/b.txt",
        sourceLocator: "test:b",
        tags: ["ensemble"],
        licenseNote: "test fixture",
      },
    ],
  };
}

const provider = {
  name: "provider",
  model: "model",
  revision: "r1",
  license: "test",
};

const commandTemplate = ["provider-cli", "--input", "{source}", "--output", "{output}", "--id", "{book_id}"];

test("whole-book manifest accepts safe relative source paths", () => {
  assert.doesNotThrow(() => validateWholeBookSuite(manifest()));
});

test("whole-book manifest rejects path traversal and duplicate sources", () => {
  const traversal = manifest();
  traversal.books[0]!.sourceFile = "../secret.txt";
  assert.throws(() => validateWholeBookSuite(traversal), /unsafe_whole_book_source_path:book-a/);

  const duplicate = manifest();
  duplicate.books[1]!.sourceFile = "a.txt";
  assert.throws(() => validateWholeBookSuite(duplicate), /duplicate_whole_book_source_file:book-b/);
});

test("whole-book command requires source and output placeholders", () => {
  assert.equal(wholeBookCommandFingerprint({ provider, commandTemplate }).length, 64);
  assert.throws(
    () => wholeBookCommandFingerprint({ provider, commandTemplate: ["provider-cli", "{source}"] }),
    /whole_book_command_missing_output_placeholder/,
  );
});

test("whole-book report separates semantic fingerprints from runtime resources", () => {
  const input = {
    manifest: manifest(),
    provider,
    commandTemplate,
    platform: "linux test",
    cpuCount: 4,
    gpu: null,
    records: [
      {
        bookId: "book-a",
        title: "Book A",
        tags: ["first-person"],
        source: { relativePath: "a.txt", bytes: 10, sha256: "a".repeat(64) },
        status: "completed" as const,
        exitCode: 0,
        signal: null,
        wallClockSeconds: 10,
        peakResidentMemoryMb: 100,
        peakVramMb: null,
        outputBytes: 20,
        outputFileCount: 1,
        outputFingerprint: "b".repeat(64),
      },
      {
        bookId: "book-b",
        title: "Book B",
        tags: ["ensemble"],
        source: { relativePath: "nested/b.txt", bytes: 30, sha256: "c".repeat(64) },
        status: "completed" as const,
        exitCode: 0,
        signal: null,
        wallClockSeconds: 20,
        peakResidentMemoryMb: 200,
        peakVramMb: 300,
        outputBytes: 40,
        outputFileCount: 2,
        outputFingerprint: "d".repeat(64),
      },
    ],
  };

  const first = buildWholeBookBenchmarkReport(input);
  const second = buildWholeBookBenchmarkReport({
    ...input,
    records: input.records.map((record) => ({
      ...record,
      wallClockSeconds: record.wallClockSeconds + 999,
      peakResidentMemoryMb: (record.peakResidentMemoryMb ?? 0) + 999,
    })),
  });

  assert.equal(first.sourceFingerprint, second.sourceFingerprint);
  assert.equal(first.semanticResultFingerprint, second.semanticResultFingerprint);
  assert.equal(first.aggregate.completedBookCount, 2);
  assert.equal(first.aggregate.inputBytes, 40);
  assert.equal(first.aggregate.outputBytes, 60);
  assert.equal(first.aggregate.peakResidentMemoryMb, 200);
  assert.equal(first.aggregate.peakVramMb, 300);
  assert.notEqual(first.aggregate.wallClockSeconds, second.aggregate.wallClockSeconds);
});

test("whole-book report fails closed when a suite entry has no record", () => {
  assert.throws(
    () => buildWholeBookBenchmarkReport({
      manifest: manifest(),
      provider,
      commandTemplate,
      platform: "linux test",
      cpuCount: 4,
      gpu: null,
      records: [],
    }),
    /missing_whole_book_record:book-a/,
  );
});
