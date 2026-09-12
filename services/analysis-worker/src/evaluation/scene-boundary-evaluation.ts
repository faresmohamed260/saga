import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import type { NormalizedSection } from "../ingestion/types.js";

export type SceneParagraph = {
  paragraphIndex: number;
  paragraphKey: string;
  startOffset: number;
  endOffset: number;
};

export type SceneSectionParagraphIndex = {
  sectionKey: string;
  sectionOrdinal: number;
  paragraphCount: number;
  paragraphs: SceneParagraph[];
};

export type SceneBoundaryAnnotation = {
  sectionKey: string;
  paragraphCount: number;
  sceneStartParagraphs: number[];
};

export type SceneBoundaryReference = {
  schemaVersion: "saga-scene-boundary-reference-v1";
  bookId: string;
  sourceSha256: string;
  normalizedInputFingerprint: string;
  annotationProtocolVersion: string;
  annotations: SceneBoundaryAnnotation[];
};

export type SceneBoundaryPrediction = {
  sectionKey: string;
  paragraphCount: number;
  sceneStartParagraphs: number[];
};

export type SceneBoundaryProviderResult = {
  schemaVersion: "saga-scene-boundary-prediction-v1";
  provider: { name: string; model: string | null; revision: string };
  normalizedInputFingerprint: string;
  predictions: SceneBoundaryPrediction[];
};

export type BoundaryScore = {
  truePositive: number;
  falsePositive: number;
  falseNegative: number;
  precision: number;
  recall: number;
  f1: number;
};

export type SceneBoundaryEvaluationReport = {
  schemaVersion: "saga-scene-boundary-evaluation-v1";
  bookId: string;
  provider: SceneBoundaryProviderResult["provider"];
  normalizedInputFingerprint: string;
  toleranceParagraphs: number;
  exact: BoundaryScore;
  tolerant: BoundaryScore;
  tolerantMeanAbsoluteParagraphError: number | null;
  goldSceneCount: number;
  predictedSceneCount: number;
  extraPredictionCount: number;
  missedGoldCount: number;
  chapterCount: number;
  outputFingerprint: string;
  chapters: Array<{
    sectionKey: string;
    goldBoundaryCount: number;
    predictedBoundaryCount: number;
    exact: BoundaryScore;
    tolerant: BoundaryScore;
    tolerantMeanAbsoluteParagraphError: number | null;
  }>;
};

function codePointLength(value: string) {
  return [...value].length;
}

export function buildSceneParagraphIndex(sections: NormalizedSection[]): SceneSectionParagraphIndex[] {
  return sections
    .filter((section) => section.section_kind === "chapter" || section.section_kind === "document")
    .map((section) => {
      const rawParagraphs = section.normalized_text.split(/\n\n+/u);
      const paragraphs: SceneParagraph[] = [];
      let searchFrom = 0;
      for (const raw of rawParagraphs) {
        const text = raw.trim();
        if (!text) continue;
        const startCodeUnit = section.normalized_text.indexOf(text, searchFrom);
        if (startCodeUnit < 0) throw new Error(`scene_paragraph_not_found:${section.stable_key}`);
        const prefix = section.normalized_text.slice(0, startCodeUnit);
        const startOffset = codePointLength(prefix);
        const endOffset = startOffset + codePointLength(text);
        const paragraphIndex = paragraphs.length;
        paragraphs.push({
          paragraphIndex,
          paragraphKey: `${section.stable_key}:p:${String(paragraphIndex).padStart(5, "0")}`,
          startOffset,
          endOffset,
        });
        searchFrom = startCodeUnit + text.length;
      }
      return {
        sectionKey: section.stable_key,
        sectionOrdinal: section.ordinal,
        paragraphCount: paragraphs.length,
        paragraphs,
      };
    });
}

function validateStarts(sectionKey: string, paragraphCount: number, starts: number[]) {
  if (!Number.isSafeInteger(paragraphCount) || paragraphCount < 1) {
    throw new Error(`invalid_scene_paragraph_count:${sectionKey}`);
  }
  if (starts.length === 0 || starts[0] !== 0) throw new Error(`scene_first_start_missing:${sectionKey}`);
  const seen = new Set<number>();
  for (const start of starts) {
    if (!Number.isSafeInteger(start) || start < 0 || start >= paragraphCount) {
      throw new Error(`invalid_scene_start:${sectionKey}:${start}`);
    }
    if (seen.has(start)) throw new Error(`duplicate_scene_start:${sectionKey}:${start}`);
    seen.add(start);
  }
  for (let index = 1; index < starts.length; index += 1) {
    if (starts[index]! <= starts[index - 1]!) throw new Error(`unsorted_scene_starts:${sectionKey}`);
  }
}

