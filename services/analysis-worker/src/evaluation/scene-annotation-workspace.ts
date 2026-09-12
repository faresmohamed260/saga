import type { NormalizationResult } from "../ingestion/types.js";
import {
  buildSceneParagraphIndex,
  validateSceneBoundaryReference,
  type SceneBoundaryReference,
} from "./scene-boundary-evaluation.js";

export type SceneAnnotationWorkspaceSection = {
  sectionKey: string;
  title: string | null;
  sectionOrdinal: number;
  status: "pending" | "complete";
  paragraphs: Array<{
    paragraphIndex: number;
    paragraphKey: string;
    text: string;
  }>;
  sceneStartParagraphs: number[];
  ambiguousSceneStartParagraphs: number[];
  notes: string[];
};

export type SceneAnnotationWorkspace = {
  schemaVersion: "saga-private-scene-annotation-workspace-v1";
  privacy: "PRIVATE_SOURCE_TEXT_DO_NOT_COMMIT";
  bookId: string;
  sourceSha256: string;
  normalizedInputFingerprint: string;
  annotationProtocolVersion: string;
  sections: SceneAnnotationWorkspaceSection[];
};

export function createSceneAnnotationWorkspace(input: {
  bookId: string;
  sourceSha256: string;
  normalization: NormalizationResult;
  annotationProtocolVersion: string;
  sectionKeys?: string[];
}): SceneAnnotationWorkspace {
  if (!input.bookId.trim() || !input.annotationProtocolVersion.trim()) throw new Error("invalid_scene_workspace_metadata");
  if (!/^[0-9a-f]{64}$/u.test(input.sourceSha256)) throw new Error("invalid_scene_workspace_source_sha256");
  const wanted = input.sectionKeys ? new Set(input.sectionKeys) : null;
  const indexes = buildSceneParagraphIndex(input.normalization.sections);
  const sectionsByKey = new Map(input.normalization.sections.map((section) => [section.stable_key, section]));
  const selected = indexes.filter((index) => !wanted || wanted.has(index.sectionKey));
  if (selected.length === 0) throw new Error("empty_scene_annotation_workspace");
  if (wanted) {
    const observed = new Set(selected.map((entry) => entry.sectionKey));
    const missing = [...wanted].filter((key) => !observed.has(key));
    if (missing.length > 0) throw new Error(`scene_workspace_section_not_found:${missing.sort()[0]}`);
  }

  return {
    schemaVersion: "saga-private-scene-annotation-workspace-v1",
    privacy: "PRIVATE_SOURCE_TEXT_DO_NOT_COMMIT",
    bookId: input.bookId,
    sourceSha256: input.sourceSha256,
    normalizedInputFingerprint: input.normalization.outputFingerprint,
    annotationProtocolVersion: input.annotationProtocolVersion,
    sections: selected.map((index) => {
      const sourceSection = sectionsByKey.get(index.sectionKey);
      if (!sourceSection) throw new Error(`scene_workspace_source_section_missing:${index.sectionKey}`);
      const paragraphTexts = sourceSection.normalized_text.split(/\n\n+/u).map((value) => value.trim()).filter(Boolean);
      if (paragraphTexts.length !== index.paragraphCount) throw new Error(`scene_workspace_paragraph_count_mismatch:${index.sectionKey}`);
      return {
        sectionKey: index.sectionKey,
        title: sourceSection.title,
        sectionOrdinal: sourceSection.ordinal,
        status: "pending" as const,
        paragraphs: index.paragraphs.map((paragraph) => ({
          paragraphIndex: paragraph.paragraphIndex,
          paragraphKey: paragraph.paragraphKey,
          text: paragraphTexts[paragraph.paragraphIndex]!,
        })),
        sceneStartParagraphs: [0],
        ambiguousSceneStartParagraphs: [],
        notes: [],
      };
    }),
  };
}

export function finalizeSceneAnnotationWorkspace(workspace: SceneAnnotationWorkspace): SceneBoundaryReference {
  if (workspace.schemaVersion !== "saga-private-scene-annotation-workspace-v1") throw new Error("unsupported_scene_workspace");
  if (workspace.privacy !== "PRIVATE_SOURCE_TEXT_DO_NOT_COMMIT") throw new Error("invalid_scene_workspace_privacy_marker");
  const complete = workspace.sections.filter((section) => section.status === "complete");
  if (complete.length === 0) throw new Error("no_completed_scene_annotations");
  for (const section of complete) {
    if (section.paragraphs.length === 0) throw new Error(`empty_scene_workspace_section:${section.sectionKey}`);
    for (let index = 0; index < section.paragraphs.length; index += 1) {
      const paragraph = section.paragraphs[index]!;
      if (paragraph.paragraphIndex !== index || paragraph.paragraphKey !== `${section.sectionKey}:p:${String(index).padStart(5, "0")}`) {
        throw new Error(`scene_workspace_paragraph_identity_mismatch:${section.sectionKey}:${index}`);
      }
    }
  }
  const reference: SceneBoundaryReference = {
    schemaVersion: "saga-scene-boundary-reference-v1",
    bookId: workspace.bookId,
    sourceSha256: workspace.sourceSha256,
    normalizedInputFingerprint: workspace.normalizedInputFingerprint,
    annotationProtocolVersion: workspace.annotationProtocolVersion,
    annotations: complete.map((section) => ({
      sectionKey: section.sectionKey,
      paragraphCount: section.paragraphs.length,
      sceneStartParagraphs: [...section.sceneStartParagraphs],
      ambiguousSceneStartParagraphs: [...section.ambiguousSceneStartParagraphs],
    })),
  };
  validateSceneBoundaryReference(reference);
  return reference;
}
