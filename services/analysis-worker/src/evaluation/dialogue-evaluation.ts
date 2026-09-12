import { canonicalJson, sha256Hex } from "../ingestion/hash.js";

export type DialogueSpeakerStatus = "known" | "unknown" | "ambiguous";

export type DialogueProviderDescriptor = {
  name: string;
  model: string | null;
  revision: string;
};

export type DialogueQuoteAnnotation = {
  quoteId: string;
  sectionKey: string;
  startOffset: number;
  endOffset: number;
  speakerStatus: DialogueSpeakerStatus;
  speakerKey: string | null;
};

export type DialogueReference = {
  schemaVersion: "saga-dialogue-reference-v1";
  bookId: string;
  sourceSha256: string;
  normalizedInputFingerprint: string;
  annotationProtocolVersion: string;
  quotes: DialogueQuoteAnnotation[];
};

export type DialogueQuotePrediction = {
  quoteId: string;
  sectionKey: string;
  startOffset: number;
  endOffset: number;
  speakerKey: string | null;
  decisionReason: string;
};

export type DialogueProviderResult = {
  schemaVersion: "saga-dialogue-prediction-v1";
  provider: DialogueProviderDescriptor;
  normalizedInputFingerprint: string;
  quotes: DialogueQuotePrediction[];
  outputFingerprint: string;
};

export type DialogueDetectionScore = {
  truePositive: number;
  falsePositive: number;
  falseNegative: number;
  precision: number;
  recall: number;
  f1: number;
};

export type DialogueEvaluationReport = {
  schemaVersion: "saga-dialogue-evaluation-v1";
  bookId: string;
  provider: DialogueProviderDescriptor;
  normalizedInputFingerprint: string;
  quoteDetection: DialogueDetectionScore;
  knownSpeakerGoldCount: number;
  matchedKnownSpeakerCount: number;
  knownSpeakerMissedQuoteCount: number;
  speakerCorrectCount: number;
  speakerIncorrectCount: number;
  speakerUnresolvedCount: number;
  speakerAccuracyOnMatchedQuotes: number;
  resolvedSpeakerAccuracy: number;
  speakerUnresolvedRateOnMatchedQuotes: number;
  crossCharacterContaminationRateOnMatchedQuotes: number;
  endToEndSpeakerRecall: number;
  unknownSpeakerMatchedCount: number;
  ambiguousSpeakerMatchedCount: number;
  unscoredSpeakerAssignmentCount: number;
  outputFingerprint: string;
};

function score(tp: number, fp: number, fn: number): DialogueDetectionScore {
  const precision = tp + fp === 0 ? (tp + fn === 0 ? 1 : 0) : tp / (tp + fp);
  const recall = tp + fn === 0 ? 1 : tp / (tp + fn);
  return {
    truePositive: tp,
    falsePositive: fp,
    falseNegative: fn,
    precision,
    recall,
    f1: precision + recall === 0 ? 0 : (2 * precision * recall) / (precision + recall),
  };
}

function validateFingerprint(value: string, errorCode: string) {
  if (!/^[0-9a-f]{64}$/u.test(value)) throw new Error(errorCode);
}

function validateQuoteSpan(input: {
  quoteId: string;
  sectionKey: string;
  startOffset: number;
  endOffset: number;
}) {
  if (!input.quoteId.trim()) throw new Error("invalid_dialogue_quote_id");
  if (!input.sectionKey.trim()) throw new Error(`invalid_dialogue_section:${input.quoteId}`);
  if (!Number.isSafeInteger(input.startOffset) || input.startOffset < 0) {
    throw new Error(`invalid_dialogue_start_offset:${input.quoteId}`);
  }
  if (!Number.isSafeInteger(input.endOffset) || input.endOffset <= input.startOffset) {
    throw new Error(`invalid_dialogue_end_offset:${input.quoteId}`);
  }
}

function spanKey(value: { sectionKey: string; startOffset: number; endOffset: number }) {
  return `${value.sectionKey}:${value.startOffset}:${value.endOffset}`;
}

export function validateDialogueReference(reference: DialogueReference) {
  if (reference.schemaVersion !== "saga-dialogue-reference-v1") throw new Error("unsupported_dialogue_reference");
  if (!reference.bookId.trim() || !reference.annotationProtocolVersion.trim()) {
    throw new Error("invalid_dialogue_reference_metadata");
  }
  validateFingerprint(reference.sourceSha256, "invalid_dialogue_source_sha256");
  validateFingerprint(reference.normalizedInputFingerprint, "invalid_dialogue_input_fingerprint");
  if (reference.quotes.length === 0) throw new Error("empty_dialogue_reference");

  const ids = new Set<string>();
  const spans = new Set<string>();
  for (const quote of reference.quotes) {
    validateQuoteSpan(quote);
    if (ids.has(quote.quoteId)) throw new Error(`duplicate_dialogue_reference_id:${quote.quoteId}`);
    ids.add(quote.quoteId);
    const key = spanKey(quote);
    if (spans.has(key)) throw new Error(`duplicate_dialogue_reference_span:${key}`);
    spans.add(key);
    if (quote.speakerStatus === "known") {
      if (!quote.speakerKey?.trim()) throw new Error(`known_dialogue_speaker_missing:${quote.quoteId}`);
    } else if (quote.speakerKey !== null) {
      throw new Error(`unscored_dialogue_speaker_must_be_null:${quote.quoteId}`);
    }
  }
}

