import { sha256Hex } from "./hash.js";
import { NormalizationError, type NormalizedSection } from "./types.js";

const CHAPTER_HEADING = /^(?:chapter\s+(?:\d+|[ivxlcdm]+|[a-z][a-z\s'-]{0,50})|prologue|epilogue|interlude)(?:\s*[:.—-]\s*.*)?$/i;

export function codePointLength(value: string) {
  return Array.from(value).length;
}

export function decodeUtf8Strict(bytes: Uint8Array) {
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(bytes).replace(/^\uFEFF/, "");
  } catch {
    throw new NormalizationError("invalid_utf8", "Source bytes are not valid UTF-8.");
  }
}

export function canonicalizePlainText(value: string) {
  return value
    .normalize("NFC")
    .replace(/\r\n?/g, "\n")
    .replace(/\u00A0/g, " ")
    .split("\n")
    .map((line) => line.replace(/[\t ]+$/g, ""))
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function stableSectionKey(prefix: string, ordinal: number, locator: string, text: string) {
  const digest = sha256Hex(`${locator}\n${text}`).slice(0, 16);
  return `${prefix}-${String(ordinal).padStart(4, "0")}-${digest}`;
}

function finalizeSections(
  raw: Array<{
    title: string | null;
    text: string;
    sourceLocator: string;
    kind: "document" | "chapter" | "section";
  }>,
  prefix: string,
) {
  let cursor = 0;
  return raw.map<NormalizedSection>((section, ordinal) => {
    const start = cursor;
    const length = codePointLength(section.text);
    const end = start + length;
    cursor = end + 2;
    return {
      stable_key: stableSectionKey(prefix, ordinal, section.sourceLocator, section.text),
      ordinal,
      section_kind: section.kind,
      title: section.title,
      source_locator: section.sourceLocator,
      start_offset: start,
      end_offset: end,
      normalized_text: section.text,
    };
  });
}

function splitChapterSections(text: string) {
  const lines = text.split("\n");
  const headings: number[] = [];
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index]?.trim() ?? "";
    if (line && line.length <= 120 && CHAPTER_HEADING.test(line)) headings.push(index);
  }

  if (headings.length === 0) {
    return [
      {
        title: null,
        text,
        sourceLocator: "txt:document",
        kind: "document" as const,
      },
    ];
  }

  const sections: Array<{
    title: string | null;
    text: string;
    sourceLocator: string;
    kind: "chapter" | "section";
  }> = [];

  const firstHeading = headings[0] ?? 0;
  if (firstHeading > 0) {
    const preface = canonicalizePlainText(lines.slice(0, firstHeading).join("\n"));
    if (preface) {
      sections.push({
        title: null,
        text: preface,
        sourceLocator: `txt:lines:1-${firstHeading}`,
        kind: "section",
      });
    }
  }

  for (let headingIndex = 0; headingIndex < headings.length; headingIndex += 1) {
    const startLine = headings[headingIndex] ?? 0;
    const nextHeading = headings[headingIndex + 1] ?? lines.length;
    const sectionText = canonicalizePlainText(lines.slice(startLine, nextHeading).join("\n"));
    if (!sectionText) continue;
    sections.push({
      title: lines[startLine]?.trim() || null,
      text: sectionText,
      sourceLocator: `txt:lines:${startLine + 1}-${nextHeading}`,
      kind: "chapter",
    });
  }

  return sections;
}

export function normalizeTextSource(bytes: Uint8Array) {
  const normalized = canonicalizePlainText(decodeUtf8Strict(bytes));
  if (!normalized) {
    throw new NormalizationError("empty_source", "Text source is empty after normalization.");
  }
  return finalizeSections(splitChapterSections(normalized), "txt");
}

export function finalizeNormalizedSections(
  raw: Array<{
    title: string | null;
    text: string;
    sourceLocator: string;
    kind: "document" | "chapter" | "section";
  }>,
  prefix: string,
) {
  const nonEmpty = raw
    .map((section) => ({ ...section, text: canonicalizePlainText(section.text) }))
    .filter((section) => section.text.length > 0);

  if (nonEmpty.length === 0) {
    throw new NormalizationError("empty_source", "Source is empty after normalization.");
  }
  return finalizeSections(nonEmpty, prefix);
}
