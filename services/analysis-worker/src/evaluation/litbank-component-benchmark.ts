import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import type { NormalizedSection } from "../ingestion/types.js";
import type { CharacterIdentityResult, ResolvedIdentityMention } from "../identity/types.js";
import { BOOKNLP_SMALL_PROVIDER } from "../local-analysis/booknlp-provider.js";
import type { LocalLiteraryEvidenceBundle } from "../local-analysis/types.js";
import { predictDeterministicDialogue } from "./dialogue-deterministic-baseline.js";
import {
  dialoguePredictionFingerprint,
  evaluateDialogue,
  validateDialogueProviderResult,
  type DialogueEvaluationReport,
  type DialogueProviderResult,
  type DialogueReference,
} from "./dialogue-evaluation.js";
import { predictDeterministicEventCandidates } from "./event-deterministic-baseline.js";
import {
  eventPredictionFingerprint,
  evaluateEvents,
  validateEventProviderResult,
  type EventEvaluationReport,
  type EventProviderResult,
  type EventReference,
} from "./event-evaluation.js";
import { convertLitBankTsvDocument, LITBANK_ORACLE_PROVIDER } from "./litbank-tsv.js";
import type { GoldIdentityDocument } from "./types.js";

export const LITBANK_COMPONENT_ANNOTATION_VERSION = "dbamman-litbank-component-v1";
export const LITBANK_COMPONENT_SECTION_PREFIX = "litbank";

function normalizeNewlines(value: string) {
  return value.replace(/\r\n?/gu, "\n");
}

function collapseWhitespace(value: string) {
  return value.replace(/\s+/gu, " ").trim();
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

type TokenSpan = { text: string; startCodeUnit: number; endCodeUnit: number };

function tokensForLine(line: string): TokenSpan[] {
  return [...line.matchAll(/\S+/gu)].map((match) => ({
    text: match[0],
    startCodeUnit: match.index,
    endCodeUnit: match.index + match[0].length,
  }));
}

function locateTokenRange(input: {
  text: string;
  startLine: number;
  startToken: number;
  endLine: number;
  endToken: number;
  label: string;
}) {
  const text = normalizeNewlines(input.text);
  const lines = text.split("\n");
  const starts = lineStarts(text);
  const boundaries = codePointBoundaryMap(text);
  const startLineText = lines[input.startLine];
  const endLineText = lines[input.endLine];
  const startLineCodeUnit = starts[input.startLine];
  const endLineCodeUnit = starts[input.endLine];
  if (
    startLineText === undefined ||
    endLineText === undefined ||
    startLineCodeUnit === undefined ||
    endLineCodeUnit === undefined
  ) throw new Error(`litbank_component_line_out_of_range:${input.label}`);

  const start = tokensForLine(startLineText)[input.startToken];
  const end = tokensForLine(endLineText)[input.endToken];
  if (!start || !end) throw new Error(`litbank_component_token_out_of_range:${input.label}`);
  const startCodeUnit = startLineCodeUnit + start.startCodeUnit;
  const endCodeUnit = endLineCodeUnit + end.endCodeUnit;
  const startOffset = boundaries.get(startCodeUnit);
  const endOffset = boundaries.get(endCodeUnit);
  if (startOffset === undefined || endOffset === undefined) {
    throw new Error(`litbank_component_non_boundary_offset:${input.label}`);
  }
  return { startOffset, endOffset, surfaceText: text.slice(startCodeUnit, endCodeUnit) };
}

function parseIndex(value: string | undefined, label: string) {
  if (!value || !/^\d+$/u.test(value)) throw new Error(`litbank_component_invalid_index:${label}`);
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed < 0) throw new Error(`litbank_component_invalid_index:${label}`);
  return parsed;
}

