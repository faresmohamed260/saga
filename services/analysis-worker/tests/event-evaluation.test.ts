import assert from "node:assert/strict";
import test from "node:test";

import {
  eventPredictionFingerprint,
  evaluateEvents,
  validateEventProviderResult,
  validateEventReference,
  type EventPrediction,
  type EventProviderResult,
  type EventReference,
} from "../src/evaluation/event-evaluation.js";

const fingerprint = "a".repeat(64);

function reference(): EventReference {
  return {
    schemaVersion: "saga-event-reference-v1",
    bookId: "book",
    sourceSha256: "b".repeat(64),
    normalizedInputFingerprint: fingerprint,
    annotationProtocolVersion: "event-v1",
    events: [
      {
        eventId: "g1",
        sectionKey: "c1",
        startOffset: 10,
        endOffset: 17,
        participantStatus: "known",
        participants: [
          { characterKey: "char-a", role: "actor" },
          { characterKey: "char-b", role: "patient" },
        ],
      },
      {
        eventId: "g2",
        sectionKey: "c1",
        startOffset: 30,
        endOffset: 37,
        participantStatus: "known",
        participants: [{ characterKey: "char-c", role: "actor" }],
      },
      {
        eventId: "g3",
        sectionKey: "c1",
        startOffset: 50,
        endOffset: 57,
        participantStatus: "unknown",
        participants: [],
      },
    ],
  };
}

function prediction(events: EventPrediction[], inputFingerprint = fingerprint): EventProviderResult {
  const provider = { name: "test", model: null, revision: "r1" };
  return {
    schemaVersion: "saga-event-prediction-v1",
    provider,
    normalizedInputFingerprint: inputFingerprint,
    events,
    outputFingerprint: eventPredictionFingerprint({ provider, normalizedInputFingerprint: inputFingerprint, events }),
  };
}

function event(input: Partial<EventPrediction> & Pick<EventPrediction, "eventId" | "startOffset" | "endOffset">): EventPrediction {
  return {
    sectionKey: "c1",
    participants: [],
    decisionReason: "test",
    ...input,
  };
}

test("event evaluation separates exact trigger quality, duplicate rate, unsupported rate, and participant grounding", () => {
  const result = evaluateEvents({
    reference: reference(),
    prediction: prediction([
      event({
        eventId: "p1",
        startOffset: 10,
        endOffset: 17,
        participants: [
          { characterKey: "char-a", role: "actor", evidenceId: "m1" },
          { characterKey: "char-b", role: "patient", evidenceId: "m2" },
        ],
      }),
      event({ eventId: "p1-duplicate", startOffset: 10, endOffset: 17 }),
      event({
        eventId: "p2",
        startOffset: 30,
        endOffset: 37,
        participants: [
          { characterKey: "char-c", role: "actor", evidenceId: "m3" },
          { characterKey: "char-x", role: "patient", evidenceId: "m4" },
        ],
      }),
      event({
        eventId: "p3",
        startOffset: 50,
        endOffset: 57,
        participants: [{ characterKey: "char-a", role: "actor", evidenceId: "m1" }],
      }),
      event({ eventId: "p4", startOffset: 70, endOffset: 77 }),
    ]),
  });

  assert.equal(result.triggerDetection.truePositive, 3);
  assert.equal(result.triggerDetection.falsePositive, 2);
  assert.equal(result.triggerDetection.falseNegative, 0);
  assert.equal(result.duplicatePredictionCount, 1);
  assert.equal(result.duplicatePredictionRate, 0.2);
  assert.equal(result.unsupportedPredictionCount, 1);
  assert.equal(result.unsupportedPredictionRate, 0.2);
  assert.equal(result.participantGrounding.truePositive, 3);
  assert.equal(result.participantGrounding.falsePositive, 1);
  assert.equal(result.participantGrounding.falseNegative, 0);
  assert.equal(result.participantGrounding.precision, 0.75);
  assert.equal(result.participantGrounding.recall, 1);
  assert.equal(result.unknownParticipantEventMatchedCount, 1);
  assert.equal(result.unscoredParticipantAssignmentCount, 1);
});

test("missed known event triggers also reduce participant recall", () => {
  const result = evaluateEvents({
    reference: reference(),
    prediction: prediction([
      event({
        eventId: "p1",
        startOffset: 10,
        endOffset: 17,
        participants: [
          { characterKey: "char-a", role: "actor", evidenceId: "m1" },
          { characterKey: "char-b", role: "patient", evidenceId: "m2" },
        ],
      }),
    ]),
  });

  assert.equal(result.missedKnownParticipantEventCount, 1);
  assert.equal(result.participantGrounding.truePositive, 2);
  assert.equal(result.participantGrounding.falseNegative, 1);
  assert.equal(result.participantGrounding.recall, 2 / 3);
});

test("event evaluation fails closed on normalized-input mismatch", () => {
  assert.throws(
    () => evaluateEvents({ reference: reference(), prediction: prediction([], "d".repeat(64)) }),
    /event_input_fingerprint_mismatch/u,
  );
});

test("event prediction validation detects semantic tampering", () => {
  const result = prediction([event({ eventId: "p1", startOffset: 10, endOffset: 17 })]);
  result.events[0]!.participants.push({ characterKey: "char-a", role: "actor", evidenceId: "m1" });
  assert.throws(() => validateEventProviderResult(result), /event_prediction_output_fingerprint_mismatch/u);
});

test("event reference validation keeps unknown participant gold unscored", () => {
  const invalid = reference();
  invalid.events[2]!.participants.push({ characterKey: "char-a", role: "actor" });
  assert.throws(() => validateEventReference(invalid), /unknown_event_participants_must_be_empty:g3/u);
});
