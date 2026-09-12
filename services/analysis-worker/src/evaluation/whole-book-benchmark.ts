import { isAbsolute, normalize, sep } from "node:path";

import { canonicalJson, sha256Hex } from "../ingestion/hash.js";

export type WholeBookSuiteEntry = {
  id: string;
  title: string;
  sourceFile: string;
  sourceLocator: string;
  tags: string[];
  licenseNote: string;
};

export type WholeBookSuiteManifest = {
  schemaVersion: "saga-whole-book-suite-v1";
  suiteId: string;
  purpose: string;
  sourcePolicy: string;
  books: WholeBookSuiteEntry[];
};

export type WholeBookProviderDescriptor = {
  name: string;
  model: string | null;
  revision: string;
  license: string;
};

export type WholeBookSourceRecord = {
  relativePath: string;
  bytes: number;
  sha256: string;
};

export type WholeBookExecutionRecord = {
  bookId: string;
  title: string;
  tags: string[];
  source: WholeBookSourceRecord;
  status: "completed" | "failed";
  exitCode: number | null;
  signal: string | null;
  wallClockSeconds: number;
  peakResidentMemoryMb: number | null;
  peakVramMb: number | null;
  outputBytes: number;
  outputFileCount: number;
  outputFingerprint: string | null;
};

function nonEmpty(value: string, code: string) {
  if (!value.trim()) throw new Error(code);
}

export function validateWholeBookSuite(manifest: WholeBookSuiteManifest) {
  if (manifest.schemaVersion !== "saga-whole-book-suite-v1") {
    throw new Error("unsupported_whole_book_suite");
  }
  nonEmpty(manifest.suiteId, "invalid_whole_book_suite_id");
  nonEmpty(manifest.purpose, "invalid_whole_book_suite_purpose");
  nonEmpty(manifest.sourcePolicy, "invalid_whole_book_source_policy");
  if (manifest.books.length === 0) throw new Error("empty_whole_book_suite");

  const ids = new Set<string>();
  const sourceFiles = new Set<string>();
  for (const book of manifest.books) {
    nonEmpty(book.id, "invalid_whole_book_id");
    nonEmpty(book.title, `invalid_whole_book_title:${book.id}`);
    nonEmpty(book.sourceFile, `invalid_whole_book_source_file:${book.id}`);
    nonEmpty(book.sourceLocator, `invalid_whole_book_source_locator:${book.id}`);
    nonEmpty(book.licenseNote, `invalid_whole_book_license_note:${book.id}`);
    if (ids.has(book.id)) throw new Error(`duplicate_whole_book_id:${book.id}`);
    ids.add(book.id);
    if (book.tags.length === 0 || book.tags.some((tag) => !tag.trim())) {
      throw new Error(`invalid_whole_book_tags:${book.id}`);
    }

    const normalized = normalize(book.sourceFile);
    if (
      isAbsolute(book.sourceFile) ||
      normalized === ".." ||
      normalized.startsWith(`..${sep}`) ||
      normalized.includes(`${sep}..${sep}`)
    ) {
      throw new Error(`unsafe_whole_book_source_path:${book.id}`);
    }
    if (sourceFiles.has(normalized)) throw new Error(`duplicate_whole_book_source_file:${book.id}`);
    sourceFiles.add(normalized);
  }
}

export function wholeBookCommandFingerprint(input: {
  provider: WholeBookProviderDescriptor;
  commandTemplate: string[];
}) {
  if (input.commandTemplate.length === 0) throw new Error("empty_whole_book_command");
  if (!input.commandTemplate.some((token) => token.includes("{source}"))) {
    throw new Error("whole_book_command_missing_source_placeholder");
  }
  if (!input.commandTemplate.some((token) => token.includes("{output}"))) {
    throw new Error("whole_book_command_missing_output_placeholder");
  }
  return sha256Hex(canonicalJson(input));
}

export function buildWholeBookBenchmarkReport(input: {
  manifest: WholeBookSuiteManifest;
  provider: WholeBookProviderDescriptor;
  commandTemplate: string[];
  platform: string;
  cpuCount: number;
  gpu: string | null;
  records: WholeBookExecutionRecord[];
}) {
  validateWholeBookSuite(input.manifest);
  const commandFingerprint = wholeBookCommandFingerprint({
    provider: input.provider,
    commandTemplate: input.commandTemplate,
  });

  const manifestIds = input.manifest.books.map((book) => book.id);
  const recordsById = new Map(input.records.map((record) => [record.bookId, record]));
  if (recordsById.size !== input.records.length) throw new Error("duplicate_whole_book_record");
  for (const id of manifestIds) {
    if (!recordsById.has(id)) throw new Error(`missing_whole_book_record:${id}`);
  }
  if (input.records.some((record) => !manifestIds.includes(record.bookId))) {
    throw new Error("unexpected_whole_book_record");
  }

  const ordered = manifestIds.map((id) => recordsById.get(id)!);
  const completed = ordered.filter((record) => record.status === "completed");
  const failed = ordered.filter((record) => record.status === "failed");
  const sourceFingerprint = sha256Hex(canonicalJson(
    ordered.map((record) => ({ bookId: record.bookId, sourceSha256: record.source.sha256 })),
  ));
  const semanticResultFingerprint = sha256Hex(canonicalJson(
    ordered.map((record) => ({
      bookId: record.bookId,
      status: record.status,
      sourceSha256: record.source.sha256,
      outputFingerprint: record.outputFingerprint,
    })),
  ));

  return {
    schemaVersion: "saga-whole-book-benchmark-report-v1" as const,
    suite: {
      id: input.manifest.suiteId,
      purpose: input.manifest.purpose,
      sourcePolicy: input.manifest.sourcePolicy,
      bookCount: input.manifest.books.length,
      tags: [...new Set(input.manifest.books.flatMap((book) => book.tags))].sort(),
    },
    provider: input.provider,
    commandFingerprint,
    sourceFingerprint,
    semanticResultFingerprint,
    hardware: {
      platform: input.platform,
      cpuCount: input.cpuCount,
      gpu: input.gpu,
    },
    aggregate: {
      attemptedBookCount: ordered.length,
      completedBookCount: completed.length,
      failedBookCount: failed.length,
      inputBytes: ordered.reduce((sum, record) => sum + record.source.bytes, 0),
      outputBytes: ordered.reduce((sum, record) => sum + record.outputBytes, 0),
      wallClockSeconds: ordered.reduce((sum, record) => sum + record.wallClockSeconds, 0),
      peakResidentMemoryMb: Math.max(0, ...ordered.map((record) => record.peakResidentMemoryMb ?? 0)),
      peakVramMb: Math.max(0, ...ordered.map((record) => record.peakVramMb ?? 0)),
    },
    books: ordered,
  };
}