export function convertLitBankQuotationReference(input: {
  documentId: string;
  text: string;
  annotation: string;
}): DialogueReference {
  const text = normalizeNewlines(input.text);
  const quoteRows = new Map<string, {
    quoteId: string;
    startLine: number;
    startToken: number;
    endLine: number;
    endToken: number;
    annotatedSurface: string;
  }>();
  const speakers = new Map<string, string>();

  for (const rawLine of normalizeNewlines(input.annotation).split("\n")) {
    if (!rawLine.trim()) continue;
    const fields = rawLine.split("\t");
    if (fields[0] === "QUOTE") {
      if (fields.length < 7 || !fields[1] || fields[6] === undefined) throw new Error(`invalid_litbank_quote:${rawLine}`);
      const quoteId = fields[1];
      if (quoteRows.has(quoteId)) throw new Error(`duplicate_litbank_quote:${quoteId}`);
      quoteRows.set(quoteId, {
        quoteId,
        startLine: parseIndex(fields[2], `${quoteId}:start_line`),
        startToken: parseIndex(fields[3], `${quoteId}:start_token`),
        endLine: parseIndex(fields[4], `${quoteId}:end_line`),
        endToken: parseIndex(fields[5], `${quoteId}:end_token`),
        annotatedSurface: fields.slice(6).join("\t"),
      });
    } else if (fields[0] === "ATTRIB") {
      const quoteId = fields[1];
      const speakerId = fields[2];
      if (!quoteId || !speakerId) throw new Error(`invalid_litbank_quote_attribution:${rawLine}`);
      if (speakers.has(quoteId)) throw new Error(`duplicate_litbank_quote_attribution:${quoteId}`);
      speakers.set(quoteId, speakerId);
    } else {
      throw new Error(`unsupported_litbank_quote_row:${rawLine}`);
    }
  }
  for (const quoteId of speakers.keys()) {
    if (!quoteRows.has(quoteId)) throw new Error(`litbank_attribution_without_quote:${quoteId}`);
  }

  const sectionKey = `${LITBANK_COMPONENT_SECTION_PREFIX}:${input.documentId}`;
  const quotes = [...quoteRows.values()].map((quote) => {
    const located = locateTokenRange({
      text,
      startLine: quote.startLine,
      startToken: quote.startToken,
      endLine: quote.endLine,
      endToken: quote.endToken,
      label: `quote:${quote.quoteId}`,
    });
    if (collapseWhitespace(located.surfaceText) !== collapseWhitespace(quote.annotatedSurface)) {
      throw new Error(`litbank_quote_surface_mismatch:${quote.quoteId}`);
    }
    const speakerKey = speakers.get(quote.quoteId) ?? null;
    return {
      quoteId: quote.quoteId,
      sectionKey,
      startOffset: located.startOffset,
      endOffset: located.endOffset,
      speakerStatus: speakerKey === null ? "unknown" as const : "known" as const,
      speakerKey,
    };
  }).sort((left, right) =>
    left.startOffset - right.startOffset || left.endOffset - right.endOffset || left.quoteId.localeCompare(right.quoteId),
  );

  return {
    schemaVersion: "saga-dialogue-reference-v1",
    bookId: input.documentId,
    sourceSha256: sha256Hex(text),
    normalizedInputFingerprint: sha256Hex(text),
    annotationProtocolVersion: LITBANK_COMPONENT_ANNOTATION_VERSION,
    quotes,
  };
}

export function convertLitBankEventReference(input: {
  documentId: string;
  text: string;
  eventTsv: string;
}): EventReference {
  const text = normalizeNewlines(input.text);
  const sourceLines = text.split("\n");
  const events: EventReference["events"] = [];
  let sentenceId = 0;
  let tokenId = 0;
  let sawTokenInSentence = false;

  const finishSentence = () => {
    if (!sawTokenInSentence) return;
    const expected = tokensForLine(sourceLines[sentenceId] ?? "").length;
    if (tokenId !== expected) {
      throw new Error(`litbank_event_sentence_token_count_mismatch:${sentenceId}:${tokenId}:${expected}`);
    }
    sentenceId += 1;
    tokenId = 0;
    sawTokenInSentence = false;
  };

  for (const rawLine of normalizeNewlines(input.eventTsv).split("\n")) {
    if (!rawLine.trim()) {
      finishSentence();
      continue;
    }
    const fields = rawLine.split("\t");
    if (fields.length !== 2 || !fields[0] || !fields[1]) throw new Error(`invalid_litbank_event_row:${rawLine}`);
    const sourceToken = tokensForLine(sourceLines[sentenceId] ?? "")[tokenId];
    if (!sourceToken) throw new Error(`litbank_event_token_out_of_range:${sentenceId}:${tokenId}`);
    if (sourceToken.text !== fields[0]) throw new Error(`litbank_event_token_mismatch:${sentenceId}:${tokenId}`);
    sawTokenInSentence = true;
    if (fields[1] !== "O" && fields[1] !== "EVENT") throw new Error(`unsupported_litbank_event_label:${fields[1]}`);
    if (fields[1] === "EVENT") {
      const located = locateTokenRange({
        text,
        startLine: sentenceId,
        startToken: tokenId,
        endLine: sentenceId,
        endToken: tokenId,
        label: `event:${sentenceId}:${tokenId}`,
      });
      events.push({
        eventId: `litbank-event:${sentenceId}:${tokenId}`,
        sectionKey: `${LITBANK_COMPONENT_SECTION_PREFIX}:${input.documentId}`,
        startOffset: located.startOffset,
        endOffset: located.endOffset,
        participantStatus: "unknown",
        participants: [],
      });
    }
    tokenId += 1;
  }
  finishSentence();
  while (sentenceId < sourceLines.length && sourceLines[sentenceId] === "") sentenceId += 1;
  if (sentenceId !== sourceLines.length) throw new Error(`litbank_event_sentence_count_mismatch:${sentenceId}:${sourceLines.length}`);

  return {
    schemaVersion: "saga-event-reference-v1",
    bookId: input.documentId,
    sourceSha256: sha256Hex(text),
    normalizedInputFingerprint: sha256Hex(text),
    annotationProtocolVersion: LITBANK_COMPONENT_ANNOTATION_VERSION,
    events,
  };
}

