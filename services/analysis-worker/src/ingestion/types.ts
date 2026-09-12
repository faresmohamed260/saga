export type SourceFormat = "txt" | "epub";
export type NormalizedSectionKind = "document" | "chapter" | "section";

export type NormalizedSection = {
  stable_key: string;
  ordinal: number;
  section_kind: NormalizedSectionKind;
  title: string | null;
  source_locator: string;
  start_offset: number;
  end_offset: number;
  normalized_text: string;
};

export type NormalizationResult = {
  normalizationVersion: string;
  configFingerprint: string;
  normalizedSha256: string;
  outputFingerprint: string;
  normalizedText: string;
  sections: NormalizedSection[];
};

export type NormalizeSourceInput = {
  bytes: Uint8Array;
  format: SourceFormat;
  expectedSha256: string;
};

export type NormalizationFailureCode =
  | "content_sha_mismatch"
  | "invalid_utf8"
  | "empty_source"
  | "invalid_epub"
  | "epub_limit_exceeded"
  | "epub_missing_container"
  | "epub_missing_package"
  | "epub_missing_spine"
  | "epub_unsafe_path";

export class NormalizationError extends Error {
  readonly code: NormalizationFailureCode;

  constructor(code: NormalizationFailureCode, message: string) {
    super(message);
    this.name = "NormalizationError";
    this.code = code;
  }
}
