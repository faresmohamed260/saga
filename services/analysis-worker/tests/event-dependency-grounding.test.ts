import assert from "node:assert/strict";
import test from "node:test";

import { predictDependencyGroundedEvents } from "../src/evaluation/event-dependency-grounding.js";
import type { NormalizedSection } from "../src/ingestion/types.js";
import type { CharacterIdentityResult, ResolvedIdentityMention } from "../src/identity/types.js";
import type {
  EventTriggerEvidence,
  LocalLiteraryEvidenceBundle,
  SyntaxTokenEvidence,
} from "../src/local-analysis/types.js";

const fingerprint = "a".repeat(64);
const sectionKey = "chapter-1";

function cpLength(value: string) {
  return Array.from(value).length;
}

function locate(text: string, surface: string, fromCodeUnit = 0) {
  const codeUnitStart = text.indexOf(surface, fromCodeUnit);
  if (codeUnitStart < 0) throw new Error(`fixture_surface_not_found:${surface}`);
  return {
    startOffset: cpLength(text.slice(0, codeUnitStart)),
    endOffset: cpLength(text.slice(0, codeUnitStart + surface.length)),
  };
}

function section(text: string): NormalizedSection {
  return {
    stable_key: sectionKey,
    ordinal: 0,
    section_kind: "chapter",
    title: "Chapter One",
    source_locator: "fixture:chapter-1",
    start_offset: 0,
    end_offset: cpLength(text),
    normalized_text: text,
  };
}

function mention(
  text: string,
  surfaceText: string,
  characterKey: string,
  evidenceId: string,
  fromCodeUnit = 0,
): ResolvedIdentityMention {
  const located = locate(text, surfaceText, fromCodeUnit);
  return {
    evidenceId,
    characterKey,
    surfaceText,
    ...located,
    structuralLocator: sectionKey,
    mentionKind: "proper_name",
    resolutionState: "linked",
    evidenceTier: "canonical_seed",
    decisionReason: "fixture",
  };
}

function identity(mentions: ResolvedIdentityMention[], inputFingerprint = fingerprint): CharacterIdentityResult {
  const keys = [...new Set(mentions.flatMap((value) => value.characterKey ? [value.characterKey] : []))];
  return {
    resolverVersion: "fixture",
    resolverConfigFingerprint: "b".repeat(64),
    provider: { name: "fixture_identity", model: null, revision: "fixture" },
    normalizedInputFingerprint: inputFingerprint,
    outputFingerprint: "c".repeat(64),
    characters: keys.map((characterKey) => ({
      characterKey,
      canonicalName: characterKey,
      admissionTier: "canonical_seed",
      evidenceCount: 1,
      aliases: [],
    })),
    mentions,
  };
}

function syntaxToken(input: {
  text: string;
  surface: string;
  tokenId: number;
  head: number;
  dependency: string;
  lemma?: string;
  sentenceId?: number;
  fromCodeUnit?: number;
}): SyntaxTokenEvidence {
  const located = locate(input.text, input.surface, input.fromCodeUnit ?? 0);
  return {
    evidenceId: `syntax:${input.tokenId}`,
    surfaceText: input.surface,
    lemma: input.lemma ?? input.surface.toLocaleLowerCase("en-US"),
    ...located,
    structuralLocator: sectionKey,
    paragraphId: 0,
    sentenceId: input.sentenceId ?? 0,
    tokenIdWithinSentence: input.tokenId,
    tokenId: input.tokenId,
    posTag: input.dependency === "ROOT" ? "VERB" : "PROPN",
    finePosTag: input.dependency === "ROOT" ? "VBD" : "NNP",
    dependencyRelation: input.dependency,
    syntacticHeadTokenId: input.head,
  };
}

function trigger(token: SyntaxTokenEvidence): EventTriggerEvidence {
  return {
    evidenceId: `event:${token.tokenId}`,
    surfaceText: token.surfaceText,
    lemma: token.lemma,
    startOffset: token.startOffset,
    endOffset: token.endOffset,
    structuralLocator: token.structuralLocator,
    sentenceId: token.sentenceId,
    tokenId: token.tokenId,
    dependencyRelation: token.dependencyRelation,
    syntacticHeadTokenId: token.syntacticHeadTokenId,
  };
}

