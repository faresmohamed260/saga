import type { NormalizedSection } from "../ingestion/types.js";
import type {
  IdentityEntityType,
  IdentityMentionKind,
  IdentityPersonEvidence,
  IdentityProviderDescriptor,
  NormalizedIdentityEvidence,
} from "../identity/types.js";
import type {
  EventTriggerEvidence,
  LiteraryEntityCategory,
  LiteraryEntityEvidence,
  LocalLiteraryEvidenceBundle,
  QuoteSpeakerEvidence,
} from "./types.js";

type TsvRow = Record<string, string>;

type BookNlpToken = {
  paragraphId: number;
  sentenceId: number;
  tokenIdWithinSentence: number;
  tokenId: number;
  providerWord: string;
  lemma: string;
  startOffset: number;
  endOffset: number;
  posTag: string;
  finePosTag: string;
  dependencyRelation: string;
  syntacticHeadTokenId: number;
  event: string;
};

const TOKEN_HEADERS = [
  "paragraph_ID",
  "sentence_ID",
  "token_ID_within_sentence",
  "token_ID_within_document",
  "word",
  "lemma",
  "byte_onset",
  "byte_offset",
  "POS_tag",
  "fine_POS_tag",
  "dependency_relation",
  "syntactic_head_ID",
  "event",
] as const;

const ENTITY_HEADERS = ["COREF", "start_token", "end_token", "prop", "cat", "text"] as const;
const QUOTE_HEADERS = [
  "quote_start",
  "quote_end",
  "mention_start",
  "mention_end",
  "mention_phrase",
  "char_id",
  "quote",
] as const;

function parseTsv(input: string, expectedHeaders: readonly string[], label: string): TsvRow[] {
  const lines = input.replace(/^\uFEFF/u, "").split(/\r?\n/u).filter((line) => line.length > 0);
  if (lines.length === 0) throw new Error(`booknlp_${label}_empty`);

  const headers = lines[0]!.split("\t");
  if (headers.length !== expectedHeaders.length || expectedHeaders.some((header, index) => headers[index] !== header)) {
    throw new Error(`booknlp_${label}_unexpected_header`);
  }

  return lines.slice(1).map((line, rowIndex) => {
    const values = line.split("\t");
    if (values.length !== headers.length) throw new Error(`booknlp_${label}_invalid_row:${rowIndex + 2}`);
    return Object.fromEntries(headers.map((header, index) => [header, values[index] ?? ""]));
  });
}

function parseNonNegativeInteger(value: string, field: string) {
  if (!/^\d+$/u.test(value)) throw new Error(`booknlp_invalid_integer:${field}`);
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed < 0) throw new Error(`booknlp_invalid_integer:${field}`);
  return parsed;
}

function parseOptionalInteger(value: string, field: string) {
  const normalized = value.trim().toLocaleLowerCase("en-US");
  if (normalized === "" || normalized === "none" || normalized === "null") return null;
  return parseNonNegativeInteger(value, field);
}

export function codePointLength(value: string) {
  return Array.from(value).length;
}

export function codePointSlice(value: string, startOffset: number, endOffset: number) {
  if (!Number.isSafeInteger(startOffset) || !Number.isSafeInteger(endOffset) || startOffset < 0 || endOffset < startOffset) {
    throw new Error("invalid_code_point_span");
  }
  return Array.from(value).slice(startOffset, endOffset).join("");
}

function structuralLocatorForSpan(sections: NormalizedSection[], startOffset: number, endOffset: number) {
  const matches = sections.filter(
    (section) => section.start_offset <= startOffset && section.end_offset >= endOffset,
  );
  matches.sort((a, b) => (a.end_offset - a.start_offset) - (b.end_offset - b.start_offset) || a.ordinal - b.ordinal);
  const section = matches[0];
  return section ? `${section.stable_key}:${section.source_locator}` : null;
}

