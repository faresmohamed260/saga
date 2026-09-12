import { canonicalJson, sha256Hex } from "../ingestion/hash.js";

export type EventParticipantRole = "actor" | "patient" | "other";
export type EventParticipantStatus = "known" | "unknown";

export type EventProviderDescriptor = {
  name: string;
  model: string | null;
  revision: string;
};

export type EventParticipantReference = {
  characterKey: string;
  role: EventParticipantRole;
};

export type EventReferenceItem = {
  eventId: string;
  sectionKey: string;
  startOffset: number;
  endOffset: number;
  participantStatus: EventParticipantStatus;
  participants: EventParticipantReference[];
};

export type EventReference = {
  schemaVersion: "saga-event-reference-v1";
  bookId: string;
  sourceSha256: string;
  normalizedInputFingerprint: string;
  annotationProtocolVersion: string;
  events: EventReferenceItem[];
};

export type EventParticipantPrediction = EventParticipantReference & {
  evidenceId: string | null;
};

export type EventPrediction = {
  eventId: string;
  sectionKey: string;
  startOffset: number;
  endOffset: number;
  participants: EventParticipantPrediction[];
  decisionReason: string;
};

export type EventProviderResult = {
  schemaVersion: "saga-event-prediction-v1";
  provider: EventProviderDescriptor;
  normalizedInputFingerprint: string;
  events: EventPrediction[];
  outputFingerprint: string;
};

export type EventScore = {
  truePositive: number;
  falsePositive: number;
  falseNegative: number;
  precision: number;
  recall: number;
  f1: number;
};

export type EventEvaluationReport = {
  schemaVersion: "saga-event-evaluation-v1";
  bookId: string;
  provider: EventProviderDescriptor;
  normalizedInputFingerprint: string;
  triggerDetection: EventScore;
  participantGrounding: EventScore;
  goldEventCount: number;
  predictedEventCount: number;
  duplicatePredictionCount: number;
  duplicatePredictionRate: number;
  unsupportedPredictionCount: number;
  unsupportedPredictionRate: number;
  knownParticipantEventCount: number;
  matchedKnownParticipantEventCount: number;
  missedKnownParticipantEventCount: number;
  unknownParticipantEventMatchedCount: number;
  unscoredParticipantAssignmentCount: number;
  outputFingerprint: string;
};

