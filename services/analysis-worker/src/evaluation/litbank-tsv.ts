import { sha256Hex } from "../ingestion/hash.js";
import type {
  IdentityBoundaryQuality,
  IdentityEntityType,
  IdentityMentionKind,
  IdentityPersonEvidence,
  NormalizedIdentityEvidence,
} from "../identity/types.js";
import type { GoldIdentityDocument, GoldIdentityMention } from "./types.js";

export const LITBANK_ORACLE_PROVIDER = {
  name: "litbank-oracle",
  model: null,
  revision: "dbamman-litbank-tsv-v1",
} as const;

type RawMention = {
  mentionId: string;
  startLine: number;
  startToken: number;
  endLine: number;
  endToken: number;
  annotatedSurface: string;
  entityClass: string;
  mentionClass: string;
};

type TokenSpan = {
  startCodeUnit: number;
  endCodeUnit: number;
};

function normalizeNewlines(value: string) {
  return value.replace(/\r\n?/g, "\n");
}

function codePointBoundaryMap(text: string) {
  const boundaries = new Map<number, number>();
  let codeUnit = 0;
  let codePoint = 0;
  boundaries.set(0, 0);
  for (const character of text) {
    codeUnit += character.length;
    codePoint += 1;
    boundaries.set(codeUnit, codePoint);
  }
  return boundaries;
}

function lineStarts(text: string) {
  const starts = [0];
  for (let index = 0; index < text.length; index += 1) {
    if (text[index] === "\n") starts.push(index + 1);
  }
  return starts;
}

function tokensForLine(line: string): TokenSpan[] {
  return [...line.matchAll(/\S+/gu)].map((match) => ({
    startCodeUnit: match.index,
    endCodeUnit: match.index + match[0].length,
  }));
}

function collapseWhitespace(value: string) {
  return value.replace(/\s+/gu, " ").trim();
}

function parseAnnotations(annotation: string) {
  const mentions = new Map<string, RawMention>();
  const coref = new Map<string, string>();

  for (const rawLine of normalizeNewlines(annotation).split("\n")) {
    if (!rawLine.trim()) continue;
    const fields = rawLine.split("\t");
    if (fields[0] === "MENTION") {
      if (fields.length < 9) throw new Error(`invalid_litbank_mention:${rawLine}`);
      const [_, mentionId, startLine, startToken, endLine, endToken, surface, entityClass, mentionClass] = fields;
      if (
        !mentionId ||
        !surface ||
        !entityClass ||
        !mentionClass ||
        !/^\d+$/.test(startLine ?? "") ||
        !/^\d+$/.test(startToken ?? "") ||
        !/^\d+$/.test(endLine ?? "") ||
        !/^\d+$/.test(endToken ?? "")
      ) {
        throw new Error(`invalid_litbank_mention:${rawLine}`);
      }
      mentions.set(mentionId, {
        mentionId,
        startLine: Number(startLine),
        startToken: Number(startToken),
        endLine: Number(endLine),
        endToken: Number(endToken),
        annotatedSurface: surface,
        entityClass,
        mentionClass,
      });
    } else if (fields[0] === "COREF") {
      const mentionId = fields[1];
      const clusterId = fields[2];
      if (!mentionId || !clusterId) throw new Error(`invalid_litbank_coref:${rawLine}`);
      coref.set(mentionId, clusterId);
    }
  }

  return { mentions: [...mentions.values()], coref };
}

function mentionKind(value: string): IdentityMentionKind {
  if (value === "PROP") return "proper_name";
  if (value === "NOM") return "nominal";
  if (value === "PRON") return "pronoun";
  throw new Error(`unsupported_litbank_mention_class:${value}`);
}

function entityType(value: string): IdentityEntityType {
  return value === "PER" ? "person" : "non_person";
}

function personEvidence(entity: IdentityEntityType, kind: IdentityMentionKind): IdentityPersonEvidence {
  if (entity !== "person") return "none";
  return kind === "proper_name" ? "strong" : "supporting";
}

function boundaryQuality(): IdentityBoundaryQuality {
  return "clean";
}

