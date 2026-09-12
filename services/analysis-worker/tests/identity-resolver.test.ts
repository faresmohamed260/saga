import assert from "node:assert/strict";
import test from "node:test";

import { sha256Hex } from "../src/ingestion/hash.js";
import { resolveCharacterIdentity } from "../src/identity/resolver.js";
import type {
  IdentityBoundaryQuality,
  IdentityEntityType,
  IdentityMentionKind,
  IdentityPersonEvidence,
  NormalizedIdentityEvidence,
} from "../src/identity/types.js";

type MentionInput = {
  id: string;
  surface: string;
  occurrence?: number;
  kind: IdentityMentionKind;
  entity: IdentityEntityType;
  personEvidence: IdentityPersonEvidence;
  boundary?: IdentityBoundaryQuality;
  cluster?: string | null;
};

const provider = {
  name: "recorded-fixture",
  model: null,
  revision: "fixture-v1",
} as const;

function codePointOffset(text: string, codeUnitOffset: number) {
  return [...text.slice(0, codeUnitOffset)].length;
}

function locate(text: string, surface: string, occurrence = 0) {
  let from = 0;
  let index = -1;
  for (let i = 0; i <= occurrence; i += 1) {
    index = text.indexOf(surface, from);
    if (index < 0) throw new Error(`fixture surface not found: ${surface}`);
    from = index + surface.length;
  }
  return {
    startOffset: codePointOffset(text, index),
    endOffset: codePointOffset(text, index + surface.length),
  };
}

function evidence(text: string, mentions: MentionInput[]): NormalizedIdentityEvidence {
  return {
    provider,
    normalizedInputFingerprint: sha256Hex(text),
    mentions: mentions.map((mention) => ({
      evidenceId: mention.id,
      surfaceText: mention.surface,
      ...locate(text, mention.surface, mention.occurrence ?? 0),
      structuralLocator: "fixture:chapter-1",
      mentionKind: mention.kind,
      entityType: mention.entity,
      personEvidence: mention.personEvidence,
      boundaryQuality: mention.boundary ?? "clean",
      providerClusterId: mention.cluster ?? null,
    })),
  };
}

test("late strong-name evidence stabilizes earlier attachment without letting pronouns mint canonicals", () => {
  const text = "She ran. Ada Vale stopped. Miss Vale turned. Ada smiled.";
  const result = resolveCharacterIdentity({
    normalizedText: text,
    evidence: evidence(text, [
      { id: "m1", surface: "She", kind: "pronoun", entity: "person", personEvidence: "supporting", cluster: "ada" },
      { id: "m2", surface: "Ada Vale", kind: "proper_name", entity: "person", personEvidence: "strong", cluster: "ada" },
      { id: "m3", surface: "Miss Vale", kind: "proper_name", entity: "person", personEvidence: "strong", cluster: "ada" },
      { id: "m4", surface: "Ada", kind: "proper_name", entity: "person", personEvidence: "strong", cluster: "ada" },
    ]),
  });

  assert.equal(result.characters.length, 1);
  const character = result.characters[0]!;
  assert.equal(character.canonicalName, "Ada Vale");
  assert.equal(character.admissionTier, "stabilized");
  assert.equal(character.evidenceCount, 4);
  assert.deepEqual(
    character.aliases.map((alias) => alias.normalizedForm).sort(),
    ["ada", "ada vale", "vale"],
  );

  const pronoun = result.mentions.find((mention) => mention.evidenceId === "m1")!;
  assert.equal(pronoun.resolutionState, "linked");
  assert.equal(pronoun.evidenceTier, "attachment");
  assert.equal(pronoun.decisionReason, "unique_provider_cluster_attachment");
  assert.equal(pronoun.characterKey, character.characterKey);
});

test("historical false-canonical classes are quarantined instead of cleaned into identities", () => {
  const text = "You waited. What happened. This gleamed. Chancery Lane emptied. Healer called. Isaac Hale and vanished.";
  const result = resolveCharacterIdentity({
    normalizedText: text,
    evidence: evidence(text, [
      { id: "you", surface: "You", kind: "proper_name", entity: "person", personEvidence: "strong" },
      { id: "what", surface: "What", kind: "proper_name", entity: "person", personEvidence: "strong" },
      { id: "this", surface: "This", kind: "proper_name", entity: "unknown", personEvidence: "weak" },
      { id: "lane", surface: "Chancery Lane", kind: "proper_name", entity: "non_person", personEvidence: "strong" },
      { id: "healer", surface: "Healer", kind: "proper_name", entity: "person", personEvidence: "strong" },
      { id: "broken", surface: "Isaac Hale and", kind: "proper_name", entity: "person", personEvidence: "strong", boundary: "malformed" },
    ]),
  });

  assert.equal(result.characters.length, 0);
  assert.deepEqual(
    Object.fromEntries(result.mentions.map((mention) => [mention.evidenceId, [mention.resolutionState, mention.decisionReason]])),
    {
      you: ["quarantined", "blocked_surface"],
      what: ["quarantined", "blocked_surface"],
      this: ["quarantined", "blocked_surface"],
      lane: ["quarantined", "non_person_evidence"],
      healer: ["quarantined", "blocked_surface"],
      broken: ["quarantined", "malformed_span"],
    },
  );
});