export function dialoguePredictionFingerprint(input: {
  provider: DialogueProviderDescriptor;
  normalizedInputFingerprint: string;
  quotes: DialogueQuotePrediction[];
}) {
  return sha256Hex(canonicalJson(input));
}

export function validateDialogueProviderResult(result: DialogueProviderResult) {
  if (result.schemaVersion !== "saga-dialogue-prediction-v1") throw new Error("unsupported_dialogue_prediction");
  if (!result.provider.name.trim() || !result.provider.revision.trim()) throw new Error("invalid_dialogue_provider");
  validateFingerprint(result.normalizedInputFingerprint, "invalid_dialogue_prediction_fingerprint");
  validateFingerprint(result.outputFingerprint, "invalid_dialogue_output_fingerprint");

  const ids = new Set<string>();
  const spans = new Set<string>();
  for (const quote of result.quotes) {
    validateQuoteSpan(quote);
    if (!quote.decisionReason.trim()) throw new Error(`invalid_dialogue_decision_reason:${quote.quoteId}`);
    if (quote.speakerKey !== null && !quote.speakerKey.trim()) {
      throw new Error(`invalid_dialogue_speaker_key:${quote.quoteId}`);
    }
    if (ids.has(quote.quoteId)) throw new Error(`duplicate_dialogue_prediction_id:${quote.quoteId}`);
    ids.add(quote.quoteId);
    const key = spanKey(quote);
    if (spans.has(key)) throw new Error(`duplicate_dialogue_prediction_span:${key}`);
    spans.add(key);
  }

  const expected = dialoguePredictionFingerprint({
    provider: result.provider,
    normalizedInputFingerprint: result.normalizedInputFingerprint,
    quotes: result.quotes,
  });
  if (expected !== result.outputFingerprint) throw new Error("dialogue_prediction_output_fingerprint_mismatch");
}

function ratio(numerator: number, denominator: number) {
  return denominator === 0 ? 0 : numerator / denominator;
}

export function evaluateDialogue(input: {
  reference: DialogueReference;
  prediction: DialogueProviderResult;
}): DialogueEvaluationReport {
  validateDialogueReference(input.reference);
  validateDialogueProviderResult(input.prediction);
  if (input.reference.normalizedInputFingerprint !== input.prediction.normalizedInputFingerprint) {
    throw new Error("dialogue_input_fingerprint_mismatch");
  }

  const goldBySpan = new Map(input.reference.quotes.map((quote) => [spanKey(quote), quote]));
  const predictionBySpan = new Map(input.prediction.quotes.map((quote) => [spanKey(quote), quote]));
  const matchedKeys = [...predictionBySpan.keys()].filter((key) => goldBySpan.has(key));
  const quoteDetection = score(
    matchedKeys.length,
    input.prediction.quotes.length - matchedKeys.length,
    input.reference.quotes.length - matchedKeys.length,
  );

  const knownSpeakerGoldCount = input.reference.quotes.filter((quote) => quote.speakerStatus === "known").length;
  let matchedKnownSpeakerCount = 0;
  let speakerCorrectCount = 0;
  let speakerIncorrectCount = 0;
  let speakerUnresolvedCount = 0;
  let unknownSpeakerMatchedCount = 0;
  let ambiguousSpeakerMatchedCount = 0;
  let unscoredSpeakerAssignmentCount = 0;

  for (const key of matchedKeys) {
    const gold = goldBySpan.get(key)!;
    const predicted = predictionBySpan.get(key)!;
    if (gold.speakerStatus === "known") {
      matchedKnownSpeakerCount += 1;
      if (predicted.speakerKey === null) speakerUnresolvedCount += 1;
      else if (predicted.speakerKey === gold.speakerKey) speakerCorrectCount += 1;
      else speakerIncorrectCount += 1;
    } else {
      if (gold.speakerStatus === "unknown") unknownSpeakerMatchedCount += 1;
      else ambiguousSpeakerMatchedCount += 1;
      if (predicted.speakerKey !== null) unscoredSpeakerAssignmentCount += 1;
    }
  }

  const knownSpeakerMissedQuoteCount = knownSpeakerGoldCount - matchedKnownSpeakerCount;
  const resolvedCount = speakerCorrectCount + speakerIncorrectCount;
  const semantic = {
    bookId: input.reference.bookId,
    provider: input.prediction.provider,
    normalizedInputFingerprint: input.reference.normalizedInputFingerprint,
    quoteDetection,
    knownSpeakerGoldCount,
    matchedKnownSpeakerCount,
    knownSpeakerMissedQuoteCount,
    speakerCorrectCount,
    speakerIncorrectCount,
    speakerUnresolvedCount,
    speakerAccuracyOnMatchedQuotes: ratio(speakerCorrectCount, matchedKnownSpeakerCount),
    resolvedSpeakerAccuracy: ratio(speakerCorrectCount, resolvedCount),
    speakerUnresolvedRateOnMatchedQuotes: ratio(speakerUnresolvedCount, matchedKnownSpeakerCount),
    crossCharacterContaminationRateOnMatchedQuotes: ratio(speakerIncorrectCount, matchedKnownSpeakerCount),
    endToEndSpeakerRecall: ratio(speakerCorrectCount, knownSpeakerGoldCount),
    unknownSpeakerMatchedCount,
    ambiguousSpeakerMatchedCount,
    unscoredSpeakerAssignmentCount,
  };

  return {
    schemaVersion: "saga-dialogue-evaluation-v1",
    ...semantic,
    outputFingerprint: sha256Hex(canonicalJson(semantic)),
  };
}
