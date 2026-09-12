import assert from "node:assert/strict";
import test from "node:test";

import {
  dialoguePredictionFingerprint,
  evaluateDialogue,
  validateDialogueProviderResult,
  validateDialogueReference,
  type DialogueProviderResult,
  type DialogueQuotePrediction,
  type DialogueReference,
} from "../src/evaluation/dialogue-evaluation.js";

const fingerprint = "a".repeat(64);

function reference(): DialogueReference {
  return {
    schemaVersion: "saga-dialogue-reference-v1",
    bookId: "book",
    sourceSha256: "b".repeat(64),
    normalizedInputFingerprint: fingerprint,
    annotationProtocolVersion: "dialogue-v1",
    quotes: [
      { quoteId: "q1", sectionKey: "c1", startOffset: 10, endOffset: 20, speakerStatus: "known", speakerKey: "char-a" },
      { quoteId: "q2", sectionKey: "c1", startOffset: 30, endOffset: 40, speakerStatus: "known", speakerKey: "char-b" },
      { quoteId: "q3", sectionKey: "c1", startOffset: 50, endOffset: 60, speakerStatus: "unknown", speakerKey: null },
    ],
  };
}

function prediction(quotes: DialogueQuotePrediction[], inputFingerprint = fingerprint): DialogueProviderResult {
  const provider = { name: "test", model: null, revision: "r1" };
  return {
    schemaVersion: "saga-dialogue-prediction-v1",
    provider,
    normalizedInputFingerprint: inputFingerprint,
    quotes,
    outputFingerprint: dialoguePredictionFingerprint({ provider, normalizedInputFingerprint: inputFingerprint, quotes }),
  };
}

test("dialogue evaluation scores exact quote spans and speaker contamination independently", () => {
  const result = evaluateDialogue({
    reference: reference(),
    prediction: prediction([
      { quoteId: "p1", sectionKey: "c1", startOffset: 10, endOffset: 20, speakerKey: "char-a", decisionReason: "test" },
      { quoteId: "p2", sectionKey: "c1", startOffset: 30, endOffset: 40, speakerKey: "char-c", decisionReason: "test" },
      { quoteId: "p3", sectionKey: "c1", startOffset: 50, endOffset: 60, speakerKey: "char-a", decisionReason: "test" },
      { quoteId: "p4", sectionKey: "c1", startOffset: 70, endOffset: 80, speakerKey: null, decisionReason: "test" },
    ]),
  });

  assert.equal(result.quoteDetection.truePositive, 3);
  assert.equal(result.quoteDetection.falsePositive, 1);
  assert.equal(result.quoteDetection.falseNegative, 0);
  assert.equal(result.quoteDetection.precision, 0.75);
  assert.equal(result.quoteDetection.recall, 1);
  assert.equal(result.knownSpeakerGoldCount, 2);
  assert.equal(result.matchedKnownSpeakerCount, 2);
  assert.equal(result.speakerCorrectCount, 1);
  assert.equal(result.speakerIncorrectCount, 1);
  assert.equal(result.speakerUnresolvedCount, 0);
  assert.equal(result.speakerAccuracyOnMatchedQuotes, 0.5);
  assert.equal(result.resolvedSpeakerAccuracy, 0.5);
  assert.equal(result.crossCharacterContaminationRateOnMatchedQuotes, 0.5);
  assert.equal(result.endToEndSpeakerRecall, 0.5);
  assert.equal(result.unknownSpeakerMatchedCount, 1);
  assert.equal(result.unscoredSpeakerAssignmentCount, 1);
});

test("dialogue evaluation reports unresolved known speakers without turning them into wrong-character contamination", () => {
  const result = evaluateDialogue({
    reference: reference(),
    prediction: prediction([
      { quoteId: "p1", sectionKey: "c1", startOffset: 10, endOffset: 20, speakerKey: "char-a", decisionReason: "test" },
      { quoteId: "p2", sectionKey: "c1", startOffset: 30, endOffset: 40, speakerKey: null, decisionReason: "test" },
      { quoteId: "p3", sectionKey: "c1", startOffset: 50, endOffset: 60, speakerKey: null, decisionReason: "test" },
    ]),
  });
  assert.equal(result.speakerCorrectCount, 1);
  assert.equal(result.speakerIncorrectCount, 0);
  assert.equal(result.speakerUnresolvedCount, 1);
  assert.equal(result.speakerUnresolvedRateOnMatchedQuotes, 0.5);
  assert.equal(result.crossCharacterContaminationRateOnMatchedQuotes, 0);
  assert.equal(result.resolvedSpeakerAccuracy, 1);
});

test("dialogue evaluation fails closed on normalized-input mismatch", () => {
  const differentFingerprint = "d".repeat(64);
  assert.throws(
    () => evaluateDialogue({
      reference: reference(),
      prediction: prediction([
        { quoteId: "p1", sectionKey: "c1", startOffset: 10, endOffset: 20, speakerKey: "char-a", decisionReason: "test" },
      ], differentFingerprint),
    }),
    /dialogue_input_fingerprint_mismatch/u,
  );
});

test("dialogue prediction validation rejects semantic fingerprint tampering", () => {
  const result = prediction([
    { quoteId: "p1", sectionKey: "c1", startOffset: 10, endOffset: 20, speakerKey: "char-a", decisionReason: "test" },
  ]);
  result.quotes[0]!.speakerKey = "char-tampered";
  assert.throws(() => validateDialogueProviderResult(result), /dialogue_prediction_output_fingerprint_mismatch/u);
});

test("dialogue reference validation enforces explicit speaker-status semantics", () => {
  const invalid = reference();
  invalid.quotes[2]!.speakerKey = "char-a";
  assert.throws(() => validateDialogueReference(invalid), /unscored_dialogue_speaker_must_be_null:q3/u);
});
