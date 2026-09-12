import assert from "node:assert/strict";
import test from "node:test";

import {
  extractDeterministicQuoteSpans,
  predictDeterministicDialogue,
} from "../src/evaluation/dialogue-deterministic-baseline.js";
import type { CharacterIdentityResult, ResolvedIdentityMention } from "../src/identity/types.js";
import type { NormalizedSection } from "../src/ingestion/types.js";

const fingerprint = "a".repeat(64);
const sectionKey = "chapter-1";

function cpLength(value: string) {
  return Array.from(value).length;
}

function cpIndexOf(text: string, value: string, fromCodeUnit = 0) {
  const index = text.indexOf(value, fromCodeUnit);
  if (index < 0) throw new Error(`test_value_not_found:${value}`);
  return cpLength(text.slice(0, index));
}

function section(text: string): NormalizedSection {
  return {
    stable_key: sectionKey,
    ordinal: 0,
    section_kind: "chapter",
    title: "Chapter One",
    source_locator: "test:chapter-1",
    start_offset: 0,
    end_offset: cpLength(text),
    normalized_text: text,
  };
}

function mention(text: string, surfaceText: string, characterKey: string, evidenceId: string, fromCodeUnit = 0): ResolvedIdentityMention {
  const codeUnitStart = text.indexOf(surfaceText, fromCodeUnit);
  if (codeUnitStart < 0) throw new Error(`test_mention_not_found:${surfaceText}`);
  const startOffset = cpLength(text.slice(0, codeUnitStart));
  return {
    evidenceId,
    characterKey,
    surfaceText,
    startOffset,
    endOffset: startOffset + cpLength(surfaceText),
    structuralLocator: sectionKey,
    mentionKind: "proper_name",
    resolutionState: "linked",
    evidenceTier: "canonical_seed",
    decisionReason: "test",
  };
}

function identity(mentions: ResolvedIdentityMention[], inputFingerprint = fingerprint): CharacterIdentityResult {
  const characterKeys = [...new Set(mentions.map((value) => value.characterKey).filter((value): value is string => value !== null))];
  return {
    resolverVersion: "test-resolver",
    resolverConfigFingerprint: "b".repeat(64),
    provider: { name: "test", model: null, revision: "r1" },
    normalizedInputFingerprint: inputFingerprint,
    outputFingerprint: "c".repeat(64),
    characters: characterKeys.map((characterKey) => ({
      characterKey,
      canonicalName: characterKey,
      admissionTier: "canonical_seed",
      evidenceCount: 1,
      aliases: [],
    })),
    mentions,
  };
}

test("deterministic dialogue baseline detects curly quotes and preserves Unicode code-point offsets", () => {
  const text = "Alice said, “Hello 😀.”";
  const inputSection = section(text);
  const result = predictDeterministicDialogue({
    sections: [inputSection],
    normalizedInputFingerprint: fingerprint,
    identity: identity([mention(text, "Alice", "char-alice", "m1")]),
  });
  assert.equal(result.quotes.length, 1);
  const quote = result.quotes[0]!;
  assert.equal(quote.startOffset, cpIndexOf(text, "“"));
  assert.equal(quote.endOffset, cpLength(text));
  assert.equal(quote.speakerKey, "char-alice");
  assert.match(quote.decisionReason, /^speech_verb_linked_mention:before:said:/u);
});

test("deterministic dialogue baseline attributes post-quote speech tags", () => {
  const text = "“Goodbye,” Bob replied.";
  const result = predictDeterministicDialogue({
    sections: [section(text)],
    normalizedInputFingerprint: fingerprint,
    identity: identity([mention(text, "Bob", "char-bob", "m1")]),
  });
  assert.equal(result.quotes[0]?.speakerKey, "char-bob");
  assert.match(result.quotes[0]?.decisionReason ?? "", /^speech_verb_linked_mention:after:replied:/u);
});

test("speech-verb proximity beats a nearer non-speaker name", () => {
  const text = "Alice said to Bob, “Hi.”";
  const mentions = [
    mention(text, "Alice", "char-alice", "m1"),
    mention(text, "Bob", "char-bob", "m2"),
  ];
  const result = predictDeterministicDialogue({
    sections: [section(text)],
    normalizedInputFingerprint: fingerprint,
    identity: identity(mentions),
  });
  assert.equal(result.quotes[0]?.speakerKey, "char-alice");
});

test("deterministic dialogue baseline remains unresolved without a speech-verb pair", () => {
  const text = "Alice smiled. “Hello.”";
  const result = predictDeterministicDialogue({
    sections: [section(text)],
    normalizedInputFingerprint: fingerprint,
    identity: identity([mention(text, "Alice", "char-alice", "m1")]),
  });
  assert.equal(result.quotes[0]?.speakerKey, null);
  assert.equal(result.quotes[0]?.decisionReason, "no_speech_verb_character_pair");
});

test("quote extraction supports paired straight double quotes and ignores unmatched opens", () => {
  const paired = extractDeterministicQuoteSpans([section('Alice asked, "Ready?"')]);
  assert.equal(paired.length, 1);
  const unmatched = extractDeterministicQuoteSpans([section("Alice said, “Hello.")]);
  assert.equal(unmatched.length, 0);
});

test("dialogue baseline fails closed when identity evidence belongs to a different normalized input", () => {
  const text = "Alice said, “Hello.”";
  assert.throws(
    () => predictDeterministicDialogue({
      sections: [section(text)],
      normalizedInputFingerprint: fingerprint,
      identity: identity([mention(text, "Alice", "char-alice", "m1")], "d".repeat(64)),
    }),
    /dialogue_identity_input_fingerprint_mismatch/u,
  );
});