function parseTokens(tokensTsv: string, normalizedText: string) {
  const rows = parseTsv(tokensTsv, TOKEN_HEADERS, "tokens");
  const sourceLength = codePointLength(normalizedText);
  const tokens = rows.map<BookNlpToken>((row, index) => {
    const tokenId = parseNonNegativeInteger(row.token_ID_within_document!, "token_ID_within_document");
    const startOffset = parseNonNegativeInteger(row.byte_onset!, "byte_onset");
    const endOffset = parseNonNegativeInteger(row.byte_offset!, "byte_offset");
    if (endOffset <= startOffset || endOffset > sourceLength) throw new Error(`booknlp_token_span_out_of_range:${tokenId}`);

    const surface = codePointSlice(normalizedText, startOffset, endOffset);
    if (surface.length === 0) throw new Error(`booknlp_token_empty_surface:${tokenId}`);

    return {
      paragraphId: parseNonNegativeInteger(row.paragraph_ID!, "paragraph_ID"),
      sentenceId: parseNonNegativeInteger(row.sentence_ID!, "sentence_ID"),
      tokenIdWithinSentence: parseNonNegativeInteger(row.token_ID_within_sentence!, "token_ID_within_sentence"),
      tokenId,
      providerWord: row.word!,
      lemma: row.lemma!,
      startOffset,
      endOffset,
      posTag: row.POS_tag!,
      finePosTag: row.fine_POS_tag!,
      dependencyRelation: row.dependency_relation!,
      syntacticHeadTokenId: parseNonNegativeInteger(row.syntactic_head_ID!, "syntactic_head_ID"),
      event: row.event!,
    };
  });

  const seen = new Set<number>();
  for (const token of tokens) {
    if (seen.has(token.tokenId)) throw new Error(`booknlp_duplicate_token_id:${token.tokenId}`);
    seen.add(token.tokenId);
  }
  if (tokens.some((token, index) => token.tokenId !== index)) throw new Error("booknlp_non_contiguous_token_ids");
  return tokens;
}

function sourceSpanForTokenRange(
  tokens: BookNlpToken[],
  normalizedText: string,
  startTokenId: number,
  endTokenId: number,
) {
  if (endTokenId < startTokenId) throw new Error("booknlp_invalid_token_range");
  const start = tokens[startTokenId];
  const end = tokens[endTokenId];
  if (!start || !end) throw new Error("booknlp_missing_token_reference");
  const startOffset = start.startOffset;
  const endOffset = end.endOffset;
  return {
    startOffset,
    endOffset,
    surfaceText: codePointSlice(normalizedText, startOffset, endOffset),
  };
}

function mentionKind(prop: string): IdentityMentionKind {
  switch (prop.toLocaleUpperCase("en-US")) {
    case "PROP": return "proper_name";
    case "PRON": return "pronoun";
    case "NOM": return "nominal";
    default: return "nominal";
  }
}

function literaryCategory(cat: string): LiteraryEntityCategory {
  switch (cat.toLocaleUpperCase("en-US")) {
    case "PER": return "person";
    case "LOC": return "location";
    case "FAC": return "facility";
    case "GPE": return "geopolitical";
    case "ORG": return "organization";
    case "VEH": return "vehicle";
    default: return "unknown";
  }
}

function identityEntityType(category: LiteraryEntityCategory): IdentityEntityType {
  if (category === "person") return "person";
  if (category === "unknown") return "unknown";
  return "non_person";
}

function personEvidence(kind: IdentityMentionKind, entityType: IdentityEntityType): IdentityPersonEvidence {
  if (entityType !== "person") return "none";
  if (kind === "proper_name") return "strong";
  if (kind === "nominal") return "supporting";
  return "weak";
}

function normalizeCluster(value: string) {
  const trimmed = value.trim();
  if (trimmed === "" || trimmed.toLocaleLowerCase("en-US") === "none") return null;
  return `booknlp:${trimmed}`;
}

export type NormalizeBookNlpOutputInput = {
  normalizedInputFingerprint: string;
  normalizedText: string;
  sections: NormalizedSection[];
  provider: IdentityProviderDescriptor;
  tokensTsv: string;
  entitiesTsv: string;
  quotesTsv: string;
};