function evidence(
  eventTriggers: EventTriggerEvidence[],
  syntaxTokens: SyntaxTokenEvidence[] | undefined,
  inputFingerprint = fingerprint,
): LocalLiteraryEvidenceBundle {
  return {
    provider: { name: "booknlp-small", model: "small", revision: "fixture" },
    normalizedInputFingerprint: inputFingerprint,
    identityEvidence: {
      provider: { name: "booknlp-small", model: "small", revision: "fixture" },
      normalizedInputFingerprint: inputFingerprint,
      mentions: [],
    },
    entities: [],
    quotes: [],
    eventTriggers,
    ...(syntaxTokens === undefined ? {} : { syntaxTokens }),
  };
}

test("dependency grounding attaches direct active subject and object through S.A.G.A. identity", () => {
  const text = "Alice struck Bob.";
  const alice = syntaxToken({ text, surface: "Alice", tokenId: 0, head: 1, dependency: "nsubj" });
  const struck = syntaxToken({ text, surface: "struck", tokenId: 1, head: 1, dependency: "ROOT", lemma: "strike" });
  const bob = syntaxToken({ text, surface: "Bob", tokenId: 2, head: 1, dependency: "dobj" });
  const result = predictDependencyGroundedEvents({
    sections: [section(text)],
    normalizedInputFingerprint: fingerprint,
    identity: identity([
      mention(text, "Alice", "char-alice", "m-alice"),
      mention(text, "Bob", "char-bob", "m-bob"),
    ]),
    literaryEvidence: evidence([trigger(struck)], [alice, struck, bob]),
  });

  assert.equal(result.events.length, 1);
  assert.deepEqual(result.events[0]!.participants, [
    { characterKey: "char-alice", role: "actor", evidenceId: "m-alice" },
    { characterKey: "char-bob", role: "patient", evidenceId: "m-bob" },
  ]);
});

test("dependency grounding handles passive patient and by-agent actor", () => {
  const text = "Bob was struck by Alice.";
  const bob = syntaxToken({ text, surface: "Bob", tokenId: 0, head: 2, dependency: "nsubjpass" });
  const was = syntaxToken({ text, surface: "was", tokenId: 1, head: 2, dependency: "auxpass" });
  const struck = syntaxToken({ text, surface: "struck", tokenId: 2, head: 2, dependency: "ROOT", lemma: "strike" });
  const by = syntaxToken({ text, surface: "by", tokenId: 3, head: 2, dependency: "agent" });
  const alice = syntaxToken({ text, surface: "Alice", tokenId: 4, head: 3, dependency: "pobj" });
  const result = predictDependencyGroundedEvents({
    sections: [section(text)],
    normalizedInputFingerprint: fingerprint,
    identity: identity([
      mention(text, "Bob", "char-bob", "m-bob"),
      mention(text, "Alice", "char-alice", "m-alice"),
    ]),
    literaryEvidence: evidence([trigger(struck)], [bob, was, struck, by, alice]),
  });

  assert.deepEqual(result.events[0]!.participants, [
    { characterKey: "char-alice", role: "actor", evidenceId: "m-alice" },
    { characterKey: "char-bob", role: "patient", evidenceId: "m-bob" },
  ]);
});

