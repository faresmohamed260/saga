import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import type { CharacterIdentityResult, ResolvedCharacter } from "../src/identity/types.js";
import {
  evaluatePrimaryFictionRegression,
  validatePrimaryFictionRegressionManifest,
  type PrimaryFictionRegressionCase,
  type PrimaryFictionRegressionManifest,
} from "../src/evaluation/primary-fiction-regression.js";

function character(key: string, canonicalName: string, aliases: string[]): ResolvedCharacter {
  return {
    characterKey: key,
    canonicalName,
    admissionTier: "canonical_seed",
    evidenceCount: Math.max(1, aliases.length),
    aliases: aliases.map((surfaceForm) => ({
      surfaceForm,
      normalizedForm: surfaceForm.toLocaleLowerCase("en-US").replace(/^prince\s+/u, "").replace(/^professor\s+/u, ""),
      evidenceCount: 1,
    })),
  };
}

function result(input: {
  characters: ResolvedCharacter[];
  linkedSurfaces?: Array<{ surfaceText: string; characterKey: string }>;
}): CharacterIdentityResult {
  return {
    resolverVersion: "test-resolver",
    resolverConfigFingerprint: "a".repeat(64),
    provider: { name: "test-provider", model: null, revision: "r1" },
    normalizedInputFingerprint: "b".repeat(64),
    outputFingerprint: "c".repeat(64),
    characters: input.characters,
    mentions: (input.linkedSurfaces ?? []).map((mention, index) => ({
      evidenceId: `e-${index}`,
      characterKey: mention.characterKey,
      surfaceText: mention.surfaceText,
      startOffset: index * 10,
      endOffset: index * 10 + [...mention.surfaceText].length,
      structuralLocator: null,
      mentionKind: "proper_name",
      resolutionState: "linked",
      evidenceTier: "attachment",
      decisionReason: "test",
    })),
  };
}

const cruelPrinceCase: PrimaryFictionRegressionCase = {
  caseId: "cruel-prince-full-book",
  bookId: "the-cruel-prince",
  title: "The Cruel Prince",
  scope: { kind: "full_book" },
  mustCanonicalSurfaces: ["Jude", "Cardan", "Taryn"],
  mustMergeSurfaceGroups: [["Cardan", "Prince Cardan"]],
  forbiddenCanonicalSurfaces: ["High Fae"],
  forbiddenLinkedSurfaces: ["High Fae"],
  notes: [],
};

test("primary-fiction evaluator passes merged title variants and rejects absent fantasy groups", () => {
  const report = evaluatePrimaryFictionRegression({
    regressionCase: cruelPrinceCase,
    result: result({
      characters: [
        character("jude", "Jude", ["Jude"]),
        character("cardan", "Prince Cardan", ["Prince Cardan", "Cardan"]),
        character("taryn", "Taryn", ["Taryn"]),
      ],
    }),
  });

  assert.equal(report.passed, true);
  assert.equal(report.failedAssertionCount, 0);
  assert.equal(report.passRate, 1);
});

test("primary-fiction evaluator exposes fragmentation rather than hiding it behind normalized titles", () => {
  const report = evaluatePrimaryFictionRegression({
    regressionCase: cruelPrinceCase,
    result: result({
      characters: [
        character("jude", "Jude", ["Jude"]),
        character("cardan", "Cardan", ["Cardan"]),
        character("prince-cardan", "Prince Cardan", ["Prince Cardan"]),
        character("taryn", "Taryn", ["Taryn"]),
      ],
    }),
  });

  assert.equal(report.passed, false);
  const merge = report.assertions.find((assertion) => assertion.kind === "must_merge");
  assert.equal(merge?.passed, false);
  assert.match(merge?.details ?? "", /2 canonical characters/u);
});

test("primary-fiction evaluator rejects a fantasy group admitted or attached as a character", () => {
  const admitted = evaluatePrimaryFictionRegression({
    regressionCase: cruelPrinceCase,
    result: result({
      characters: [
        character("jude", "Jude", ["Jude"]),
        character("cardan", "Prince Cardan", ["Prince Cardan", "Cardan"]),
        character("taryn", "Taryn", ["Taryn"]),
        character("high-fae", "High Fae", ["High Fae"]),
      ],
      linkedSurfaces: [{ surfaceText: "High Fae", characterKey: "high-fae" }],
    }),
  });

  assert.equal(admitted.passed, false);
  assert.equal(admitted.assertions.find((assertion) => assertion.kind === "forbidden_canonical")?.passed, false);
  assert.equal(admitted.assertions.find((assertion) => assertion.kind === "forbidden_link")?.passed, false);
});

test("historical primary-fiction manifest is valid and keeps opening/full-book scopes separate", async () => {
  const path = new URL("../benchmarks/primary-fiction-regression-expectations.v1.json", import.meta.url);
  const manifest = JSON.parse(await readFile(path, "utf8")) as PrimaryFictionRegressionManifest;
  assert.doesNotThrow(() => validatePrimaryFictionRegressionManifest(manifest));

  const opening = manifest.cases.find((entry) => entry.caseId === "harry-potter-opening-regression");
  const fullBook = manifest.cases.find((entry) => entry.caseId === "harry-potter-full-book");
  assert.equal(opening?.scope.kind, "bounded_epub");
  assert.equal(fullBook?.scope.kind, "full_book");
  assert.ok(opening?.forbiddenCanonicalSurfaces.includes("Harry Potter"));
  assert.ok(fullBook?.mustCanonicalSurfaces.includes("Harry Potter"));
});
