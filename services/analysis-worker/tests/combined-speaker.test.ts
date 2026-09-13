import assert from "node:assert/strict";
import test from "node:test";

import { canonicalJson, sha256Hex } from "../src/ingestion/hash.js";
import type { NormalizedSection } from "../src/ingestion/types.js";
import type { CharacterIdentityResult, ResolvedIdentityMention } from "../src/identity/types.js";
import type { LocalLiteraryEvidenceBundle, QuoteSpeakerEvidence } from "../src/local-analysis/types.js";
import { predictCombinedSpeakerDialogue } from "../src/evaluation/combined-speaker.js";

function codePointOffset(text: string, codeUnitOffset: number) {
  return Array.from(text.slice(0, codeUnitOffset)).length;
}

function span(text: string, surface: string, from = 0) {
  const startCodeUnit = text.indexOf(surface, from);
  assert.notEqual(startCodeUnit, -1);
  return {
    startOffset: codePointOffset(text, startCodeUnit),
    endOffset: codePointOffset(text, startCodeUnit + surface.length),
  };
}

function section(text: string): NormalizedSection {
  return {
    stable_key: "document:fixture",
    ordinal: 0,
    section_kind: "document",
    title: null,
    source_locator: "fixture",
    start_offset: 0,
    end_offset: Array.from(text).length,
    normalized_text: text,
  };
}

function identity(text: string, entries: Array<{ surface: string; characterKey: string; from?: number }>): CharacterIdentityResult {
  const fingerprint = sha256Hex(text);
  const mentions: ResolvedIdentityMention[] = entries.map((entry, index) => {
    const located = span(text, entry.surface, entry.from ?? 0);
    return {
      evidenceId: `mention:${index}`,
      characterKey: entry.characterKey,
      surfaceText: entry.surface,
      startOffset: located.startOffset,
      endOffset: located.endOffset,
      structuralLocator: "document:fixture",
      mentionKind: "proper_name",
      resolutionState: "linked",
      evidenceTier: "canonical_seed",
      decisionReason: "fixture",
    };
  });
  const characters = [...new Set(entries.map((entry) => entry.characterKey))].map((characterKey) => ({
    characterKey,
    canonicalName: characterKey,
    admissionTier: "canonical_seed" as const,
    evidenceCount: mentions.filter((mention) => mention.characterKey === characterKey).length,
    aliases: [],
  }));
  return {
    resolverVersion: "fixture",
    resolverConfigFingerprint: sha256Hex("fixture-config"),
    provider: { name: "fixture_identity", model: null, revision: "fixture" },
    normalizedInputFingerprint: fingerprint,
    outputFingerprint: sha256Hex(canonicalJson({ characters, mentions })),
    characters,
    mentions,
  };
}

function literaryEvidence(text: string, quotes: QuoteSpeakerEvidence[]): LocalLiteraryEvidenceBundle {
  const fingerprint = sha256Hex(text);
  return {
    provider: { name: "fixture_booknlp", model: "small", revision: "fixture" },
    normalizedInputFingerprint: fingerprint,
    identityEvidence: {
      provider: { name: "fixture_booknlp", model: "small", revision: "fixture" },
      normalizedInputFingerprint: fingerprint,
      mentions: [],
    },
    entities: [],
    quotes,
    eventTriggers: [],
  };
}

function providerQuote(text: string, speakerSurface: string, options: { quoteShift?: number } = {}): QuoteSpeakerEvidence {
  const quoteSurface = "“Hello.”";
  const quote = span(text, quoteSurface);
  const speaker = span(text, speakerSurface);
  const shift = options.quoteShift ?? 0;
  return {
    evidenceId: `quote:${speakerSurface}:${shift}`,
    quoteText: quoteSurface,
    startOffset: quote.startOffset + shift,
    endOffset: quote.endOffset,
    structuralLocator: "document:fixture",
    speakerSurfaceText: speakerSurface,
    speakerStartOffset: speaker.startOffset,
    speakerEndOffset: speaker.endOffset,
    speakerProviderClusterId: "ignored-cluster",
  };
}