test("sentence-initial capitalization and weak person evidence do not seed a canonical", () => {
  const text = "Morning came.";
  const result = resolveCharacterIdentity({
    normalizedText: text,
    evidence: evidence(text, [
      { id: "morning", surface: "Morning", kind: "proper_name", entity: "unknown", personEvidence: "weak" },
    ]),
  });

  assert.equal(result.characters.length, 0);
  assert.equal(result.mentions[0]?.resolutionState, "unresolved");
  assert.equal(result.mentions[0]?.decisionReason, "insufficient_seed_evidence");
});

test("contaminated provider clusters cannot force two incompatible canonical seeds together", () => {
  const text = "Cardan met Locke. He watched.";
  const result = resolveCharacterIdentity({
    normalizedText: text,
    evidence: evidence(text, [
      { id: "cardan", surface: "Cardan", kind: "proper_name", entity: "person", personEvidence: "strong", cluster: "contaminated" },
      { id: "locke", surface: "Locke", kind: "proper_name", entity: "person", personEvidence: "strong", cluster: "contaminated" },
      { id: "he", surface: "He", kind: "pronoun", entity: "person", personEvidence: "supporting", cluster: "contaminated" },
    ]),
  });

  assert.deepEqual(result.characters.map((character) => character.canonicalName), ["Cardan", "Locke"]);
  const pronoun = result.mentions.find((mention) => mention.evidenceId === "he")!;
  assert.equal(pronoun.characterKey, null);
  assert.equal(pronoun.resolutionState, "unresolved");
  assert.equal(pronoun.decisionReason, "ambiguous_provider_cluster");
});

test("a nominal can attach to one existing canonical but cannot create one alone", () => {
  const text = "The healer entered. Ada Vale nodded.";
  const result = resolveCharacterIdentity({
    normalizedText: text,
    evidence: evidence(text, [
      { id: "role", surface: "healer", kind: "nominal", entity: "person", personEvidence: "supporting", cluster: "ada" },
      { id: "ada", surface: "Ada Vale", kind: "proper_name", entity: "person", personEvidence: "strong", cluster: "ada" },
    ]),
  });

  assert.equal(result.characters.length, 1);
  assert.equal(result.mentions.find((mention) => mention.evidenceId === "role")?.resolutionState, "linked");
  assert.deepEqual(result.characters[0]?.aliases.map((alias) => alias.normalizedForm), ["ada vale"]);

  const roleOnlyText = "The healer entered.";
  const roleOnly = resolveCharacterIdentity({
    normalizedText: roleOnlyText,
    evidence: evidence(roleOnlyText, [
      { id: "role-only", surface: "healer", kind: "nominal", entity: "person", personEvidence: "supporting", cluster: "role" },
    ]),
  });
  assert.equal(roleOnly.characters.length, 0);
  assert.equal(roleOnly.mentions[0]?.resolutionState, "unresolved");
});

test("span mismatches are quarantined instead of silently repairing provider boundaries", () => {
  const text = "Ada arrived.";
  const fixture = evidence(text, [
    { id: "ada", surface: "Ada", kind: "proper_name", entity: "person", personEvidence: "strong" },
  ]);
  fixture.mentions[0] = { ...fixture.mentions[0]!, endOffset: fixture.mentions[0]!.endOffset + 1 };

  const result = resolveCharacterIdentity({ normalizedText: text, evidence: fixture });
  assert.equal(result.characters.length, 0);
  assert.equal(result.mentions[0]?.resolutionState, "quarantined");
  assert.equal(result.mentions[0]?.decisionReason, "span_text_mismatch");
});

test("fixed normalized evidence produces the same semantic identity output fingerprint", () => {
  const text = "She ran. Ada Vale stopped.";
  const fixture = evidence(text, [
    { id: "p", surface: "She", kind: "pronoun", entity: "person", personEvidence: "supporting", cluster: "ada" },
    { id: "n", surface: "Ada Vale", kind: "proper_name", entity: "person", personEvidence: "strong", cluster: "ada" },
  ]);

  const first = resolveCharacterIdentity({ normalizedText: text, evidence: structuredClone(fixture) });
  const second = resolveCharacterIdentity({ normalizedText: text, evidence: structuredClone(fixture) });

  assert.deepEqual(first, second);
  assert.match(first.outputFingerprint, /^[0-9a-f]{64}$/);
});