function spanKey(startOffset: number, endOffset: number) {
  return `${startOffset}:${endOffset}`;
}

function goldSpeakerBySpan(gold: GoldIdentityDocument) {
  const clusters = new Map<string, Set<string>>();
  for (const mention of gold.mentions) {
    if (!mention.goldCharacterId || mention.entityType !== "person") continue;
    const key = spanKey(mention.startOffset, mention.endOffset);
    const current = clusters.get(key) ?? new Set<string>();
    current.add(mention.goldCharacterId);
    clusters.set(key, current);
  }
  return new Map([...clusters.entries()].map(([key, values]) => [key, values.size === 1 ? [...values][0]! : null]));
}

export function bookNlpDialoguePrediction(input: {
  documentId: string;
  evidence: LocalLiteraryEvidenceBundle;
  goldIdentity: GoldIdentityDocument;
}): { prediction: DialogueProviderResult; attributedMentionCount: number; goldMappedMentionCount: number } {
  const mapping = goldSpeakerBySpan(input.goldIdentity);
  let attributedMentionCount = 0;
  let goldMappedMentionCount = 0;
  const quotes = input.evidence.quotes.map((quote) => {
    let speakerKey: string | null = null;
    if (quote.speakerStartOffset !== null && quote.speakerEndOffset !== null) {
      attributedMentionCount += 1;
      speakerKey = mapping.get(spanKey(quote.speakerStartOffset, quote.speakerEndOffset)) ?? null;
      if (speakerKey !== null) goldMappedMentionCount += 1;
    }
    return {
      quoteId: quote.evidenceId,
      sectionKey: `${LITBANK_COMPONENT_SECTION_PREFIX}:${input.documentId}`,
      startOffset: quote.startOffset,
      endOffset: quote.endOffset,
      speakerKey,
      decisionReason: speakerKey === null ? "booknlp_speaker_unmapped_to_gold" : "booknlp_speaker_mention_gold_mapped",
    };
  }).sort((left, right) => left.startOffset - right.startOffset || left.endOffset - right.endOffset || left.quoteId.localeCompare(right.quoteId));

  const provider = BOOKNLP_SMALL_PROVIDER;
  return {
    prediction: {
      schemaVersion: "saga-dialogue-prediction-v1",
      provider,
      normalizedInputFingerprint: input.evidence.normalizedInputFingerprint,
      quotes,
      outputFingerprint: dialoguePredictionFingerprint({ provider, normalizedInputFingerprint: input.evidence.normalizedInputFingerprint, quotes }),
    },
    attributedMentionCount,
    goldMappedMentionCount,
  };
}

export function bookNlpEventPrediction(input: {
  documentId: string;
  evidence: LocalLiteraryEvidenceBundle;
}): EventProviderResult {
  const events = input.evidence.eventTriggers.map((event) => ({
    eventId: event.evidenceId,
    sectionKey: `${LITBANK_COMPONENT_SECTION_PREFIX}:${input.documentId}`,
    startOffset: event.startOffset,
    endOffset: event.endOffset,
    participants: [],
    decisionReason: "booknlp_event_trigger",
  })).sort((left, right) => left.startOffset - right.startOffset || left.endOffset - right.endOffset || left.eventId.localeCompare(right.eventId));
  const provider = BOOKNLP_SMALL_PROVIDER;
  return {
    schemaVersion: "saga-event-prediction-v1",
    provider,
    normalizedInputFingerprint: input.evidence.normalizedInputFingerprint,
    events,
    outputFingerprint: eventPredictionFingerprint({ provider, normalizedInputFingerprint: input.evidence.normalizedInputFingerprint, events }),
  };
}

