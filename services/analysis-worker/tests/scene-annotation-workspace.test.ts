import assert from "node:assert/strict";
import test from "node:test";

import {
  createSceneAnnotationWorkspace,
  finalizeSceneAnnotationWorkspace,
} from "../src/evaluation/scene-annotation-workspace.js";
import type { NormalizationResult } from "../src/ingestion/types.js";

function normalization(): NormalizationResult {
  const text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph.";
  return {
    normalizationVersion: "test",
    configFingerprint: "a".repeat(64),
    normalizedSha256: "b".repeat(64),
    outputFingerprint: "c".repeat(64),
    normalizedText: text,
    sections: [{
      stable_key: "chapter-1",
      ordinal: 0,
      section_kind: "chapter",
      title: "Chapter One",
      source_locator: "epub:chapter.xhtml",
      start_offset: 0,
      end_offset: [...text].length,
      normalized_text: text,
    }],
  };
}

function multiSectionNormalization(): NormalizationResult {
  const first = normalization();
  const secondText = "Fourth paragraph.\n\nFifth paragraph.";
  return {
    ...first,
    normalizedText: `${first.normalizedText}\n\n${secondText}`,
    sections: [
      ...first.sections,
      {
        stable_key: "chapter-2",
        ordinal: 1,
        section_kind: "chapter",
        title: "Chapter Two",
        source_locator: "epub:chapter-2.xhtml",
        start_offset: [...first.normalizedText].length + 2,
        end_offset: [...first.normalizedText].length + 2 + [...secondText].length,
        normalized_text: secondText,
      },
    ],
  };
}

test("annotation workspace contains private prose but final reference strips it", () => {
  const workspace = createSceneAnnotationWorkspace({
    bookId: "private-book",
    sourceSha256: "d".repeat(64),
    normalization: normalization(),
    annotationProtocolVersion: "scene-annotation-v1",
  });
  assert.equal(workspace.privacy, "PRIVATE_SOURCE_TEXT_DO_NOT_COMMIT");
  assert.equal(workspace.sections[0]?.paragraphs[1]?.text, "Second paragraph.");
  workspace.sections[0]!.status = "complete";
  workspace.sections[0]!.sceneStartParagraphs = [0, 2];

  const reference = finalizeSceneAnnotationWorkspace(workspace);
  const rendered = JSON.stringify(reference);
  assert.equal(rendered.includes("First paragraph"), false);
  assert.equal(rendered.includes("Second paragraph"), false);
  assert.deepEqual(reference.annotations[0]?.sceneStartParagraphs, [0, 2]);
});

test("annotation finalization refuses unreviewed workspaces", () => {
  const workspace = createSceneAnnotationWorkspace({
    bookId: "private-book",
    sourceSha256: "d".repeat(64),
    normalization: normalization(),
    annotationProtocolVersion: "scene-annotation-v1",
  });
  assert.throws(() => finalizeSceneAnnotationWorkspace(workspace), /no_completed_scene_annotations/u);
});

test("annotation finalization refuses partially reviewed workspaces", () => {
  const workspace = createSceneAnnotationWorkspace({
    bookId: "private-book",
    sourceSha256: "d".repeat(64),
    normalization: multiSectionNormalization(),
    annotationProtocolVersion: "scene-annotation-v1",
  });
  workspace.sections[0]!.status = "complete";
  assert.throws(
    () => finalizeSceneAnnotationWorkspace(workspace),
    /incomplete_scene_annotations:chapter-2/u,
  );
});

test("annotation finalization fails if paragraph identity was edited", () => {
  const workspace = createSceneAnnotationWorkspace({
    bookId: "private-book",
    sourceSha256: "d".repeat(64),
    normalization: normalization(),
    annotationProtocolVersion: "scene-annotation-v1",
  });
  workspace.sections[0]!.status = "complete";
  workspace.sections[0]!.paragraphs[1]!.paragraphKey = "tampered";
  assert.throws(
    () => finalizeSceneAnnotationWorkspace(workspace),
    /scene_workspace_paragraph_identity_mismatch/u,
  );
});