test("combined speaker accepts deterministic/provider agreement", () => {
  const text = "Alice said, “Hello.”";
  const result = predictCombinedSpeakerDialogue({
    sections: [section(text)],
    normalizedInputFingerprint: sha256Hex(text),
    identity: identity(text, [{ surface: "Alice", characterKey: "alice" }]),
    literaryEvidence: literaryEvidence(text, [providerQuote(text, "Alice")]),
  });

  assert.equal(result.quotes.length, 1);
  assert.equal(result.quotes[0]!.speakerKey, "alice");
  assert.match(result.quotes[0]!.decisionReason, /^combined_agreement:/u);
});

test("combined speaker uses provider only when deterministic attribution is unresolved", () => {
  const text = "“Hello.” Alice smiled.";
  const result = predictCombinedSpeakerDialogue({
    sections: [section(text)],
    normalizedInputFingerprint: sha256Hex(text),
    identity: identity(text, [{ surface: "Alice", characterKey: "alice" }]),
    literaryEvidence: literaryEvidence(text, [providerQuote(text, "Alice")]),
  });

  assert.equal(result.quotes[0]!.speakerKey, "alice");
  assert.match(result.quotes[0]!.decisionReason, /^combined_provider_fallback:/u);
});

test("combined speaker leaves deterministic/provider disagreement unresolved", () => {
  const text = "Bob watched. Alice said, “Hello.”";
  const result = predictCombinedSpeakerDialogue({
    sections: [section(text)],
    normalizedInputFingerprint: sha256Hex(text),
    identity: identity(text, [
      { surface: "Bob", characterKey: "bob" },
      { surface: "Alice", characterKey: "alice" },
    ]),
    literaryEvidence: literaryEvidence(text, [providerQuote(text, "Bob")]),
  });

  assert.equal(result.quotes[0]!.speakerKey, null);
  assert.match(result.quotes[0]!.decisionReason, /^combined_conflict_unresolved:/u);
});

test("combined speaker never lets a non-exact provider quote override deterministic boundaries", () => {
  const text = "Alice said, “Hello.”";
  const result = predictCombinedSpeakerDialogue({
    sections: [section(text)],
    normalizedInputFingerprint: sha256Hex(text),
    identity: identity(text, [{ surface: "Alice", characterKey: "alice" }]),
    literaryEvidence: literaryEvidence(text, [providerQuote(text, "Alice", { quoteShift: 1 })]),
  });

  assert.equal(result.quotes[0]!.speakerKey, "alice");
  assert.match(result.quotes[0]!.decisionReason, /^combined_deterministic_only:/u);
  assert.match(result.quotes[0]!.decisionReason, /provider_quote_no_exact_match/u);
});

test("combined speaker ignores provider cluster ids and requires exact resolved identity span", () => {
  const text = "“Hello.” Alice smiled.";
  const quote = providerQuote(text, "Alice");
  quote.speakerStartOffset! += 1;
  const result = predictCombinedSpeakerDialogue({
    sections: [section(text)],
    normalizedInputFingerprint: sha256Hex(text),
    identity: identity(text, [{ surface: "Alice", characterKey: "alice" }]),
    literaryEvidence: literaryEvidence(text, [quote]),
  });

  assert.equal(result.quotes[0]!.speakerKey, null);
  assert.match(result.quotes[0]!.decisionReason, /provider_speaker_not_uniquely_resolved/u);
});

test("combined speaker fails closed when provider evidence belongs to another normalized input", () => {
  const text = "Alice said, “Hello.”";
  const evidence = literaryEvidence(text, [providerQuote(text, "Alice")]);
  evidence.normalizedInputFingerprint = sha256Hex("different input");

  assert.throws(
    () => predictCombinedSpeakerDialogue({
      sections: [section(text)],
      normalizedInputFingerprint: sha256Hex(text),
      identity: identity(text, [{ surface: "Alice", characterKey: "alice" }]),
      literaryEvidence: evidence,
    }),
    /combined_speaker_provider_input_fingerprint_mismatch/u,
  );
});
