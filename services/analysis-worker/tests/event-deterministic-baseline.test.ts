import assert from "node:assert/strict";
import test from "node:test";

import { predictDeterministicEventCandidates } from "../src/evaluation/event-deterministic-baseline.js";
import type { CharacterIdentityResult, ResolvedIdentityMention } from "../src/identity/types.js";
import type { NormalizedSection } from "../src/ingestion/types.js";

const fingerprint = "a".repeat(64);
const sectionKey = "chapter-1";

function cpLength(value: string) {
  return Array.from(value).length;
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

test("deterministic event floor anchors configured verbs and nearby canonical participants", () => {
  const text = "😀 Alice grabbed Bob. Carol entered.";
  const mentions = [
    mention(text, "Alice", "char-alice", "m1"),
    mention(text, "Bob", "char-bob", "m2"),
    mention(text, "Carol", "char-carol", "m3"),
  ];
  const result = predictDeterministicEventCandidates({
    sections: [section(text)],
    normalizedInputFingerprint: fingerprint,
    identity: identity(mentions),
  });

  assert.equal(result.events.length, 2);
  const grabbed = result.events.find((candidate) => candidate.decisionReason === "lexical_event_verb:grabbed");
  const entered = result.events.find((candidate) => candidate.decisionReason === "lexical_event_verb:entered");
  assert.ok(grabbed);
  assert.ok(entered);
  assert.equal(grabbed.startOffset, cpLength("😀 Alice "));
  assert.deepEqual(grabbed.participants, [
    { characterKey: "char-alice", role: "actor", evidenceId: "m1" },
    { characterKey: "char-bob", role: "patient", evidenceId: "m2" },
  ]);
  assert.deepEqual(entered.participants, [
    { characterKey: "char-carol", role: "actor", evidenceId: "m3" },
  ]);
});

test("participant attachment does not cross a sentence barrier", () => {
  const text = "Alice smiled. Bob grabbed Carol.";
  const result = predictDeterministicEventCandidates({
    sections: [section(text)],
    normalizedInputFingerprint: fingerprint,
    identity: identity([
      mention(text, "Alice", "char-alice", "m1"),
      mention(text, "Bob", "char-bob", "m2"),
      mention(text, "Carol", "char-carol", "m3"),
    ]),
  });
  const grabbed = result.events.find((candidate) => candidate.decisionReason === "lexical_event_verb:grabbed");
  assert.ok(grabbed);
  assert.deepEqual(grabbed.participants, [
    { characterKey: "char-bob", role: "actor", evidenceId: "m2" },
    { characterKey: "char-carol", role: "patient", evidenceId: "m3" },
  ]);
});

test("event floor emits triggers even when participant identity evidence is absent", () => {
  const text = "The door opened.";
  const result = predictDeterministicEventCandidates({
    sections: [section(text)],
    normalizedInputFingerprint: fingerprint,
    identity: identity([]),
  });
  assert.equal(result.events.length, 1);
  assert.equal(result.events[0]?.decisionReason, "lexical_event_verb:opened");
  assert.deepEqual(result.events[0]?.participants, []);
});

test("event floor ignores verbs outside the configured high-precision lexicon", () => {
  const text = "Alice contemplated Bob.";
  const result = predictDeterministicEventCandidates({
    sections: [section(text)],
    normalizedInputFingerprint: fingerprint,
    identity: identity([
      mention(text, "Alice", "char-alice", "m1"),
      mention(text, "Bob", "char-bob", "m2"),
    ]),
  });
  assert.deepEqual(result.events, []);
});

test("event floor fails closed when identity evidence belongs to another normalized input", () => {
  const text = "Alice grabbed Bob.";
  assert.throws(
    () => predictDeterministicEventCandidates({
      sections: [section(text)],
      normalizedInputFingerprint: fingerprint,
      identity: identity([
        mention(text, "Alice", "char-alice", "m1"),
        mention(text, "Bob", "char-bob", "m2"),
      ], "d".repeat(64)),
    }),
    /event_identity_input_fingerprint_mismatch/u,
  );
});
