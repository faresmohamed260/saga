import type { NormalizedSection } from "../ingestion/types.js";
import type {
  IdentityBoundaryQuality,
  IdentityEntityType,
  IdentityEvidenceMention,
  IdentityMentionKind,
  IdentityPersonEvidence,
  IdentityProviderDescriptor,
  NormalizedIdentityEvidence,
} from "../identity/types.js";
import type {
  EventTriggerEvidence,
  LiteraryEntityCategory,
  LiteraryEntityEvidence,
  LocalLiteraryAnalysisInput,
  LocalLiteraryEvidenceBundle,
  QuoteSpeakerEvidence,
  SyntaxTokenEvidence,
} from "./types.js";

const mentionKinds = new Set<IdentityMentionKind>(["proper_name", "nominal", "pronoun"]);
const entityTypes = new Set<IdentityEntityType>(["person", "non_person", "unknown"]);
const personEvidenceValues = new Set<IdentityPersonEvidence>(["strong", "supporting", "weak", "none"]);
const boundaryQualities = new Set<IdentityBoundaryQuality>(["clean", "malformed"]);
const literaryCategories = new Set<LiteraryEntityCategory>([
  "person",
  "location",
  "facility",
  "geopolitical",
  "organization",
  "vehicle",
  "unknown",
]);

export class LocalLiteraryEvidenceValidationError extends Error {
  readonly code: string;

  constructor(code: string) {
    super(code);
    this.name = "LocalLiteraryEvidenceValidationError";
    this.code = code;
  }
}

function record(value: unknown, code: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new LocalLiteraryEvidenceValidationError(code);
  }
  return value as Record<string, unknown>;
}

function requiredString(value: unknown, code: string) {
  if (typeof value !== "string" || !value.trim()) {
    throw new LocalLiteraryEvidenceValidationError(code);
  }
  return value;
}

function nullableString(value: unknown, code: string) {
  if (value === null) return null;
  return requiredString(value, code);
}

function safeInteger(value: unknown, code: string) {
  if (typeof value !== "number" || !Number.isSafeInteger(value)) {
    throw new LocalLiteraryEvidenceValidationError(code);
  }
  return value;
}

function nonNegativeInteger(value: unknown, code: string) {
  const parsed = safeInteger(value, code);
  if (parsed < 0) throw new LocalLiteraryEvidenceValidationError(code);
  return parsed;
}

function requireFingerprint(value: unknown, code: string) {
  if (typeof value !== "string" || !/^[0-9a-f]{64}$/u.test(value)) {
    throw new LocalLiteraryEvidenceValidationError(code);
  }
  return value;
}

export function validateProviderDescriptor(value: unknown): IdentityProviderDescriptor {
  const row = record(value, "invalid_local_provider_descriptor");
  const name = requiredString(row.name, "invalid_local_provider_descriptor");
  const revision = requiredString(row.revision, "invalid_local_provider_descriptor");
  const model = row.model === null ? null : requiredString(row.model, "invalid_local_provider_model");
  return { name, model, revision };
}

export function sameProviderDescriptor(left: IdentityProviderDescriptor, right: IdentityProviderDescriptor) {
  return left.name === right.name && left.model === right.model && left.revision === right.revision;
}

type SourceIndex = {
  readonly codePointToCodeUnit: number[];
  readonly codePointLength: number;
};

function buildSourceIndex(text: string): SourceIndex {
  const codePointToCodeUnit = [0];
  let codeUnitOffset = 0;
  for (const symbol of text) {
    codeUnitOffset += symbol.length;
    codePointToCodeUnit.push(codeUnitOffset);
  }
  return { codePointToCodeUnit, codePointLength: codePointToCodeUnit.length - 1 };
}

function sourceSlice(text: string, index: SourceIndex, startOffset: number, endOffset: number) {
  const start = index.codePointToCodeUnit[startOffset];
  const end = index.codePointToCodeUnit[endOffset];
  if (start === undefined || end === undefined) return null;
  return text.slice(start, end);
}

type ValidationContext = {
  source: LocalLiteraryAnalysisInput;
  index: SourceIndex;
};

