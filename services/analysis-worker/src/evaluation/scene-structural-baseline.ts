import type { NormalizedSection } from "../ingestion/types.js";
import { buildSceneParagraphIndex, type SceneBoundaryProviderResult } from "./scene-boundary-evaluation.js";

export const SCENE_STRUCTURAL_BASELINE_REVISION = "saga-scene-structural-v1";

const ORNAMENT_ONLY = /^(?:(?:\*\s*){3,}|(?:#\s*){3,}|(?:[-–—]\s*){3,}|(?:~\s*){3,}|(?:•\s*){3,}|[⁂❦❧§]+)$/u;

function normalizedParagraphs(section: NormalizedSection) {
  return section.normalized_text
    .split(/\n\n+/u)
    .map((value) => value.trim())
    .filter(Boolean);
}

export function isStrongSceneBreakMarker(paragraph: string) {
  const normalized = paragraph.normalize("NFKC").trim();
  return normalized.length > 0 && normalized.length <= 40 && ORNAMENT_ONLY.test(normalized);
}

export function predictStructuralSceneBoundaries(input: {
  sections: NormalizedSection[];
  normalizedInputFingerprint: string;
}): SceneBoundaryProviderResult {
  if (!/^[0-9a-f]{64}$/u.test(input.normalizedInputFingerprint)) {
    throw new Error("invalid_scene_structural_input_fingerprint");
  }
  const indexes = buildSceneParagraphIndex(input.sections);
  const sectionsByKey = new Map(input.sections.map((section) => [section.stable_key, section]));

  return {
    schemaVersion: "saga-scene-boundary-prediction-v1",
    provider: {
      name: "saga_structural_scene_baseline",
      model: null,
      revision: SCENE_STRUCTURAL_BASELINE_REVISION,
    },
    normalizedInputFingerprint: input.normalizedInputFingerprint,
    predictions: indexes.map((index) => {
      const section = sectionsByKey.get(index.sectionKey);
      if (!section) throw new Error(`scene_structural_section_missing:${index.sectionKey}`);
      const paragraphs = normalizedParagraphs(section);
      if (paragraphs.length !== index.paragraphCount) {
        throw new Error(`scene_structural_paragraph_count_mismatch:${index.sectionKey}`);
      }
      const starts = new Set<number>([0]);
      for (let paragraphIndex = 0; paragraphIndex < paragraphs.length - 1; paragraphIndex += 1) {
        if (isStrongSceneBreakMarker(paragraphs[paragraphIndex]!)) starts.add(paragraphIndex + 1);
      }
      return {
        sectionKey: index.sectionKey,
        paragraphCount: index.paragraphCount,
        sceneStartParagraphs: [...starts].sort((a, b) => a - b),
      };
    }),
  };
}
