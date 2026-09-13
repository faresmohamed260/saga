import assert from "node:assert/strict";
import test from "node:test";

import { sha256Hex } from "../src/ingestion/hash.js";
import { alignSingleSectionOracleIdentity } from "../src/evaluation/litbank-oracle-section-alignment.js";
import type { CharacterIdentityResult } from "../src/identity/types.js";
import type { NormalizedSection } from "../src/ingestion/types.js";

const text = "Alice waved.";
const fingerprint = sha256Hex(text);
const section: NormalizedSection = {
  stable_key: "litbank:fixture",
  ordinal: 0,
  section_kind: "document",
  title: null,
  source_locator: "litbank:fixture",
  start_offset: 0,
  end_offset: text.length,
  normalized_text: text,
};

function identity(): CharacterIdentityResult {
  return {
    resolverVersion: "oracle-fixture",
    resolverConfigFingerprint: "b".repeat(64),
    provider: { name: "oracle", model: null, revision: "fixture" },
    normalizedInputFingerprint: fingerprint,
    outputFingerprint: "c".repeat(64),
    characters: [{
      characterKey: "alice",
      canonicalName: "Alice",
      admissionTier: "canonical_seed",
      evidenceCount: 1,
      aliases: [],
    }],
    mentions: [{
      evidenceId: "m1",
      characterKey: "alice",
      surfaceText: "Alice",
      startOffset: 0,
      endOffset: 5,
      structuralLocator: "litbank:fixture",
      mentionKind: "proper_name",
      resolutionState: "linked",
      evidenceTier: "canonical_seed",
      decisionReason: "oracle_fixture",
    }],
  };
}

test("LitBank oracle alignment uses the provider structural-locator convention and re-fingerprints", () => {
  const before = identity();
  const aligned = alignSingleSectionOracleIdentity({ identity: before, section });
  assert.equal(aligned.mentions[0]!.structuralLocator, "litbank:fixture:litbank:fixture");
  assert.notEqual(aligned.outputFingerprint, before.outputFingerprint);
  assert.equal(before.mentions[0]!.structuralLocator, "litbank:fixture");
});

test("LitBank oracle alignment fails closed when a mention falls outside the section", () => {
  const outside = identity();
  outside.mentions[0] = { ...outside.mentions[0]!, endOffset: section.end_offset + 1 };
  assert.throws(
    () => alignSingleSectionOracleIdentity({ identity: outside, section }),
    /oracle_identity_mention_outside_section:m1/u,
  );
});