export function litBankGoldIdentityResult(gold: GoldIdentityDocument): CharacterIdentityResult {
  const inputFingerprint = sha256Hex(gold.text);
  const personMentions = gold.mentions.filter((mention) => mention.entityType === "person");
  const byCharacter = new Map<string, typeof personMentions>();
  for (const mention of personMentions) {
    if (!mention.goldCharacterId) continue;
    const current = byCharacter.get(mention.goldCharacterId) ?? [];
    current.push(mention);
    byCharacter.set(mention.goldCharacterId, current);
  }
  const characters = [...byCharacter.entries()].sort(([left], [right]) => left.localeCompare(right)).map(([characterKey, mentions]) => {
    const proper = mentions.find((mention) => mention.mentionKind === "proper_name");
    return {
      characterKey,
      canonicalName: proper?.surfaceText ?? mentions[0]!.surfaceText,
      admissionTier: "canonical_seed" as const,
      evidenceCount: mentions.length,
      aliases: [],
    };
  });
  const mentions: ResolvedIdentityMention[] = personMentions.map((mention) => ({
    evidenceId: mention.mentionId,
    characterKey: mention.goldCharacterId,
    surfaceText: mention.surfaceText,
    startOffset: mention.startOffset,
    endOffset: mention.endOffset,
    structuralLocator: `${LITBANK_COMPONENT_SECTION_PREFIX}:${gold.documentId}`,
    mentionKind: mention.mentionKind,
    resolutionState: mention.goldCharacterId ? "linked" as const : "unresolved" as const,
    evidenceTier: mention.mentionKind === "proper_name" ? "canonical_seed" as const : "attachment" as const,
    decisionReason: "litbank_gold_oracle_identity",
  }));
  const semantic = { characters, mentions };
  return {
    resolverVersion: "litbank-gold-oracle-v1",
    resolverConfigFingerprint: sha256Hex("litbank-gold-oracle-v1"),
    provider: LITBANK_ORACLE_PROVIDER,
    normalizedInputFingerprint: inputFingerprint,
    outputFingerprint: sha256Hex(canonicalJson(semantic)),
    characters,
    mentions,
  };
}

export function litBankDocumentSection(documentId: string, text: string): NormalizedSection {
  const normalizedText = normalizeNewlines(text);
  return {
    stable_key: `${LITBANK_COMPONENT_SECTION_PREFIX}:${documentId}`,
    ordinal: 0,
    section_kind: "document",
    title: null,
    source_locator: `${LITBANK_COMPONENT_SECTION_PREFIX}:${documentId}`,
    start_offset: 0,
    end_offset: Array.from(normalizedText).length,
    normalized_text: normalizedText,
  };
}

function metricScore(tp: number, fp: number, fn: number) {
  const precision = tp + fp === 0 ? (tp + fn === 0 ? 1 : 0) : tp / (tp + fp);
  const recall = tp + fn === 0 ? 1 : tp / (tp + fn);
  return { truePositive: tp, falsePositive: fp, falseNegative: fn, precision, recall, f1: precision + recall === 0 ? 0 : (2 * precision * recall) / (precision + recall) };
}

function ratio(numerator: number, denominator: number) {
  return denominator === 0 ? 0 : numerator / denominator;
}

function evaluateDialogueAllowEmpty(input: { reference: DialogueReference; prediction: DialogueProviderResult }): DialogueEvaluationReport {
  if (input.reference.quotes.length > 0) return evaluateDialogue(input);
  validateDialogueProviderResult(input.prediction);
  if (input.reference.normalizedInputFingerprint !== input.prediction.normalizedInputFingerprint) {
    throw new Error("dialogue_input_fingerprint_mismatch");
  }
  const quoteDetection = metricScore(0, input.prediction.quotes.length, 0);
  const semantic = {
    bookId: input.reference.bookId,
    provider: input.prediction.provider,
    normalizedInputFingerprint: input.reference.normalizedInputFingerprint,
    quoteDetection,
    knownSpeakerGoldCount: 0,
    matchedKnownSpeakerCount: 0,
    knownSpeakerMissedQuoteCount: 0,
    speakerCorrectCount: 0,
    speakerIncorrectCount: 0,
    speakerUnresolvedCount: 0,
    speakerAccuracyOnMatchedQuotes: 0,
    resolvedSpeakerAccuracy: 0,
    speakerUnresolvedRateOnMatchedQuotes: 0,
    crossCharacterContaminationRateOnMatchedQuotes: 0,
    endToEndSpeakerRecall: 0,
    unknownSpeakerMatchedCount: 0,
    ambiguousSpeakerMatchedCount: 0,
    unscoredSpeakerAssignmentCount: 0,
  };
  return { schemaVersion: "saga-dialogue-evaluation-v1", ...semantic, outputFingerprint: sha256Hex(canonicalJson(semantic)) };
}

