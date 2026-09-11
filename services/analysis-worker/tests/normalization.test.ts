import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { strToU8, zipSync } from "fflate";

import { sha256Hex } from "../src/ingestion/hash.js";
import { normalizeSource } from "../src/ingestion/normalize.js";
import { NormalizationError } from "../src/ingestion/types.js";

const here = dirname(fileURLToPath(import.meta.url));
const fixtures = join(here, "fixtures");

function fixture(relativePath: string) {
  return new Uint8Array(readFileSync(join(fixtures, relativePath)));
}

function buildGoldenEpub() {
  return zipSync({
    mimetype: fixture("epub/mimetype"),
    "META-INF/container.xml": fixture("epub/META-INF/container.xml"),
    "OEBPS/content.opf": fixture("epub/OEBPS/content.opf"),
    "OEBPS/chapter1.xhtml": fixture("epub/OEBPS/chapter1.xhtml"),
    "OEBPS/chapter2.xhtml": fixture("epub/OEBPS/chapter2.xhtml"),
  });
}

test("TXT normalization is deterministic and preserves chapter evidence with code-point offsets", () => {
  const bytes = fixture("story.txt");
  const input = { bytes, format: "txt" as const, expectedSha256: sha256Hex(bytes) };
  const result = normalizeSource(input);
  const rerun = normalizeSource(input);

  assert.deepEqual(rerun, result);
  assert.equal(
    result.normalizedText,
    "Preface\n\nCHAPTER I\nAda  arrived.\n\nCHAPTER II: Glass\nBéla waited.",
  );
  assert.equal(result.sections.length, 3);
  assert.deepEqual(
    result.sections.map(({ ordinal, section_kind, title, source_locator, start_offset, end_offset }) => ({
      ordinal,
      section_kind,
      title,
      source_locator,
      start_offset,
      end_offset,
    })),
    [
      {
        ordinal: 0,
        section_kind: "section",
        title: null,
        source_locator: "txt:lines:1-2",
        start_offset: 0,
        end_offset: 7,
      },
      {
        ordinal: 1,
        section_kind: "chapter",
        title: "CHAPTER I",
        source_locator: "txt:lines:3-5",
        start_offset: 9,
        end_offset: 32,
      },
      {
        ordinal: 2,
        section_kind: "chapter",
        title: "CHAPTER II: Glass",
        source_locator: "txt:lines:6-7",
        start_offset: 34,
        end_offset: 64,
      },
    ],
  );
  assert.match(result.normalizedSha256, /^[0-9a-f]{64}$/);
  assert.match(result.outputFingerprint, /^[0-9a-f]{64}$/);
  assert.ok(result.sections.every((section) => /^[a-z]+-\d{4}-[0-9a-f]{16}$/.test(section.stable_key)));
});

test("worker refuses source bytes that do not match the immutable source fingerprint", () => {
  const bytes = fixture("story.txt");
  assert.throws(
    () => normalizeSource({ bytes, format: "txt", expectedSha256: "0".repeat(64) }),
    (error: unknown) => error instanceof NormalizationError && error.code === "content_sha_mismatch",
  );
});

test("TXT normalization rejects invalid UTF-8", () => {
  const bytes = new Uint8Array([0xc3, 0x28]);
  assert.throws(
    () => normalizeSource({ bytes, format: "txt", expectedSha256: sha256Hex(bytes) }),
    (error: unknown) => error instanceof NormalizationError && error.code === "invalid_utf8",
  );
});

test("EPUB normalization follows package spine order and emits stable source locators", () => {
  const bytes = buildGoldenEpub();
  const input = { bytes, format: "epub" as const, expectedSha256: sha256Hex(bytes) };
  const result = normalizeSource(input);
  const rerun = normalizeSource(input);

  assert.deepEqual(rerun, result);
  assert.equal(result.sections.length, 2);
  assert.deepEqual(
    result.sections.map((section) => ({
      ordinal: section.ordinal,
      title: section.title,
      locator: section.source_locator,
      kind: section.section_kind,
    })),
    [
      {
        ordinal: 0,
        title: "Chapter One",
        locator: "epub:OEBPS/chapter1.xhtml",
        kind: "chapter",
      },
      {
        ordinal: 1,
        title: "Chapter Two",
        locator: "epub:OEBPS/chapter2.xhtml",
        kind: "chapter",
      },
    ],
  );
  assert.equal(
    result.normalizedText,
    "Chapter One\n\nAda & Béla arrived.\n\nLine two.\n\nChapter Two\n\n“Wait,” Ada said.",
  );
  assert.equal(result.sections[0]?.start_offset, 0);
  assert.equal(
    result.sections[1]?.start_offset,
    (result.sections[0]?.end_offset ?? 0) + 2,
  );
});

test("EPUB normalization fails closed on missing container metadata", () => {
  const bytes = zipSync({
    mimetype: strToU8("application/epub+zip"),
    "OEBPS/chapter.xhtml": strToU8("<html><body><p>No container</p></body></html>"),
  });

  assert.throws(
    () => normalizeSource({ bytes, format: "epub", expectedSha256: sha256Hex(bytes) }),
    (error: unknown) =>
      error instanceof NormalizationError && error.code === "epub_missing_container",
  );
});
