import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import type { NormalizedSection } from "../ingestion/types.js";
import { buildSceneParagraphIndex, type SceneBoundaryProviderResult } from "./scene-boundary-evaluation.js";

export type SceneLexicalBaselineConfig = {
  windowParagraphs: number;
  minimumTokensPerSide: number;
  minimumDissimilarity: number;
  madMultiplier: number;
};

export const DEFAULT_SCENE_LEXICAL_CONFIG: SceneLexicalBaselineConfig = {
  windowParagraphs: 2,
  minimumTokensPerSide: 8,
  minimumDissimilarity: 0.55,
  madMultiplier: 2,
};

function words(text: string) {
  return text
    .normalize("NFKC")
    .toLocaleLowerCase("en-US")
    .match(/[\p{L}\p{M}][\p{L}\p{M}'’-]*/gu) ?? [];
}

function termCounts(texts: string[]) {
  const counts = new Map<string, number>();
  let total = 0;
  for (const text of texts) {
    for (const word of words(text)) {
      if (word.length < 2) continue;
      counts.set(word, (counts.get(word) ?? 0) + 1);
      total += 1;
    }
  }
  return { counts, total };
}

function cosine(left: Map<string, number>, right: Map<string, number>) {
  let dot = 0;
  let leftNorm = 0;
  let rightNorm = 0;
  for (const value of left.values()) leftNorm += value * value;
  for (const value of right.values()) rightNorm += value * value;
  if (leftNorm === 0 || rightNorm === 0) return 0;
  for (const [term, value] of left) dot += value * (right.get(term) ?? 0);
  return dot / (Math.sqrt(leftNorm) * Math.sqrt(rightNorm));
}

function median(values: number[]) {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 1
    ? sorted[middle]!
    : (sorted[middle - 1]! + sorted[middle]!) / 2;
}

function threshold(scores: number[], config: SceneLexicalBaselineConfig) {
  if (scores.length === 0) return 1;
  const center = median(scores);
  const mad = median(scores.map((score) => Math.abs(score - center)));
  return Math.min(1, Math.max(config.minimumDissimilarity, center + config.madMultiplier * mad));
}

function validateConfig(config: SceneLexicalBaselineConfig) {
  if (!Number.isSafeInteger(config.windowParagraphs) || config.windowParagraphs < 1 || config.windowParagraphs > 10) {
    throw new Error("invalid_scene_lexical_window");
  }
  if (!Number.isSafeInteger(config.minimumTokensPerSide) || config.minimumTokensPerSide < 1) {
    throw new Error("invalid_scene_lexical_minimum_tokens");
  }
  if (!Number.isFinite(config.minimumDissimilarity) || config.minimumDissimilarity < 0 || config.minimumDissimilarity > 1) {
    throw new Error("invalid_scene_lexical_minimum_dissimilarity");
  }
  if (!Number.isFinite(config.madMultiplier) || config.madMultiplier < 0 || config.madMultiplier > 10) {
    throw new Error("invalid_scene_lexical_mad_multiplier");
  }
}

export function sceneLexicalConfigFingerprint(config: SceneLexicalBaselineConfig) {
  validateConfig(config);
  return sha256Hex(canonicalJson(config));
}

export function predictLexicalSceneBoundaries(input: {
  sections: NormalizedSection[];
  normalizedInputFingerprint: string;
  config?: SceneLexicalBaselineConfig;
}): SceneBoundaryProviderResult {
  if (!/^[0-9a-f]{64}$/u.test(input.normalizedInputFingerprint)) throw new Error("invalid_scene_lexical_input_fingerprint");
  const config = input.config ?? DEFAULT_SCENE_LEXICAL_CONFIG;
  validateConfig(config);
  const configFingerprint = sceneLexicalConfigFingerprint(config);
  const indexes = buildSceneParagraphIndex(input.sections);
  const sectionsByKey = new Map(input.sections.map((section) => [section.stable_key, section]));

  return {
    schemaVersion: "saga-scene-boundary-prediction-v1",
    provider: {
      name: "saga_lexical_scene_baseline",
      model: null,
      revision: `saga-scene-lexical-v1:${configFingerprint.slice(0, 16)}`,
    },
    normalizedInputFingerprint: input.normalizedInputFingerprint,
    predictions: indexes.map((index) => {
      const section = sectionsByKey.get(index.sectionKey);
      if (!section) throw new Error(`scene_lexical_section_missing:${index.sectionKey}`);
      const paragraphs = section.normalized_text.split(/\n\n+/u).map((value) => value.trim()).filter(Boolean);
      if (paragraphs.length !== index.paragraphCount) throw new Error(`scene_lexical_paragraph_count_mismatch:${index.sectionKey}`);

      const candidates: Array<{ boundary: number; dissimilarity: number }> = [];
      for (let boundary = 1; boundary < paragraphs.length; boundary += 1) {
        const left = termCounts(paragraphs.slice(Math.max(0, boundary - config.windowParagraphs), boundary));
        const right = termCounts(paragraphs.slice(boundary, Math.min(paragraphs.length, boundary + config.windowParagraphs)));
        if (left.total < config.minimumTokensPerSide || right.total < config.minimumTokensPerSide) continue;
        candidates.push({ boundary, dissimilarity: 1 - cosine(left.counts, right.counts) });
      }
      const cutoff = threshold(candidates.map((candidate) => candidate.dissimilarity), config);
      const starts = [0, ...candidates.filter((candidate) => candidate.dissimilarity >= cutoff).map((candidate) => candidate.boundary)];
      return {
        sectionKey: index.sectionKey,
        paragraphCount: index.paragraphCount,
        sceneStartParagraphs: [...new Set(starts)].sort((a, b) => a - b),
      };
    }),
  };
}
