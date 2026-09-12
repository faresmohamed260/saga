import assert from "node:assert/strict";
import test from "node:test";

import {
  predictLexicalSceneBoundaries,
  sceneLexicalConfigFingerprint,
  type SceneLexicalBaselineConfig,
} from "../src/evaluation/scene-lexical-baseline.js";
import type { NormalizedSection } from "../src/ingestion/types.js";

const fingerprint = "a".repeat(64);

function section(paragraphs: string[]): NormalizedSection {
  const text = paragraphs.join("\n\n");
  return {
    stable_key: "chapter-1",
    ordinal: 0,
    section_kind: "chapter",
    title: "Chapter One",
    source_locator: "epub:chapter.xhtml",
    start_offset: 0,
    end_offset: [...text].length,
    normalized_text: text,
  };
}

const permissiveConfig: SceneLexicalBaselineConfig = {
  windowParagraphs: 1,
  minimumTokensPerSide: 4,
  minimumDissimilarity: 0.6,
  madMultiplier: 0,
};

test("lexical baseline finds a strong vocabulary discontinuity", () => {
  const result = predictLexicalSceneBoundaries({
    sections: [section([
      "The ballroom music filled the palace while Jude watched the dancers turn beneath chandeliers.",
      "Cardan raised his goblet in the ballroom and the musicians began another courtly song.",
      "Snow covered the mountain trail as wolves circled the frozen camp beyond the pine forest.",
      "The riders pushed through ice and wind toward the distant mountain pass before nightfall.",
    ])],
    normalizedInputFingerprint: fingerprint,
    config: permissiveConfig,
  });
  assert.ok(result.predictions[0]?.sceneStartParagraphs.includes(2));
});

test("lexical baseline avoids inventing boundaries in highly continuous prose", () => {
  const result = predictLexicalSceneBoundaries({
    sections: [section([
      "Jude crossed the palace hall and watched Cardan speak beside the throne during the feast.",
      "At the palace feast Jude kept watching Cardan beside the throne while courtiers filled the hall.",
      "Cardan remained by the throne as Jude moved through the same crowded palace hall and listened.",
      "The feast continued in the palace hall while Jude and Cardan stayed near the throne together.",
    ])],
    normalizedInputFingerprint: fingerprint,
    config: permissiveConfig,
  });
  assert.deepEqual(result.predictions[0]?.sceneStartParagraphs, [0]);
});

test("lexical configuration is fingerprinted and parameter changes are new experiments", () => {
  const first = sceneLexicalConfigFingerprint(permissiveConfig);
  const second = sceneLexicalConfigFingerprint({ ...permissiveConfig, minimumDissimilarity: 0.61 });
  assert.equal(first.length, 64);
  assert.notEqual(first, second);
});

test("lexical baseline rejects invalid configuration", () => {
  assert.throws(
    () => predictLexicalSceneBoundaries({
      sections: [section(["one two three four", "five six seven eight"])],
      normalizedInputFingerprint: fingerprint,
      config: { ...permissiveConfig, windowParagraphs: 0 },
    }),
    /invalid_scene_lexical_window/u,
  );
});
