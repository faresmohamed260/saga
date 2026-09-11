import { normalizeEpubSource } from "./epub.js";
import { canonicalJson, sha256Hex } from "./hash.js";
import { normalizeTextSource } from "./text.js";
import {
  NormalizationError,
  type NormalizationResult,
  type NormalizeSourceInput,
} from "./types.js";

export const NORMALIZATION_VERSION = "saga-normalizer-v1";

const NORMALIZATION_CONFIG = {
  version: NORMALIZATION_VERSION,
  unicode: "NFC",
  lineEndings: "LF",
  sectionSeparator: "\\n\\n",
  offsets: "unicode-code-points",
  txtChapterHeadings: "chapter|prologue|epilogue|interlude-v1",
  epub: {
    maxEntries: 2000,
    maxEntryBytes: 16 * 1024 * 1024,
    maxExpandedBytes: 100 * 1024 * 1024,
    spineMediaTypes: ["application/xhtml+xml", "text/html"],
  },
} as const;

export const NORMALIZATION_CONFIG_FINGERPRINT = sha256Hex(
  canonicalJson(NORMALIZATION_CONFIG),
);

export function normalizeSource(input: NormalizeSourceInput): NormalizationResult {
  const actualSha256 = sha256Hex(input.bytes);
  if (actualSha256 !== input.expectedSha256.toLowerCase()) {
    throw new NormalizationError(
      "content_sha_mismatch",
      `Source bytes hash to ${actualSha256}, not the declared fingerprint.`,
    );
  }

  const sections =
    input.format === "txt"
      ? normalizeTextSource(input.bytes)
      : normalizeEpubSource(input.bytes);
  const normalizedText = sections.map((section) => section.normalized_text).join("\n\n");
  const normalizedSha256 = sha256Hex(normalizedText);
  const outputFingerprint = sha256Hex(
    canonicalJson({
      normalizationVersion: NORMALIZATION_VERSION,
      configFingerprint: NORMALIZATION_CONFIG_FINGERPRINT,
      normalizedSha256,
      sections,
    }),
  );

  return {
    normalizationVersion: NORMALIZATION_VERSION,
    configFingerprint: NORMALIZATION_CONFIG_FINGERPRINT,
    normalizedSha256,
    outputFingerprint,
    normalizedText,
    sections,
  };
}