function evaluateEventsAllowEmpty(input: { reference: EventReference; prediction: EventProviderResult }): EventEvaluationReport {
  if (input.reference.events.length > 0) return evaluateEvents(input);
  validateEventProviderResult(input.prediction);
  if (input.reference.normalizedInputFingerprint !== input.prediction.normalizedInputFingerprint) {
    throw new Error("event_input_fingerprint_mismatch");
  }
  const triggerDetection = metricScore(0, input.prediction.events.length, 0);
  const participantGrounding = metricScore(0, 0, 0);
  const semantic = {
    bookId: input.reference.bookId,
    provider: input.prediction.provider,
    normalizedInputFingerprint: input.reference.normalizedInputFingerprint,
    triggerDetection,
    participantGrounding,
    goldEventCount: 0,
    predictedEventCount: input.prediction.events.length,
    duplicatePredictionCount: 0,
    duplicatePredictionRate: 0,
    unsupportedPredictionCount: input.prediction.events.length,
    unsupportedPredictionRate: input.prediction.events.length === 0 ? 0 : 1,
    knownParticipantEventCount: 0,
    matchedKnownParticipantEventCount: 0,
    missedKnownParticipantEventCount: 0,
    unknownParticipantEventMatchedCount: 0,
    unscoredParticipantAssignmentCount: 0,
  };
  return { schemaVersion: "saga-event-evaluation-v1", ...semantic, outputFingerprint: sha256Hex(canonicalJson(semantic)) };
}

export function aggregateDialogueReports(reports: DialogueEvaluationReport[]) {
  const counts = reports.reduce((total, report) => ({
    quoteTp: total.quoteTp + report.quoteDetection.truePositive,
    quoteFp: total.quoteFp + report.quoteDetection.falsePositive,
    quoteFn: total.quoteFn + report.quoteDetection.falseNegative,
    knownSpeakerGoldCount: total.knownSpeakerGoldCount + report.knownSpeakerGoldCount,
    matchedKnownSpeakerCount: total.matchedKnownSpeakerCount + report.matchedKnownSpeakerCount,
    speakerCorrectCount: total.speakerCorrectCount + report.speakerCorrectCount,
    speakerIncorrectCount: total.speakerIncorrectCount + report.speakerIncorrectCount,
    speakerUnresolvedCount: total.speakerUnresolvedCount + report.speakerUnresolvedCount,
  }), {
    quoteTp: 0, quoteFp: 0, quoteFn: 0, knownSpeakerGoldCount: 0, matchedKnownSpeakerCount: 0,
    speakerCorrectCount: 0, speakerIncorrectCount: 0, speakerUnresolvedCount: 0,
  });
  const resolved = counts.speakerCorrectCount + counts.speakerIncorrectCount;
  return {
    documentCount: reports.length,
    quoteDetection: metricScore(counts.quoteTp, counts.quoteFp, counts.quoteFn),
    knownSpeakerGoldCount: counts.knownSpeakerGoldCount,
    matchedKnownSpeakerCount: counts.matchedKnownSpeakerCount,
    speakerCorrectCount: counts.speakerCorrectCount,
    speakerIncorrectCount: counts.speakerIncorrectCount,
    speakerUnresolvedCount: counts.speakerUnresolvedCount,
    speakerAccuracyOnMatchedQuotes: ratio(counts.speakerCorrectCount, counts.matchedKnownSpeakerCount),
    resolvedSpeakerAccuracy: ratio(counts.speakerCorrectCount, resolved),
    speakerUnresolvedRateOnMatchedQuotes: ratio(counts.speakerUnresolvedCount, counts.matchedKnownSpeakerCount),
    crossCharacterContaminationRateOnMatchedQuotes: ratio(counts.speakerIncorrectCount, counts.matchedKnownSpeakerCount),
    endToEndSpeakerRecall: ratio(counts.speakerCorrectCount, counts.knownSpeakerGoldCount),
  };
}