export function normalizeBookNlpOutput(input: NormalizeBookNlpOutputInput): LocalLiteraryEvidenceBundle {
  const tokens = parseTokens(input.tokensTsv, input.normalizedText);
  const entityRows = parseTsv(input.entitiesTsv, ENTITY_HEADERS, "entities");
  const quoteRows = parseTsv(input.quotesTsv, QUOTE_HEADERS, "quotes");

  const entities: LiteraryEntityEvidence[] = [];
  const identityMentions: NormalizedIdentityEvidence["mentions"] = [];

  entityRows.forEach((row, rowIndex) => {
    const startToken = parseNonNegativeInteger(row.start_token!, "entity.start_token");
    const endToken = parseNonNegativeInteger(row.end_token!, "entity.end_token");
    const span = sourceSpanForTokenRange(tokens, input.normalizedText, startToken, endToken);
    const kind = mentionKind(row.prop!);
    const category = literaryCategory(row.cat!);
    const entityType = identityEntityType(category);
    const evidenceId = `booknlp:entity:${rowIndex}:${startToken}-${endToken}`;
    const structuralLocator = structuralLocatorForSpan(input.sections, span.startOffset, span.endOffset);
    const boundaryQuality = structuralLocator === null ? "malformed" as const : "clean" as const;
    const providerClusterId = normalizeCluster(row.COREF!);

    entities.push({
      evidenceId,
      surfaceText: span.surfaceText,
      startOffset: span.startOffset,
      endOffset: span.endOffset,
      structuralLocator,
      mentionKind: kind,
      category,
      providerClusterId,
      boundaryQuality,
    });

    identityMentions.push({
      evidenceId,
      surfaceText: span.surfaceText,
      startOffset: span.startOffset,
      endOffset: span.endOffset,
      structuralLocator,
      mentionKind: kind,
      entityType,
      personEvidence: personEvidence(kind, entityType),
      boundaryQuality,
      providerClusterId,
    });
  });

  const quotes: QuoteSpeakerEvidence[] = quoteRows.map((row, rowIndex) => {
    const quoteStart = parseNonNegativeInteger(row.quote_start!, "quote.quote_start");
    const quoteEnd = parseNonNegativeInteger(row.quote_end!, "quote.quote_end");
    const quoteSpan = sourceSpanForTokenRange(tokens, input.normalizedText, quoteStart, quoteEnd);
    const mentionStart = parseOptionalInteger(row.mention_start!, "quote.mention_start");
    const mentionEnd = parseOptionalInteger(row.mention_end!, "quote.mention_end");
    if ((mentionStart === null) !== (mentionEnd === null)) throw new Error("booknlp_quote_partial_speaker_span");
    const speakerSpan = mentionStart === null || mentionEnd === null
      ? null
      : sourceSpanForTokenRange(tokens, input.normalizedText, mentionStart, mentionEnd);

    return {
      evidenceId: `booknlp:quote:${rowIndex}:${quoteStart}-${quoteEnd}`,
      quoteText: quoteSpan.surfaceText,
      startOffset: quoteSpan.startOffset,
      endOffset: quoteSpan.endOffset,
      structuralLocator: structuralLocatorForSpan(input.sections, quoteSpan.startOffset, quoteSpan.endOffset),
      speakerSurfaceText: speakerSpan?.surfaceText ?? null,
      speakerStartOffset: speakerSpan?.startOffset ?? null,
      speakerEndOffset: speakerSpan?.endOffset ?? null,
      speakerProviderClusterId: normalizeCluster(row.char_id!),
    };
  });

  const eventTriggers: EventTriggerEvidence[] = tokens
    .filter((token) => token.event.toLocaleUpperCase("en-US") === "EVENT")
    .map((token) => ({
      evidenceId: `booknlp:event:${token.tokenId}`,
      surfaceText: codePointSlice(input.normalizedText, token.startOffset, token.endOffset),
      lemma: token.lemma,
      startOffset: token.startOffset,
      endOffset: token.endOffset,
      structuralLocator: structuralLocatorForSpan(input.sections, token.startOffset, token.endOffset),
      sentenceId: token.sentenceId,
      tokenId: token.tokenId,
      dependencyRelation: token.dependencyRelation,
      syntacticHeadTokenId: token.syntacticHeadTokenId,
    }));

  return {
    provider: input.provider,
    normalizedInputFingerprint: input.normalizedInputFingerprint,
    identityEvidence: {
      provider: input.provider,
      normalizedInputFingerprint: input.normalizedInputFingerprint,
      mentions: identityMentions,
    },
    entities,
    quotes,
    eventTriggers,
  };
}