export function validateSceneBoundaryReference(reference: SceneBoundaryReference) {
  if (reference.schemaVersion !== "saga-scene-boundary-reference-v1") throw new Error("unsupported_scene_reference");
  if (!reference.bookId.trim() || !reference.annotationProtocolVersion.trim()) throw new Error("invalid_scene_reference_metadata");
  if (!/^[0-9a-f]{64}$/u.test(reference.sourceSha256)) throw new Error("invalid_scene_source_sha256");
  if (!/^[0-9a-f]{64}$/u.test(reference.normalizedInputFingerprint)) throw new Error("invalid_scene_input_fingerprint");
  if (reference.annotations.length === 0) throw new Error("empty_scene_reference");
  const sectionKeys = new Set<string>();
  for (const annotation of reference.annotations) {
    if (sectionKeys.has(annotation.sectionKey)) throw new Error(`duplicate_scene_reference_section:${annotation.sectionKey}`);
    sectionKeys.add(annotation.sectionKey);
    validateStarts(annotation.sectionKey, annotation.paragraphCount, annotation.sceneStartParagraphs);
  }
}

function validateProviderResult(result: SceneBoundaryProviderResult) {
  if (result.schemaVersion !== "saga-scene-boundary-prediction-v1") throw new Error("unsupported_scene_prediction");
  if (!result.provider.name.trim() || !result.provider.revision.trim()) throw new Error("invalid_scene_provider");
  if (!/^[0-9a-f]{64}$/u.test(result.normalizedInputFingerprint)) throw new Error("invalid_scene_prediction_fingerprint");
  const keys = new Set<string>();
  for (const prediction of result.predictions) {
    if (keys.has(prediction.sectionKey)) throw new Error(`duplicate_scene_prediction_section:${prediction.sectionKey}`);
    keys.add(prediction.sectionKey);
    validateStarts(prediction.sectionKey, prediction.paragraphCount, prediction.sceneStartParagraphs);
  }
}

