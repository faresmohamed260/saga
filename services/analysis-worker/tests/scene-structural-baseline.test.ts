import assert from "node:assert/strict";
import test from "node:test";

import {
  isStrongSceneBreakMarker,
  predictStructuralSceneBoundaries,
} from "../src/evaluation/scene-structural-baseline.js";
import type { NormalizedSection } from "../src/ingestion/types.js";

const fingerprint = "a".repeat(64);

function section(text: string): NormalizedSection {
  return {
    stable_key: "chapter-1",
    ordinal: 0,
    section_kind: "chapter",
    title: "Chapter One",
    source_locator: "epub:chapter-1.xhtml",
    start_offset: 0,
    end_offset: [...text].length,
    normalized_text: text,
  };
}

test("structural baseline recognizes only strong ornament-only paragraphs", () => {
  for (const marker of ["***", "* * *", "⁂", "❦", "— — —", "• • •"]) {
    assert.equal(isStrongSceneBreakMarker(marker), true, marker);
  }
  for (const prose of ["Hours later...", "*** whispered Jude", "Chapter 3", "- not a break", "Night Court"]) {
    assert.equal(isStrongSceneBreakMarker(prose), false, prose);
  }
});

test("structural baseline starts the scene after a marker paragraph", () => {
  const result = predictStructuralSceneBoundaries({
    sections: [section("Opening action.\n\n***\n\nNew place.\n\nStill there.\n\n⁂\n\nLater scene.")],
    normalizedInputFingerprint: fingerprint,
  });
  assert.deepEqual(result.predictions[0]?.sceneStartParagraphs, [0, 2, 5]);
  assert.equal(result.predictions[0]?.paragraphCount, 6);
  assert.equal(result.provider.model, null);
});

test("structural baseline deliberately ignores semantic-only shifts", () => {
  const result = predictStructuralSceneBoundaries({
    sections: [section("They left the palace.\n\nHours later, Jude woke in another room.\n\nShe found Cardan waiting.")],
    normalizedInputFingerprint: fingerprint,
  });
  assert.deepEqual(result.predictions[0]?.sceneStartParagraphs, [0]);
});

test("structural baseline fails closed on invalid source fingerprint", () => {
  assert.throws(
    () => predictStructuralSceneBoundaries({ sections: [section("Text")], normalizedInputFingerprint: "bad" }),
    /invalid_scene_structural_input_fingerprint/u,
  );
});