function score(tp: number, fp: number, fn: number): EventScore {
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

function ratio(numerator: number, denominator: number) {
  return denominator === 0 ? 0 : numerator / denominator;
}

function validateFingerprint(value: string, errorCode: string) {
  if (!/^[0-9a-f]{64}$/u.test(value)) throw new Error(errorCode);
}

function validateSpan(value: { eventId: string; sectionKey: string; startOffset: number; endOffset: number }) {
  if (!value.eventId.trim()) throw new Error("invalid_event_id");
  if (!value.sectionKey.trim()) throw new Error(`invalid_event_section:${value.eventId}`);
  if (!Number.isSafeInteger(value.startOffset) || value.startOffset < 0) {
    throw new Error(`invalid_event_start_offset:${value.eventId}`);
  }
  if (!Number.isSafeInteger(value.endOffset) || value.endOffset <= value.startOffset) {
    throw new Error(`invalid_event_end_offset:${value.eventId}`);
  }
}

function spanKey(value: { sectionKey: string; startOffset: number; endOffset: number }) {
  return `${value.sectionKey}:${value.startOffset}:${value.endOffset}`;
}

function participantKey(value: EventParticipantReference) {
  return `${value.role}:${value.characterKey}`;
}

function validateParticipants(eventId: string, participants: EventParticipantReference[]) {
  const seen = new Set<string>();
  for (const participant of participants) {
    if (!participant.characterKey.trim()) throw new Error(`invalid_event_participant:${eventId}`);
    const key = participantKey(participant);
    if (seen.has(key)) throw new Error(`duplicate_event_participant:${eventId}:${key}`);
    seen.add(key);
  }
}

export function validateEventReference(reference: EventReference) {
  if (reference.schemaVersion !== "saga-event-reference-v1") throw new Error("unsupported_event_reference");
  if (!reference.bookId.trim() || !reference.annotationProtocolVersion.trim()) {
    throw new Error("invalid_event_reference_metadata");
  }
  validateFingerprint(reference.sourceSha256, "invalid_event_source_sha256");
  validateFingerprint(reference.normalizedInputFingerprint, "invalid_event_input_fingerprint");
  if (reference.events.length === 0) throw new Error("empty_event_reference");

  const ids = new Set<string>();
  const spans = new Set<string>();
  for (const event of reference.events) {
    validateSpan(event);
    if (ids.has(event.eventId)) throw new Error(`duplicate_event_reference_id:${event.eventId}`);
    ids.add(event.eventId);
    const key = spanKey(event);
    if (spans.has(key)) throw new Error(`duplicate_event_reference_span:${key}`);
    spans.add(key);
    validateParticipants(event.eventId, event.participants);
    if (event.participantStatus === "unknown" && event.participants.length > 0) {
      throw new Error(`unknown_event_participants_must_be_empty:${event.eventId}`);
    }
  }
}

export function eventPredictionFingerprint(input: {
  provider: EventProviderDescriptor;
  normalizedInputFingerprint: string;
  events: EventPrediction[];
}) {
  return sha256Hex(canonicalJson(input));
}

export function validateEventProviderResult(result: EventProviderResult) {
  if (result.schemaVersion !== "saga-event-prediction-v1") throw new Error("unsupported_event_prediction");
  if (!result.provider.name.trim() || !result.provider.revision.trim()) throw new Error("invalid_event_provider");
  validateFingerprint(result.normalizedInputFingerprint, "invalid_event_prediction_fingerprint");
  validateFingerprint(result.outputFingerprint, "invalid_event_output_fingerprint");

  const ids = new Set<string>();
  for (const event of result.events) {
    validateSpan(event);
    if (!event.decisionReason.trim()) throw new Error(`invalid_event_decision_reason:${event.eventId}`);
    if (ids.has(event.eventId)) throw new Error(`duplicate_event_prediction_id:${event.eventId}`);
    ids.add(event.eventId);
    validateParticipants(event.eventId, event.participants);
  }

  const expected = eventPredictionFingerprint({
    provider: result.provider,
    normalizedInputFingerprint: result.normalizedInputFingerprint,
    events: result.events,
  });
  if (expected !== result.outputFingerprint) throw new Error("event_prediction_output_fingerprint_mismatch");
}

export function evaluateEvents(input: {
  reference: EventReference;
  prediction: EventProviderResult;
}): EventEvaluationReport {
  validateEventReference(input.reference);
  validateEventProviderResult(input.prediction);
  if (input.reference.normalizedInputFingerprint !== input.prediction.normalizedInputFingerprint) {
    throw new Error("event_input_fingerprint_mismatch");
  }

  const goldBySpan = new Map(input.reference.events.map((event) => [spanKey(event), event]));
  const predictionsBySpan = new Map<string, EventPrediction[]>();
  for (const event of input.prediction.events) {
    const key = spanKey(event);
    const current = predictionsBySpan.get(key) ?? [];
    current.push(event);
    predictionsBySpan.set(key, current);
  }
  for (const group of predictionsBySpan.values()) group.sort((left, right) => left.eventId.localeCompare(right.eventId));

  let matchedSpanCount = 0;
  let duplicatePredictionCount = 0;
  let unsupportedPredictionCount = 0;
  let participantTp = 0;
  let participantFp = 0;
  let participantFn = 0;
  let knownParticipantEventCount = 0;
  let matchedKnownParticipantEventCount = 0;
  let missedKnownParticipantEventCount = 0;
  let unknownParticipantEventMatchedCount = 0;
  let unscoredParticipantAssignmentCount = 0;

  for (const group of predictionsBySpan.values()) {
    if (group.length > 1) duplicatePredictionCount += group.length - 1;
  }

  for (const [key, group] of predictionsBySpan) {
    const gold = goldBySpan.get(key);
    if (!gold) {
      unsupportedPredictionCount += group.length;
      continue;
    }
    matchedSpanCount += 1;
    const representative = group[0]!;
    if (gold.participantStatus === "unknown") {
      unknownParticipantEventMatchedCount += 1;
      unscoredParticipantAssignmentCount += representative.participants.length;
      continue;
    }

    matchedKnownParticipantEventCount += 1;
    const goldParticipants = new Set(gold.participants.map(participantKey));
    const predictedParticipants = new Set(representative.participants.map(participantKey));
    for (const keyValue of predictedParticipants) {
      if (goldParticipants.has(keyValue)) participantTp += 1;
      else participantFp += 1;
    }
    for (const keyValue of goldParticipants) {
      if (!predictedParticipants.has(keyValue)) participantFn += 1;
    }
  }

  for (const gold of input.reference.events) {
    if (gold.participantStatus !== "known") continue;
    knownParticipantEventCount += 1;
    if (predictionsBySpan.has(spanKey(gold))) continue;
    missedKnownParticipantEventCount += 1;
    participantFn += gold.participants.length;
  }

  const triggerDetection = score(
    matchedSpanCount,
    input.prediction.events.length - matchedSpanCount,
    input.reference.events.length - matchedSpanCount,
  );
  const participantGrounding = score(participantTp, participantFp, participantFn);
  const predictedEventCount = input.prediction.events.length;
  const semantic = {
    bookId: input.reference.bookId,
    provider: input.prediction.provider,
    normalizedInputFingerprint: input.reference.normalizedInputFingerprint,
    triggerDetection,
    participantGrounding,
    goldEventCount: input.reference.events.length,
    predictedEventCount,
    duplicatePredictionCount,
    duplicatePredictionRate: ratio(duplicatePredictionCount, predictedEventCount),
    unsupportedPredictionCount,
    unsupportedPredictionRate: ratio(unsupportedPredictionCount, predictedEventCount),
    knownParticipantEventCount,
    matchedKnownParticipantEventCount,
    missedKnownParticipantEventCount,
    unknownParticipantEventMatchedCount,
    unscoredParticipantAssignmentCount,
  };

  return {
    schemaVersion: "saga-event-evaluation-v1",
    ...semantic,
    outputFingerprint: sha256Hex(canonicalJson(semantic)),
  };
}