function score(tp: number, fp: number, fn: number): BoundaryScore {
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

function exactScore(gold: number[], predicted: number[]) {
  const goldSet = new Set(gold);
  const predictedSet = new Set(predicted);
  const tp = predicted.filter((boundary) => goldSet.has(boundary)).length;
  return score(tp, predictedSet.size - tp, goldSet.size - tp);
}

function tolerantScore(gold: number[], predicted: number[], tolerance: number) {
  const candidates: Array<{ distance: number; gold: number; predicted: number }> = [];
  for (const predictedBoundary of predicted) {
    for (const goldBoundary of gold) {
      const distance = Math.abs(predictedBoundary - goldBoundary);
      if (distance <= tolerance) candidates.push({ distance, gold: goldBoundary, predicted: predictedBoundary });
    }
  }
  candidates.sort((a, b) => a.distance - b.distance || a.gold - b.gold || a.predicted - b.predicted);
  const matchedGold = new Set<number>();
  const matchedPredicted = new Set<number>();
  const distances: number[] = [];
  for (const candidate of candidates) {
    if (matchedGold.has(candidate.gold) || matchedPredicted.has(candidate.predicted)) continue;
    matchedGold.add(candidate.gold);
    matchedPredicted.add(candidate.predicted);
    distances.push(candidate.distance);
  }
  const result = score(matchedPredicted.size, predicted.length - matchedPredicted.size, gold.length - matchedGold.size);
  return {
    score: result,
    meanAbsoluteParagraphError: distances.length === 0 ? null : distances.reduce((sum, value) => sum + value, 0) / distances.length,
  };
}

function internalBoundaries(starts: number[]) {
  return starts.filter((start) => start > 0);
}

export function evaluateSceneBoundaries(input: {
  reference: SceneBoundaryReference;
  prediction: SceneBoundaryProviderResult;
  toleranceParagraphs?: number;
}): SceneBoundaryEvaluationReport {
  validateSceneBoundaryReference(input.reference);
  validateProviderResult(input.prediction);
  if (input.reference.normalizedInputFingerprint !== input.prediction.normalizedInputFingerprint) {
    throw new Error("scene_input_fingerprint_mismatch");
  }
  const toleranceParagraphs = input.toleranceParagraphs ?? 1;
  if (!Number.isSafeInteger(toleranceParagraphs) || toleranceParagraphs < 0 || toleranceParagraphs > 5) {
    throw new Error("invalid_scene_tolerance");
  }

  const predictions = new Map(input.prediction.predictions.map((value) => [value.sectionKey, value]));
  const chapters: SceneBoundaryEvaluationReport["chapters"] = [];
  const allGold: Array<{ sectionKey: string; boundary: number }> = [];
  const allPredicted: Array<{ sectionKey: string; boundary: number }> = [];
  let totalTolerantDistance = 0;
  let totalTolerantMatches = 0;
  let exactTp = 0;
  let exactFp = 0;
  let exactFn = 0;
  let tolerantTp = 0;
  let tolerantFp = 0;
  let tolerantFn = 0;
  let goldSceneCount = 0;
  let predictedSceneCount = 0;

  for (const annotation of input.reference.annotations) {
    const prediction = predictions.get(annotation.sectionKey);
    if (!prediction) throw new Error(`missing_scene_prediction:${annotation.sectionKey}`);
    if (prediction.paragraphCount !== annotation.paragraphCount) {
      throw new Error(`scene_paragraph_count_mismatch:${annotation.sectionKey}`);
    }
    predictions.delete(annotation.sectionKey);
    const gold = internalBoundaries(annotation.sceneStartParagraphs);
    const predicted = internalBoundaries(prediction.sceneStartParagraphs);
    const exact = exactScore(gold, predicted);
    const tolerant = tolerantScore(gold, predicted, toleranceParagraphs);
    exactTp += exact.truePositive;
    exactFp += exact.falsePositive;
    exactFn += exact.falseNegative;
    tolerantTp += tolerant.score.truePositive;
    tolerantFp += tolerant.score.falsePositive;
    tolerantFn += tolerant.score.falseNegative;
    if (tolerant.meanAbsoluteParagraphError !== null) {
      totalTolerantDistance += tolerant.meanAbsoluteParagraphError * tolerant.score.truePositive;
      totalTolerantMatches += tolerant.score.truePositive;
    }
    goldSceneCount += annotation.sceneStartParagraphs.length;
    predictedSceneCount += prediction.sceneStartParagraphs.length;
    allGold.push(...gold.map((boundary) => ({ sectionKey: annotation.sectionKey, boundary })));
    allPredicted.push(...predicted.map((boundary) => ({ sectionKey: annotation.sectionKey, boundary })));
    chapters.push({
      sectionKey: annotation.sectionKey,
      goldBoundaryCount: gold.length,
      predictedBoundaryCount: predicted.length,
      exact,
      tolerant: tolerant.score,
      tolerantMeanAbsoluteParagraphError: tolerant.meanAbsoluteParagraphError,
    });
  }
  if (predictions.size > 0) throw new Error(`unexpected_scene_prediction:${[...predictions.keys()].sort()[0]}`);

  const exact = score(exactTp, exactFp, exactFn);
  const tolerant = score(tolerantTp, tolerantFp, tolerantFn);
  const semantic = {
    bookId: input.reference.bookId,
    normalizedInputFingerprint: input.reference.normalizedInputFingerprint,
    provider: input.prediction.provider,
    toleranceParagraphs,
    exact,
    tolerant,
    goldSceneCount,
    predictedSceneCount,
    referenceBoundaries: allGold,
    predictedBoundaries: allPredicted,
  };
  return {
    schemaVersion: "saga-scene-boundary-evaluation-v1",
    bookId: input.reference.bookId,
    provider: input.prediction.provider,
    normalizedInputFingerprint: input.reference.normalizedInputFingerprint,
    toleranceParagraphs,
    exact,
    tolerant,
    tolerantMeanAbsoluteParagraphError: totalTolerantMatches === 0 ? null : totalTolerantDistance / totalTolerantMatches,
    goldSceneCount,
    predictedSceneCount,
    extraPredictionCount: tolerantFp,
    missedGoldCount: tolerantFn,
    chapterCount: chapters.length,
    outputFingerprint: sha256Hex(canonicalJson(semantic)),
    chapters,
  };
}