function validateSpan(input: {
  evidenceId: string;
  startOffset: number;
  endOffset: number;
  expectedSurface: string;
  structuralLocator: string | null;
  label: string;
  context: ValidationContext;
}) {
  if (!input.evidenceId.trim()) {
    throw new LocalLiteraryEvidenceValidationError(`invalid_local_${input.label}_evidence_id`);
  }
  if (
    input.startOffset < 0 ||
    input.endOffset <= input.startOffset ||
    input.endOffset > input.context.index.codePointLength
  ) {
    throw new LocalLiteraryEvidenceValidationError(`invalid_local_${input.label}_span:${input.evidenceId}`);
  }
  if (
    sourceSlice(
      input.context.source.normalizedText,
      input.context.index,
      input.startOffset,
      input.endOffset,
    ) !== input.expectedSurface
  ) {
    throw new LocalLiteraryEvidenceValidationError(`local_${input.label}_source_mismatch:${input.evidenceId}`);
  }

  const containing = input.context.source.sections.filter(
    (section) => section.start_offset <= input.startOffset && section.end_offset >= input.endOffset,
  );
  if (containing.length === 0) {
    if (input.structuralLocator !== null) {
      throw new LocalLiteraryEvidenceValidationError(`local_${input.label}_locator_without_section:${input.evidenceId}`);
    }
    return;
  }
  if (input.structuralLocator === null) return;

  const locatorMatches = containing.some(
    (section) =>
      input.structuralLocator === section.stable_key ||
      input.structuralLocator === `${section.stable_key}:${section.source_locator}`,
  );
  if (!locatorMatches) {
    throw new LocalLiteraryEvidenceValidationError(`local_${input.label}_locator_mismatch:${input.evidenceId}`);
  }
}

function uniqueEvidenceIds<T extends { evidenceId: string }>(values: T[], label: string) {
  const seen = new Set<string>();
  for (const value of values) {
    if (seen.has(value.evidenceId)) {
      throw new LocalLiteraryEvidenceValidationError(`duplicate_local_${label}_evidence_id:${value.evidenceId}`);
    }
    seen.add(value.evidenceId);
  }
}

function parseIdentityMention(value: unknown, context: ValidationContext): IdentityEvidenceMention {
  const row = record(value, "invalid_local_identity_evidence");
  const evidenceId = requiredString(row.evidenceId, "invalid_local_identity_evidence_id");
  const surfaceText = requiredString(row.surfaceText, `invalid_local_identity_surface:${evidenceId}`);
  const startOffset = nonNegativeInteger(row.startOffset, `invalid_local_identity_span:${evidenceId}`);
  const endOffset = nonNegativeInteger(row.endOffset, `invalid_local_identity_span:${evidenceId}`);
  const structuralLocator = row.structuralLocator === null
    ? null
    : requiredString(row.structuralLocator, `invalid_local_identity_locator:${evidenceId}`);
  if (!mentionKinds.has(row.mentionKind as IdentityMentionKind)) {
    throw new LocalLiteraryEvidenceValidationError(`invalid_local_identity_values:${evidenceId}`);
  }
  if (!entityTypes.has(row.entityType as IdentityEntityType)) {
    throw new LocalLiteraryEvidenceValidationError(`invalid_local_identity_values:${evidenceId}`);
  }
  if (!personEvidenceValues.has(row.personEvidence as IdentityPersonEvidence)) {
    throw new LocalLiteraryEvidenceValidationError(`invalid_local_identity_values:${evidenceId}`);
  }
  if (!boundaryQualities.has(row.boundaryQuality as IdentityBoundaryQuality)) {
    throw new LocalLiteraryEvidenceValidationError(`invalid_local_identity_values:${evidenceId}`);
  }
  const providerClusterId = nullableString(row.providerClusterId, `invalid_local_identity_cluster:${evidenceId}`);
  const mention: IdentityEvidenceMention = {
    evidenceId,
    surfaceText,
    startOffset,
    endOffset,
    structuralLocator,
    mentionKind: row.mentionKind as IdentityMentionKind,
    entityType: row.entityType as IdentityEntityType,
    personEvidence: row.personEvidence as IdentityPersonEvidence,
    boundaryQuality: row.boundaryQuality as IdentityBoundaryQuality,
    providerClusterId,
  };
  validateSpan({ evidenceId, startOffset, endOffset, expectedSurface: surfaceText, structuralLocator, label: "identity", context });
  return mention;
}

