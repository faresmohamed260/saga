import assert from "node:assert/strict";
import test from "node:test";

import {
  buildSceneParagraphIndex,
  evaluateSceneBoundaries,
  validateSceneBoundaryReference,
  type SceneBoundaryProviderResult,
  type SceneBoundaryReference,
} from "../src/evaluation/scene-boundary-evaluation.js";
import type { NormalizedSection } from "../src/ingestion/types.js";

const fingerprint = "a".repeat(64);

function reference(starts = [0, 2, 5], ambiguous: number[] = []): SceneBoundaryReference {
  return {
    schemaVersion: "saga-scene-boundary-reference-v1",
    bookId: "book",
    sourceSha256: "b".repeat(64),
    normalizedInputFingerprint: fingerprint,
    annotationProtocolVersion: "scene-annotation-v1",
    annotations: [{
      sectionKey: "chapter-1",
      paragraphCount: 8,
      sceneStartParagraphs: starts,
      ambiguousSceneStartParagraphs: ambiguous,
    }],
  };
}

function prediction(starts = [0, 2, 5]): SceneBoundaryProviderResult {
  return {
    schemaVersion: "saga-scene-boundary-prediction-v1",
    provider: { name: "test", model: null, revision: "r1" },
    normalizedInputFingerprint: fingerprint,
    predictions: [{ sectionKey: "chapter-1", paragraphCount: 8, sceneStartParagraphs: starts }],
  };
}

test("scene paragraph index preserves stable source-anchored offsets", () => {
  const section: NormalizedSection = {
    stable_key: "chapter-1",
    ordinal: 1,
    section_kind: "chapter",
    title: "Chapter One",
    source_locator: "epub:chapter-1.xhtml",
    start_offset: 0,
    end_offset: 28,
    normalized_text: "One 😀 paragraph.\n\nSecond.\n\nThird.",
  };
  const index = buildSceneParagraphIndex([section]);
  assert.equal(index.length, 1);
  assert.deepEqual(index[0]?.paragraphs.map((paragraph) => paragraph.paragraphKey), [
    "chapter-1:p:00000",
    "chapter-1:p:00001",
    "chapter-1:p:00002",
  ]);
  assert.equal(index[0]?.paragraphs[0]?.startOffset, 0);
  assert.equal(index[0]?.paragraphs[0]?.endOffset, [..."One 😀 paragraph."].length);
  assert.equal(index[0]?.paragraphs[1]?.startOffset, [..."One 😀 paragraph.\n\n"].length);
});

test("exact scene boundaries score perfectly", () => {
  const report = evaluateSceneBoundaries({ reference: reference(), prediction: prediction() });
  assert.equal(report.exact.f1, 1);
  assert.equal(report.tolerant.f1, 1);
  assert.equal(report.goldSceneCount, 3);
  assert.equal(report.predictedSceneCount, 3);
  assert.equal(report.extraPredictionCount, 0);
  assert.equal(report.missedGoldCount, 0);
});

test("tolerant score credits one-paragraph boundary drift without hiding exact error", () => {
  const report = evaluateSceneBoundaries({
    reference: reference([0, 2, 5]),
    prediction: prediction([0, 3, 5]),
    toleranceParagraphs: 1,
  });
  assert.equal(report.exact.truePositive, 1);
  assert.equal(report.exact.falsePositive, 1);
  assert.equal(report.exact.falseNegative, 1);
  assert.equal(report.tolerant.f1, 1);
  assert.equal(report.tolerantMeanAbsoluteParagraphError, 0.5);
});

test("tolerant matching is one-to-one and exposes extra and missed boundaries", () => {
  const report = evaluateSceneBoundaries({
    reference: reference([0, 2, 6]),
    prediction: prediction([0, 1, 2, 7]),
    toleranceParagraphs: 1,
  });
  assert.equal(report.tolerant.truePositive, 2);
  assert.equal(report.tolerant.falsePositive, 1);
  assert.equal(report.tolerant.falseNegative, 0);
  assert.equal(report.extraPredictionCount, 1);
  assert.equal(report.missedGoldCount, 0);
});

test("tolerant matching maximizes one-to-one match count before minimizing distance", () => {
  const report = evaluateSceneBoundaries({
    reference: reference([0, 1, 2]),
    prediction: prediction([0, 2, 3]),
    toleranceParagraphs: 1,
  });
  assert.equal(report.tolerant.truePositive, 2);
  assert.equal(report.tolerant.falsePositive, 0);
  assert.equal(report.tolerant.falseNegative, 0);
  assert.equal(report.tolerant.f1, 1);
  assert.equal(report.tolerantMeanAbsoluteParagraphError, 1);
});

test("ambiguous annotation zones do not become required gold or false-positive traps", () => {
  const report = evaluateSceneBoundaries({
    reference: reference([0, 2, 6], [4]),
    prediction: prediction([0, 2, 4, 6]),
    toleranceParagraphs: 1,
  });
  assert.equal(report.tolerant.f1, 1);
  assert.equal(report.ambiguousBoundaryCount, 1);
  assert.equal(report.ignoredPredictionCount, 1);
  assert.equal(report.extraPredictionCount, 0);
  assert.equal(report.goldSceneCount, 3);
  assert.equal(report.predictedSceneCount, 4);
});

test("required boundaries take precedence when an ambiguous zone is nearby", () => {
  const report = evaluateSceneBoundaries({
    reference: reference([0, 2, 6], [3]),
    prediction: prediction([0, 3, 6]),
    toleranceParagraphs: 1,
  });
  assert.equal(report.tolerant.truePositive, 2);
  assert.equal(report.ignoredPredictionCount, 0);
  assert.equal(report.tolerant.f1, 1);
});

test("scene evaluator fails closed on source/version mismatches", () => {
  const badFingerprint = prediction();
  badFingerprint.normalizedInputFingerprint = "c".repeat(64);
  assert.throws(
    () => evaluateSceneBoundaries({ reference: reference(), prediction: badFingerprint }),
    /scene_input_fingerprint_mismatch/u,
  );

  const badCount = prediction();
  badCount.predictions[0]!.paragraphCount = 9;
  assert.throws(
    () => evaluateSceneBoundaries({ reference: reference(), prediction: badCount }),
    /scene_paragraph_count_mismatch:chapter-1/u,
  );
});

test("scene reference requires paragraph zero as the implicit first scene", () => {
  assert.throws(() => validateSceneBoundaryReference(reference([2, 5])), /scene_first_start_missing/u);
});

test("scene reference rejects ambiguous boundaries that duplicate required starts", () => {
  assert.throws(
    () => validateSceneBoundaryReference(reference([0, 2, 5], [5])),
    /overlapping_scene_reference_boundary/u,
  );
});