export function aggregateEventReports(reports: EventEvaluationReport[]) {
  const counts = reports.reduce((total, report) => ({
    triggerTp: total.triggerTp + report.triggerDetection.truePositive,
    triggerFp: total.triggerFp + report.triggerDetection.falsePositive,
    triggerFn: total.triggerFn + report.triggerDetection.falseNegative,
    goldEventCount: total.goldEventCount + report.goldEventCount,
    predictedEventCount: total.predictedEventCount + report.predictedEventCount,
    duplicatePredictionCount: total.duplicatePredictionCount + report.duplicatePredictionCount,
    unsupportedPredictionCount: total.unsupportedPredictionCount + report.unsupportedPredictionCount,
  }), { triggerTp: 0, triggerFp: 0, triggerFn: 0, goldEventCount: 0, predictedEventCount: 0, duplicatePredictionCount: 0, unsupportedPredictionCount: 0 });
  return {
    documentCount: reports.length,
    triggerDetection: metricScore(counts.triggerTp, counts.triggerFp, counts.triggerFn),
    goldEventCount: counts.goldEventCount,
    predictedEventCount: counts.predictedEventCount,
    duplicatePredictionCount: counts.duplicatePredictionCount,
    duplicatePredictionRate: ratio(counts.duplicatePredictionCount, counts.predictedEventCount),
    unsupportedPredictionCount: counts.unsupportedPredictionCount,
    unsupportedPredictionRate: ratio(counts.unsupportedPredictionCount, counts.predictedEventCount),
    participantGroundingScored: false,
  };
}

export function evaluateLitBankComponentDocument(input: {
  documentId: string;
  text: string;
  corefAnnotation: string;
  quotationAnnotation: string;
  eventTsv: string;
  evidence: LocalLiteraryEvidenceBundle;
}) {
  const convertedIdentity = convertLitBankTsvDocument({ documentId: input.documentId, text: input.text, annotation: input.corefAnnotation });
  if (convertedIdentity.gold.text !== normalizeNewlines(input.text)) throw new Error("litbank_component_text_normalization_mismatch");
  const dialogueReference = convertLitBankQuotationReference({ documentId: input.documentId, text: convertedIdentity.gold.text, annotation: input.quotationAnnotation });
  const eventReference = convertLitBankEventReference({ documentId: input.documentId, text: convertedIdentity.gold.text, eventTsv: input.eventTsv });
  if (input.evidence.normalizedInputFingerprint !== sha256Hex(convertedIdentity.gold.text)) {
    throw new Error("litbank_component_provider_input_fingerprint_mismatch");
  }

  const bookNlpDialogue = bookNlpDialoguePrediction({ documentId: input.documentId, evidence: input.evidence, goldIdentity: convertedIdentity.gold });
  const bookNlpEvent = bookNlpEventPrediction({ documentId: input.documentId, evidence: input.evidence });
  const goldIdentity = litBankGoldIdentityResult(convertedIdentity.gold);
  const section = litBankDocumentSection(input.documentId, convertedIdentity.gold.text);
  const deterministicDialogue = predictDeterministicDialogue({ sections: [section], normalizedInputFingerprint: input.evidence.normalizedInputFingerprint, identity: goldIdentity });
  const deterministicEvent = predictDeterministicEventCandidates({ sections: [section], normalizedInputFingerprint: input.evidence.normalizedInputFingerprint, identity: goldIdentity });

  return {
    dialogue: {
      bookNlp: evaluateDialogueAllowEmpty({ reference: dialogueReference, prediction: bookNlpDialogue.prediction }),
      deterministicOracleIdentity: evaluateDialogueAllowEmpty({ reference: dialogueReference, prediction: deterministicDialogue }),
      bookNlpSpeakerMapping: { attributedMentionCount: bookNlpDialogue.attributedMentionCount, goldMappedMentionCount: bookNlpDialogue.goldMappedMentionCount },
    },
    events: {
      bookNlp: evaluateEventsAllowEmpty({ reference: eventReference, prediction: bookNlpEvent }),
      deterministicLexicalOracleIdentity: evaluateEventsAllowEmpty({ reference: eventReference, prediction: deterministicEvent }),
    },
  };
}