function parseEntity(value: unknown, context: ValidationContext): LiteraryEntityEvidence {
  const row = record(value, "invalid_local_entity_evidence");
  const evidenceId = requiredString(row.evidenceId, "invalid_local_entity_evidence_id");
  const surfaceText = requiredString(row.surfaceText, `invalid_local_entity_surface:${evidenceId}`);
  const startOffset = nonNegativeInteger(row.startOffset, `invalid_local_entity_span:${evidenceId}`);
  const endOffset = nonNegativeInteger(row.endOffset, `invalid_local_entity_span:${evidenceId}`);
  const structuralLocator = row.structuralLocator === null
    ? null
    : requiredString(row.structuralLocator, `invalid_local_entity_locator:${evidenceId}`);
  if (!mentionKinds.has(row.mentionKind as IdentityMentionKind)) {
    throw new LocalLiteraryEvidenceValidationError(`invalid_local_entity_values:${evidenceId}`);
  }
  if (!literaryCategories.has(row.category as LiteraryEntityCategory)) {
    throw new LocalLiteraryEvidenceValidationError(`invalid_local_entity_values:${evidenceId}`);
  }
  if (!boundaryQualities.has(row.boundaryQuality as IdentityBoundaryQuality)) {
    throw new LocalLiteraryEvidenceValidationError(`invalid_local_entity_values:${evidenceId}`);
  }
  const providerClusterId = nullableString(row.providerClusterId, `invalid_local_entity_cluster:${evidenceId}`);
  const entity: LiteraryEntityEvidence = {
    evidenceId,
    surfaceText,
    startOffset,
    endOffset,
    structuralLocator,
    mentionKind: row.mentionKind as IdentityMentionKind,
    category: row.category as LiteraryEntityCategory,
    providerClusterId,
    boundaryQuality: row.boundaryQuality as IdentityBoundaryQuality,
  };
  validateSpan({ evidenceId, startOffset, endOffset, expectedSurface: surfaceText, structuralLocator, label: "entity", context });
  return entity;
}

function parseQuote(value: unknown, context: ValidationContext): QuoteSpeakerEvidence {
  const row = record(value, "invalid_local_quote_evidence");
  const evidenceId = requiredString(row.evidenceId, "invalid_local_quote_evidence_id");
  const quoteText = requiredString(row.quoteText, `invalid_local_quote_surface:${evidenceId}`);
  const startOffset = nonNegativeInteger(row.startOffset, `invalid_local_quote_span:${evidenceId}`);
  const endOffset = nonNegativeInteger(row.endOffset, `invalid_local_quote_span:${evidenceId}`);
  const structuralLocator = row.structuralLocator === null
    ? null
    : requiredString(row.structuralLocator, `invalid_local_quote_locator:${evidenceId}`);
  validateSpan({ evidenceId, startOffset, endOffset, expectedSurface: quoteText, structuralLocator, label: "quote", context });

  const speakerSurfaceText = row.speakerSurfaceText === null
    ? null
    : requiredString(row.speakerSurfaceText, `invalid_local_quote_speaker_surface:${evidenceId}`);
  const speakerStartOffset = row.speakerStartOffset === null
    ? null
    : nonNegativeInteger(row.speakerStartOffset, `invalid_local_quote_speaker_span:${evidenceId}`);
  const speakerEndOffset = row.speakerEndOffset === null
    ? null
    : nonNegativeInteger(row.speakerEndOffset, `invalid_local_quote_speaker_span:${evidenceId}`);
  const speakerValues = [speakerSurfaceText, speakerStartOffset, speakerEndOffset];
  const nullCount = speakerValues.filter((item) => item === null).length;
  if (nullCount !== 0 && nullCount !== speakerValues.length) {
    throw new LocalLiteraryEvidenceValidationError(`local_quote_partial_speaker_span:${evidenceId}`);
  }
  if (speakerSurfaceText !== null && speakerStartOffset !== null && speakerEndOffset !== null) {
    validateSpan({
      evidenceId: `${evidenceId}:speaker`,
      startOffset: speakerStartOffset,
      endOffset: speakerEndOffset,
      expectedSurface: speakerSurfaceText,
      structuralLocator: null,
      label: "quote_speaker",
      context,
    });
  }
  const speakerProviderClusterId = nullableString(row.speakerProviderClusterId, `invalid_local_quote_speaker_cluster:${evidenceId}`);
  return {
    evidenceId,
    quoteText,
    startOffset,
    endOffset,
    structuralLocator,
    speakerSurfaceText,
    speakerStartOffset,
    speakerEndOffset,
    speakerProviderClusterId,
  };
}