function locateMention(
  text: string,
  lines: string[],
  starts: number[],
  boundaries: Map<number, number>,
  mention: RawMention,
) {
  const startLineText = lines[mention.startLine];
  const endLineText = lines[mention.endLine];
  const startLineCodeUnit = starts[mention.startLine];
  const endLineCodeUnit = starts[mention.endLine];
  if (
    startLineText === undefined ||
    endLineText === undefined ||
    startLineCodeUnit === undefined ||
    endLineCodeUnit === undefined
  ) {
    throw new Error(`litbank_line_out_of_range:${mention.mentionId}`);
  }

  const startToken = tokensForLine(startLineText)[mention.startToken];
  const endToken = tokensForLine(endLineText)[mention.endToken];
  if (!startToken || !endToken) {
    throw new Error(`litbank_token_out_of_range:${mention.mentionId}`);
  }

  const startCodeUnit = startLineCodeUnit + startToken.startCodeUnit;
  const endCodeUnit = endLineCodeUnit + endToken.endCodeUnit;
  const startOffset = boundaries.get(startCodeUnit);
  const endOffset = boundaries.get(endCodeUnit);
  if (startOffset === undefined || endOffset === undefined) {
    throw new Error(`litbank_non_boundary_offset:${mention.mentionId}`);
  }

  const surfaceText = text.slice(startCodeUnit, endCodeUnit);
  if (collapseWhitespace(surfaceText) !== collapseWhitespace(mention.annotatedSurface)) {
    throw new Error(
      `litbank_surface_mismatch:${mention.mentionId}:${JSON.stringify({ annotated: mention.annotatedSurface, observed: surfaceText })}`,
    );
  }

  return { startOffset, endOffset, surfaceText };
}

export function convertLitBankTsvDocument(input: {
  documentId: string;
  text: string;
  annotation: string;
}): { gold: GoldIdentityDocument; evidence: NormalizedIdentityEvidence } {
  const text = normalizeNewlines(input.text);
  const lines = text.split("\n");
  const starts = lineStarts(text);
  const boundaries = codePointBoundaryMap(text);
  const parsed = parseAnnotations(input.annotation);

  const goldMentions: GoldIdentityMention[] = [];
  const evidenceMentions: NormalizedIdentityEvidence["mentions"] = [];

  for (const mention of parsed.mentions) {
    const located = locateMention(text, lines, starts, boundaries, mention);
    const kind = mentionKind(mention.mentionClass);
    const entity = entityType(mention.entityClass);
    const clusterId = parsed.coref.get(mention.mentionId) ?? null;
    const evidenceId = `${input.documentId}:${mention.mentionId}`;

    goldMentions.push({
      mentionId: evidenceId,
      surfaceText: located.surfaceText,
      startOffset: located.startOffset,
      endOffset: located.endOffset,
      mentionKind: kind,
      entityType: entity === "person" ? "person" : "non_person",
      goldCharacterId: entity === "person" ? clusterId : null,
    });

    evidenceMentions.push({
      evidenceId,
      surfaceText: located.surfaceText,
      startOffset: located.startOffset,
      endOffset: located.endOffset,
      structuralLocator: `litbank:${input.documentId}:line:${mention.startLine + 1}`,
      mentionKind: kind,
      entityType: entity,
      personEvidence: personEvidence(entity, kind),
      boundaryQuality: boundaryQuality(),
      providerClusterId: clusterId,
    });
  }

  goldMentions.sort(
    (a, b) => a.startOffset - b.startOffset || a.endOffset - b.endOffset || a.mentionId.localeCompare(b.mentionId),
  );
  evidenceMentions.sort(
    (a, b) => a.startOffset - b.startOffset || a.endOffset - b.endOffset || a.evidenceId.localeCompare(b.evidenceId),
  );

  return {
    gold: {
      documentId: input.documentId,
      text,
      mentions: goldMentions,
    },
    evidence: {
      provider: LITBANK_ORACLE_PROVIDER,
      normalizedInputFingerprint: sha256Hex(text),
      mentions: evidenceMentions,
    },
  };
}
