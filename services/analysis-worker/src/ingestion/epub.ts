import { posix } from "node:path";

import { XMLParser } from "fast-xml-parser";
import { strFromU8, unzipSync } from "fflate";

import { finalizeNormalizedSections } from "./text.js";
import { NormalizationError } from "./types.js";

const MAX_EPUB_ENTRIES = 2000;
const MAX_EPUB_ENTRY_BYTES = 16 * 1024 * 1024;
const MAX_EPUB_EXPANDED_BYTES = 100 * 1024 * 1024;

const BLOCK_TAGS = new Set([
  "address",
  "article",
  "aside",
  "blockquote",
  "div",
  "figcaption",
  "footer",
  "h1",
  "h2",
  "h3",
  "h4",
  "h5",
  "h6",
  "header",
  "li",
  "main",
  "nav",
  "p",
  "pre",
  "section",
  "td",
  "th",
  "tr",
]);

const SKIP_TAGS = new Set(["script", "style", "svg", "math"]);

function asArray<T>(value: T | T[] | undefined | null): T[] {
  if (value === undefined || value === null) return [];
  return Array.isArray(value) ? value : [value];
}

function safeArchivePath(raw: string) {
  if (!raw || raw.includes("\\") || raw.includes("\0")) {
    throw new NormalizationError("epub_unsafe_path", `Unsafe EPUB path: ${raw}`);
  }

  let decoded: string;
  try {
    decoded = decodeURIComponent(raw.split(/[?#]/, 1)[0] ?? "");
  } catch {
    throw new NormalizationError("epub_unsafe_path", `Invalid escaped EPUB path: ${raw}`);
  }

  const normalized = posix.normalize(decoded).replace(/^\.\//, "");
  if (!normalized || normalized === ".." || normalized.startsWith("../") || normalized.startsWith("/")) {
    throw new NormalizationError("epub_unsafe_path", `Unsafe EPUB path: ${raw}`);
  }
  return normalized;
}

function resolveArchivePath(baseFile: string, href: string) {
  const cleanHref = safeArchivePath(href);
  return safeArchivePath(posix.join(posix.dirname(baseFile), cleanHref));
}

function decodeXml(entry: Uint8Array | undefined, failureCode: "epub_missing_container" | "epub_missing_package" | "invalid_epub") {
  if (!entry) throw new NormalizationError(failureCode, "Required EPUB XML entry is missing.");
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(entry).replace(/^\uFEFF/, "");
  } catch {
    throw new NormalizationError("invalid_epub", "EPUB XML is not valid UTF-8.");
  }
}

function parseXml(xml: string) {
  try {
    return new XMLParser({
      ignoreAttributes: false,
      attributeNamePrefix: "@_",
      removeNSPrefix: true,
      trimValues: false,
      parseTagValue: false,
      parseAttributeValue: false,
      processEntities: true,
    }).parse(xml) as Record<string, unknown>;
  } catch {
    throw new NormalizationError("invalid_epub", "EPUB XML could not be parsed.");
  }
}

function orderedXml(xml: string) {
  try {
    return new XMLParser({
      preserveOrder: true,
      ignoreAttributes: false,
      attributeNamePrefix: "@_",
      removeNSPrefix: true,
      trimValues: false,
      parseTagValue: false,
      parseAttributeValue: false,
      processEntities: true,
    }).parse(xml) as unknown[];
  } catch {
    throw new NormalizationError("invalid_epub", "EPUB content document could not be parsed.");
  }
}

function objectRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function findOrderedTag(nodes: unknown[], target: string): unknown[] | null {
  for (const node of nodes) {
    const record = objectRecord(node);
    if (!record) continue;
    for (const [key, value] of Object.entries(record)) {
      if (key === target && Array.isArray(value)) return value;
      if (Array.isArray(value)) {
        const nested = findOrderedTag(value, target);
        if (nested) return nested;
      }
    }
  }
  return null;
}

function renderOrdered(nodes: unknown[]): string {
  let output = "";
  for (const node of nodes) {
    const record = objectRecord(node);
    if (!record) continue;

    if (typeof record["#text"] === "string") output += record["#text"];

    for (const [rawTag, value] of Object.entries(record)) {
      if (rawTag === "#text" || rawTag === ":@") continue;
      const tag = rawTag.toLowerCase();
      if (SKIP_TAGS.has(tag)) continue;
      if (tag === "br") {
        output += "\n";
        continue;
      }
      if (!Array.isArray(value)) continue;
      output += renderOrdered(value);
      if (BLOCK_TAGS.has(tag)) output += "\n\n";
    }
  }
  return output;
}

function normalizeRenderedBlockText(value: string) {
  return value
    .replace(/\r\n?/g, "\n")
    .split("\n")
    .map((line) => line.trim())
    .join("\n");
}

function firstTagText(nodes: unknown[], tags: string[]) {
  for (const tag of tags) {
    const found = findOrderedTag(nodes, tag);
    if (!found) continue;
    const text = renderOrdered(found).replace(/\s+/g, " ").trim();
    if (text) return text.slice(0, 1000);
  }
  return null;
}

function readAttribute(record: Record<string, unknown> | null, name: string) {
  const value = record?.[`@_${name}`];
  return typeof value === "string" ? value : null;
}

export function normalizeEpubSource(bytes: Uint8Array) {
  let entryCount = 0;
  let expandedBytes = 0;

  let archive: Record<string, Uint8Array>;
  try {
    archive = unzipSync(bytes, {
      filter(file) {
        entryCount += 1;
        expandedBytes += file.originalSize;
        safeArchivePath(file.name);
        if (
          entryCount > MAX_EPUB_ENTRIES ||
          file.originalSize > MAX_EPUB_ENTRY_BYTES ||
          expandedBytes > MAX_EPUB_EXPANDED_BYTES
        ) {
          throw new NormalizationError("epub_limit_exceeded", "EPUB archive exceeds deterministic safety limits.");
        }
        return true;
      },
    });
  } catch (error) {
    if (error instanceof NormalizationError) throw error;
    throw new NormalizationError("invalid_epub", "EPUB archive could not be decompressed.");
  }

  const mimetype = archive.mimetype ? strFromU8(archive.mimetype).trim() : "";
  if (mimetype !== "application/epub+zip") {
    throw new NormalizationError("invalid_epub", "EPUB mimetype entry is missing or invalid.");
  }

  const containerXml = decodeXml(archive["META-INF/container.xml"], "epub_missing_container");
  const container = parseXml(containerXml);
  const containerRecord = objectRecord(container.container);
  const rootfilesRecord = objectRecord(containerRecord?.rootfiles);
  const rootfiles = asArray(rootfilesRecord?.rootfile);
  const rootfile = objectRecord(rootfiles[0]);
  const opfPathRaw = readAttribute(rootfile, "full-path");
  if (!opfPathRaw) {
    throw new NormalizationError("epub_missing_package", "EPUB container does not identify a package document.");
  }
  const opfPath = safeArchivePath(opfPathRaw);

  const packageXml = decodeXml(archive[opfPath], "epub_missing_package");
  const parsedPackage = parseXml(packageXml);
  const packageRecord = objectRecord(parsedPackage.package);
  const manifestRecord = objectRecord(packageRecord?.manifest);
  const spineRecord = objectRecord(packageRecord?.spine);
  if (!manifestRecord || !spineRecord) {
    throw new NormalizationError("epub_missing_spine", "EPUB package manifest or spine is missing.");
  }

  const manifest = new Map<string, { href: string; mediaType: string }>();
  for (const rawItem of asArray(manifestRecord.item)) {
    const item = objectRecord(rawItem);
    const id = readAttribute(item, "id");
    const href = readAttribute(item, "href");
    const mediaType = readAttribute(item, "media-type");
    if (id && href && mediaType) manifest.set(id, { href, mediaType });
  }

  const rawSections: Array<{
    title: string | null;
    text: string;
    sourceLocator: string;
    kind: "chapter";
  }> = [];

  for (const rawItemRef of asArray(spineRecord.itemref)) {
    const itemRef = objectRecord(rawItemRef);
    const idref = readAttribute(itemRef, "idref");
    if (!idref) continue;
    const manifestItem = manifest.get(idref);
    if (!manifestItem) {
      throw new NormalizationError("invalid_epub", `EPUB spine references missing manifest item: ${idref}`);
    }
    if (!new Set(["application/xhtml+xml", "text/html"]).has(manifestItem.mediaType)) continue;

    const contentPath = resolveArchivePath(opfPath, manifestItem.href);
    const xhtml = decodeXml(archive[contentPath], "invalid_epub");
    const ordered = orderedXml(xhtml);
    const body = findOrderedTag(ordered, "body") ?? ordered;
    const text = normalizeRenderedBlockText(renderOrdered(body));
    rawSections.push({
      title: firstTagText(body, ["h1", "h2", "h3"]) ?? firstTagText(ordered, ["title"]),
      text,
      sourceLocator: `epub:${contentPath}`,
      kind: "chapter",
    });
  }

  if (rawSections.length === 0) {
    throw new NormalizationError("epub_missing_spine", "EPUB spine contains no supported readable content documents.");
  }

  return finalizeNormalizedSections(rawSections, "epub");
}