function parseEvent(value: unknown, context: ValidationContext): EventTriggerEvidence {
  const row = record(value, "invalid_local_event_evidence");
  const evidenceId = requiredString(row.evidenceId, "invalid_local_event_evidence_id");
  const surfaceText = requiredString(row.surfaceText, `invalid_local_event_surface:${evidenceId}`);
  const lemma = requiredString(row.lemma, `invalid_local_event_values:${evidenceId}`);
  const startOffset = nonNegativeInteger(row.startOffset, `invalid_local_event_span:${evidenceId}`);
  const endOffset = nonNegativeInteger(row.endOffset, `invalid_local_event_span:${evidenceId}`);
  const structuralLocator = row.structuralLocator === null
    ? null
    : requiredString(row.structuralLocator, `invalid_local_event_locator:${evidenceId}`);
  const sentenceId = nonNegativeInteger(row.sentenceId, `invalid_local_event_sentence_id:${evidenceId}`);
  const tokenId = nonNegativeInteger(row.tokenId, `invalid_local_event_token_id:${evidenceId}`);
  const dependencyRelation = requiredString(row.dependencyRelation, `invalid_local_event_values:${evidenceId}`);
  const syntacticHeadTokenId = nonNegativeInteger(row.syntacticHeadTokenId, `invalid_local_event_head_id:${evidenceId}`);
  validateSpan({ evidenceId, startOffset, endOffset, expectedSurface: surfaceText, structuralLocator, label: "event", context });
  return {
    evidenceId,
    surfaceText,
    lemma,
    startOffset,
    endOffset,
    structuralLocator,
    sentenceId,
    tokenId,
    dependencyRelation,
    syntacticHeadTokenId,
  };
}

function parseSyntaxToken(value: unknown, context: ValidationContext): SyntaxTokenEvidence {
  const row = record(value, "invalid_local_syntax_token_evidence");
  const evidenceId = requiredString(row.evidenceId, "invalid_local_syntax_token_evidence_id");
  const surfaceText = requiredString(row.surfaceText, `invalid_local_syntax_token_surface:${evidenceId}`);
  const lemma = requiredString(row.lemma, `invalid_local_syntax_token_values:${evidenceId}`);
  const startOffset = nonNegativeInteger(row.startOffset, `invalid_local_syntax_token_span:${evidenceId}`);
  const endOffset = nonNegativeInteger(row.endOffset, `invalid_local_syntax_token_span:${evidenceId}`);
  const structuralLocator = row.structuralLocator === null
    ? null
    : requiredString(row.structuralLocator, `invalid_local_syntax_token_locator:${evidenceId}`);
  const paragraphId = nonNegativeInteger(row.paragraphId, `invalid_local_syntax_token_paragraph_id:${evidenceId}`);
  const sentenceId = nonNegativeInteger(row.sentenceId, `invalid_local_syntax_token_sentence_id:${evidenceId}`);
  const tokenIdWithinSentence = nonNegativeInteger(
    row.tokenIdWithinSentence,
    `invalid_local_syntax_token_sentence_token_id:${evidenceId}`,
  );
  const tokenId = nonNegativeInteger(row.tokenId, `invalid_local_syntax_token_id:${evidenceId}`);
  const posTag = requiredString(row.posTag, `invalid_local_syntax_token_values:${evidenceId}`);
  const finePosTag = requiredString(row.finePosTag, `invalid_local_syntax_token_values:${evidenceId}`);
  const dependencyRelation = requiredString(row.dependencyRelation, `invalid_local_syntax_token_values:${evidenceId}`);
  const syntacticHeadTokenId = nonNegativeInteger(
    row.syntacticHeadTokenId,
    `invalid_local_syntax_token_head_id:${evidenceId}`,
  );
  validateSpan({ evidenceId, startOffset, endOffset, expectedSurface: surfaceText, structuralLocator, label: "syntax_token", context });
  return {
    evidenceId,
    surfaceText,
    lemma,
    startOffset,
    endOffset,
    structuralLocator,
    paragraphId,
    sentenceId,
    tokenIdWithinSentence,
    tokenId,
    posTag,
    finePosTag,
    dependencyRelation,
    syntacticHeadTokenId,
  };
}

function parseArray(value: unknown, code: string) {
  if (!Array.isArray(value)) throw new LocalLiteraryEvidenceValidationError(code);
  return value;
}

