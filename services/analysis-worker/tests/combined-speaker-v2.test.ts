import assert from "node:assert/strict";
import test from "node:test";

import { canonicalJson, sha256Hex } from "../src/ingestion/hash.js";
import type { CharacterIdentityResult, ResolvedIdentityMention } from "../src/identity/types.js";
import type { LocalLiteraryEvidenceBundle } from "../src/local-analysis/types.js";
import { predictCombinedSpeakerDialogue } from "../src/evaluation/combined-speaker.js";

const text = "“Hello.” Alice said. Bob watched.";
const fingerprint = sha256Hex(text);

function locate(surface: string) {
  const codeUnitStart = text.indexOf(surface);
  assert.notEqual(codeUnitStart, -1);
  return {
    startOffset: Array.from(text.slice(0, codeUnitStart)).length,
    endOffset: Array.from(text.slice(0, codeUnitStart + surface.length)).length,
  };
}

function resolvedMention(surface: string, characterKey: string, index: number): ResolvedIdentityMention {
  const located = locate(surface);
  return {
    evidenceId: `mention:${index}`,
    characterKey,
    surfaceText: surface,
    ...located,
    structuralLocator: "document:fixture",
    mentionKind: "proper_name",
    resolutionState: "linked",
    evidenceTier: "canonical_seed",
    decisionReason: "fixture",
  };
}

const mentions = [resolvedMention("Alice", "alice", 0), resolvedMention("Bob", "bob", 1)];
const identity: CharacterIdentityResult = {
  resolverVersion: "fixture",
  resolverConfigFingerprint: sha256Hex("fixture-config"),
  provider: { name: "fixture_identity", model: null, revision: "fixture" },
  normalizedInputFingerprint: fingerprint,
  outputFingerprint: sha256Hex(canonicalJson({ mentions })),
  characters: [
    { characterKey: "alice", canonicalName: "Alice", admissionTier: "canonical_seed", evidenceCount: 1, aliases: [] },
    { characterKey: "bob", canonicalName: "Bob", admissionTier: "canonical_seed", evidenceCount: 1, aliases: [] },
  ],
  mentions,
};

const quote = locate("“Hello.”");
const bob = locate("Bob");
const literaryEvidence: LocalLiteraryEvidenceBundle = {
  provider: { name: "fixture_booknlp", model: "small", revision: "fixture" },
  normalizedInputFingerprint: fingerprint,
  identityEvidence: {
    provider: { name: "fixture_booknlp", model: "small", revision: "fixture" },
    normalizedInputFingerprint: fingerprint,
    mentions: [],
  },
  entities: [],
  quotes: [{
    evidenceId: "quote:0",
    quoteText: "“Hello.”",
    ...quote,
    structuralLocator: "document:fixture",
    speakerSurfaceText: "Bob",
    speakerStartOffset: bob.startOffset,
    speakerEndOffset: bob.endOffset,
    speakerProviderClusterId: "ignored",
  }],
  eventTriggers: [],
};

const sections = [{
  stable_key: "document:fixture",
  ordinal: 0,
  section_kind: "document" as const,
  title: null,
  source_locator: "fixture",
  start_offset: 0,
  end_offset: Array.from(text).length,
  normalized_text: text,
}];

test("v2 prefers provider when conflict comes from a post-quote speech tag", () => {
  const result = predictCombinedSpeakerDialogue({ sections, normalizedInputFingerprint: fingerprint, identity, literaryEvidence });
  assert.equal(result.quotes.length, 1);
  assert.equal(result.quotes[0]!.speakerKey, "bob");
  assert.match(result.quotes[0]!.decisionReason, /^combined_conflict_provider_after:/u);
  assert.match(result.quotes[0]!.decisionReason, /speech_verb_linked_mention:after:/u);
});

test("legacy v1 unresolved-conflict policy remains reproducible", () => {
  const result = predictCombinedSpeakerDialogue({
    sections,
    normalizedInputFingerprint: fingerprint,
    identity,
    literaryEvidence,
    conflictPolicy: "unresolved",
  });
  assert.equal(result.quotes[0]!.speakerKey, null);
  assert.match(result.quotes[0]!.decisionReason, /^combined_conflict_unresolved:/u);
});