test("a syntax token may ground through one unambiguous multi-token identity mention", () => {
  const text = "Lady Alice struck Bob.";
  const lady = syntaxToken({ text, surface: "Lady", tokenId: 0, head: 1, dependency: "compound" });
  const alice = syntaxToken({ text, surface: "Alice", tokenId: 1, head: 2, dependency: "nsubj" });
  const struck = syntaxToken({ text, surface: "struck", tokenId: 2, head: 2, dependency: "ROOT", lemma: "strike" });
  const bob = syntaxToken({ text, surface: "Bob", tokenId: 3, head: 2, dependency: "dobj" });
  const result = predictDependencyGroundedEvents({
    sections: [section(text)],
    normalizedInputFingerprint: fingerprint,
    identity: identity([
      mention(text, "Lady Alice", "char-alice", "m-alice"),
      mention(text, "Bob", "char-bob", "m-bob"),
    ]),
    literaryEvidence: evidence([trigger(struck)], [lady, alice, struck, bob]),
  });

  assert.deepEqual(result.events[0]!.participants, [
    { characterKey: "char-alice", role: "actor", evidenceId: "m-alice" },
    { characterKey: "char-bob", role: "patient", evidenceId: "m-bob" },
  ]);
});

test("ambiguous covering identities remain ungrounded rather than choosing a character", () => {
  const text = "Lady Alice struck Bob.";
  const lady = syntaxToken({ text, surface: "Lady", tokenId: 0, head: 1, dependency: "compound" });
  const alice = syntaxToken({ text, surface: "Alice", tokenId: 1, head: 2, dependency: "nsubj" });
  const struck = syntaxToken({ text, surface: "struck", tokenId: 2, head: 2, dependency: "ROOT", lemma: "strike" });
  const bob = syntaxToken({ text, surface: "Bob", tokenId: 3, head: 2, dependency: "dobj" });
  const result = predictDependencyGroundedEvents({
    sections: [section(text)],
    normalizedInputFingerprint: fingerprint,
    identity: identity([
      mention(text, "Lady Alice", "char-title", "m-title"),
      mention(text, "Alice", "char-alice", "m-alice"),
      mention(text, "Bob", "char-bob", "m-bob"),
    ]),
    literaryEvidence: evidence([trigger(struck)], [lady, alice, struck, bob]),
  });

  assert.deepEqual(result.events[0]!.participants, [
    { characterKey: "char-bob", role: "patient", evidenceId: "m-bob" },
  ]);
});

test("dative syntax is deliberately not promoted to a participant in the conservative first policy", () => {
  const text = "Alice gave Bob a book.";
  const alice = syntaxToken({ text, surface: "Alice", tokenId: 0, head: 1, dependency: "nsubj" });
  const gave = syntaxToken({ text, surface: "gave", tokenId: 1, head: 1, dependency: "ROOT", lemma: "give" });
  const bob = syntaxToken({ text, surface: "Bob", tokenId: 2, head: 1, dependency: "dative" });
  const book = syntaxToken({ text, surface: "book", tokenId: 3, head: 1, dependency: "dobj" });
  const result = predictDependencyGroundedEvents({
    sections: [section(text)],
    normalizedInputFingerprint: fingerprint,
    identity: identity([
      mention(text, "Alice", "char-alice", "m-alice"),
      mention(text, "Bob", "char-bob", "m-bob"),
    ]),
    literaryEvidence: evidence([trigger(gave)], [alice, gave, bob, book]),
  });

  assert.deepEqual(result.events[0]!.participants, [
    { characterKey: "char-alice", role: "actor", evidenceId: "m-alice" },
  ]);
});

test("dependency grounding fails closed without syntax evidence or on fingerprint drift", () => {
  const text = "Alice struck Bob.";
  const struck = syntaxToken({ text, surface: "struck", tokenId: 1, head: 1, dependency: "ROOT", lemma: "strike" });
  assert.throws(
    () => predictDependencyGroundedEvents({
      sections: [section(text)],
      normalizedInputFingerprint: fingerprint,
      identity: identity([]),
      literaryEvidence: evidence([trigger(struck)], undefined),
    }),
    /event_dependency_syntax_evidence_missing/u,
  );
  assert.throws(
    () => predictDependencyGroundedEvents({
      sections: [section(text)],
      normalizedInputFingerprint: fingerprint,
      identity: identity([]),
      literaryEvidence: evidence([trigger(struck)], [struck], "d".repeat(64)),
    }),
    /event_dependency_provider_input_fingerprint_mismatch/u,
  );
});