function validateSyntaxGraph(syntaxTokens: SyntaxTokenEvidence[], eventTriggers: EventTriggerEvidence[]) {
  const byTokenId = new Map<number, SyntaxTokenEvidence>();
  const withinSentence = new Set<string>();
  for (const token of syntaxTokens) {
    if (byTokenId.has(token.tokenId)) {
      throw new LocalLiteraryEvidenceValidationError(`duplicate_local_syntax_token_id:${token.tokenId}`);
    }
    byTokenId.set(token.tokenId, token);
    const sentenceKey = `${token.sentenceId}:${token.tokenIdWithinSentence}`;
    if (withinSentence.has(sentenceKey)) {
      throw new LocalLiteraryEvidenceValidationError(`duplicate_local_syntax_sentence_token_id:${sentenceKey}`);
    }
    withinSentence.add(sentenceKey);
  }

  for (const token of syntaxTokens) {
    const head = byTokenId.get(token.syntacticHeadTokenId);
    if (!head) {
      throw new LocalLiteraryEvidenceValidationError(
        `local_syntax_token_missing_head:${token.evidenceId}:${token.syntacticHeadTokenId}`,
      );
    }
    if (head.sentenceId !== token.sentenceId) {
      throw new LocalLiteraryEvidenceValidationError(
        `local_syntax_token_cross_sentence_head:${token.evidenceId}:${token.syntacticHeadTokenId}`,
      );
    }
  }

  for (const event of eventTriggers) {
    const token = byTokenId.get(event.tokenId);
    if (!token) {
      throw new LocalLiteraryEvidenceValidationError(`local_event_missing_syntax_token:${event.evidenceId}`);
    }
    if (
      token.surfaceText !== event.surfaceText ||
      token.lemma !== event.lemma ||
      token.startOffset !== event.startOffset ||
      token.endOffset !== event.endOffset ||
      token.sentenceId !== event.sentenceId ||
      token.dependencyRelation !== event.dependencyRelation ||
      token.syntacticHeadTokenId !== event.syntacticHeadTokenId
    ) {
      throw new LocalLiteraryEvidenceValidationError(`local_event_syntax_token_mismatch:${event.evidenceId}`);
    }
  }
}

export function validateLocalLiteraryEvidenceBundle(input: {
  evidence: unknown;
  source: LocalLiteraryAnalysisInput;
  expectedProvider?: IdentityProviderDescriptor;
}): LocalLiteraryEvidenceBundle {
  requireFingerprint(input.source.normalizedInputFingerprint, "invalid_local_source_fingerprint");
  const context: ValidationContext = { source: input.source, index: buildSourceIndex(input.source.normalizedText) };
  const row = record(input.evidence, "invalid_local_evidence_bundle");
  const provider = validateProviderDescriptor(row.provider);
  if (input.expectedProvider) {
    const expectedProvider = validateProviderDescriptor(input.expectedProvider);
    if (!sameProviderDescriptor(provider, expectedProvider)) {
      throw new LocalLiteraryEvidenceValidationError("local_provider_descriptor_mismatch");
    }
  }
  const normalizedInputFingerprint = requireFingerprint(
    row.normalizedInputFingerprint,
    "invalid_local_evidence_input_fingerprint",
  );
  if (normalizedInputFingerprint !== input.source.normalizedInputFingerprint) {
    throw new LocalLiteraryEvidenceValidationError("local_evidence_input_fingerprint_mismatch");
  }

  const identityRow = record(row.identityEvidence, "invalid_local_identity_evidence_bundle");
  const identityProvider = validateProviderDescriptor(identityRow.provider);
  if (!sameProviderDescriptor(identityProvider, provider)) {
    throw new LocalLiteraryEvidenceValidationError("local_identity_provider_descriptor_mismatch");
  }
  const identityFingerprint = requireFingerprint(
    identityRow.normalizedInputFingerprint,
    "invalid_local_identity_input_fingerprint",
  );
  if (identityFingerprint !== input.source.normalizedInputFingerprint) {
    throw new LocalLiteraryEvidenceValidationError("local_identity_input_fingerprint_mismatch");
  }

  const identityMentions = parseArray(identityRow.mentions, "invalid_local_identity_mentions")
    .map((value) => parseIdentityMention(value, context));
  const entities = parseArray(row.entities, "invalid_local_entities")
    .map((value) => parseEntity(value, context));
  const quotes = parseArray(row.quotes, "invalid_local_quotes")
    .map((value) => parseQuote(value, context));
  const eventTriggers = parseArray(row.eventTriggers, "invalid_local_event_triggers")
    .map((value) => parseEvent(value, context));
  const syntaxTokens = row.syntaxTokens === undefined
    ? undefined
    : parseArray(row.syntaxTokens, "invalid_local_syntax_tokens").map((value) => parseSyntaxToken(value, context));

  uniqueEvidenceIds(identityMentions, "identity");
  uniqueEvidenceIds(entities, "entity");
  uniqueEvidenceIds(quotes, "quote");
  uniqueEvidenceIds(eventTriggers, "event");
  if (syntaxTokens) {
    uniqueEvidenceIds(syntaxTokens, "syntax_token");
    validateSyntaxGraph(syntaxTokens, eventTriggers);
  }

  const identityEvidence: NormalizedIdentityEvidence = {
    provider: identityProvider,
    normalizedInputFingerprint: identityFingerprint,
    mentions: identityMentions,
  };
  return {
    provider,
    normalizedInputFingerprint,
    identityEvidence,
    entities,
    quotes,
    eventTriggers,
    ...(syntaxTokens ? { syntaxTokens } : {}),
  };
}
