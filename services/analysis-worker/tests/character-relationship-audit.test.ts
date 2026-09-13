import assert from "node:assert/strict";
import test from "node:test";

import {
  auditCharacterRelationshipCoverage,
} from "../src/evaluation/character-relationship-audit.js";
import {
  deriveCharacterRelationshipEvidence,
} from "../src/evaluation/character-relationship-evidence.js";
import type { CharacterIdentityResult, ResolvedIdentityMention } from "../src/identity/types.js";
import type { LocalLiteraryEvidenceBundle, SyntaxTokenEvidence } from "../src/local-analysis/types.js";

const fingerprint = "a".repeat(64);
const identityFingerprint = "b".repeat(64);
const locator = "chapter-1:fixture:chapter-1";

function cpLength(value: string) {
  return Array.from(value).length;
}

function locate(text: string, surface: string, fromCodeUnit = 0) {
  const start = text.indexOf(surface, fromCodeUnit);
  if (start < 0) throw new Error(`fixture_surface_not_found:${surface}`);
  return {
    startOffset: cpLength(text.slice(0, start)),
    endOffset: cpLength(text.slice(0, start + surface.length)),
  };
}

function token(input: {
  text: string;
  surface: string;
  tokenId: number;
  head: number;
  dep: string;
  lemma?: string;
  sentenceId?: number;
  fromCodeUnit?: number;
  posTag?: string;
  finePosTag?: string;
  structuralLocator?: string | null;
}): SyntaxTokenEvidence {
  return {
    evidenceId: `syntax:${input.tokenId}`,
    surfaceText: input.surface,
    lemma: input.lemma ?? input.surface.toLocaleLowerCase("en-US"),
    ...locate(input.text, input.surface, input.fromCodeUnit ?? 0),
    structuralLocator: input.structuralLocator === undefined ? locator : input.structuralLocator,
    paragraphId: 0,
    sentenceId: input.sentenceId ?? 0,
    tokenIdWithinSentence: input.tokenId,
    tokenId: input.tokenId,
    posTag: input.posTag ?? (input.dep === "ROOT" ? "VERB" : "X"),
    finePosTag: input.finePosTag ?? "X",
    dependencyRelation: input.dep,
    syntacticHeadTokenId: input.head,
  };
}

function mention(input: {
  evidenceId: string;
  characterKey: string | null;
  token: SyntaxTokenEvidence;
  state?: "linked" | "unresolved" | "quarantined";
  structuralLocator?: string | null;
}): ResolvedIdentityMention {
  return {
    evidenceId: input.evidenceId,
    characterKey: input.characterKey,
    surfaceText: input.token.surfaceText,
    startOffset: input.token.startOffset,
    endOffset: input.token.endOffset,
    structuralLocator: input.structuralLocator === undefined ? input.token.structuralLocator : input.structuralLocator,
    mentionKind: input.token.posTag === "PRON" ? "pronoun" : "proper_name",
    resolutionState: input.state ?? "linked",
    evidenceTier: input.state === "quarantined" ? "quarantined" : "attachment",
    decisionReason: "fixture",
  };
}

function identity(mentions: ResolvedIdentityMention[]): CharacterIdentityResult {
  const keys = [...new Set(mentions.flatMap((item) => item.characterKey ? [item.characterKey] : []))].sort();
  return {
    resolverVersion: "fixture-resolver-v1",
    resolverConfigFingerprint: "c".repeat(64),
    provider: { name: "fixture", model: null, revision: "1" },
    normalizedInputFingerprint: fingerprint,
    outputFingerprint: identityFingerprint,
    characters: keys.map((key) => ({
      characterKey: key,
      canonicalName: key,
      admissionTier: "stabilized" as const,
      evidenceCount: 1,
      aliases: [],
    })),
    mentions,
  };
}

function evidence(tokens: SyntaxTokenEvidence[], inputFingerprint = fingerprint): LocalLiteraryEvidenceBundle {
  const provider = { name: "booknlp-small", model: "small", revision: "fixture" };
  return {
    provider,
    normalizedInputFingerprint: inputFingerprint,
    identityEvidence: { provider, normalizedInputFingerprint: inputFingerprint, mentions: [] },
    entities: [],
    quotes: [],
    eventTriggers: [],
    syntaxTokens: tokens,
  };
}

function audit(tokens: SyntaxTokenEvidence[], mentions: ResolvedIdentityMention[]) {
  const resolvedIdentity = identity(mentions);
  const literaryEvidence = evidence(tokens);
  const relationships = deriveCharacterRelationshipEvidence({
    normalizedInputFingerprint: fingerprint,
    identity: resolvedIdentity,
    literaryEvidence,
  });
  return auditCharacterRelationshipCoverage({ literaryEvidence, identity: resolvedIdentity, relationships });
}

test("relationship audit preserves accepted active and passive binary shapes", () => {
  const activeText = "Alice loves Bob.";
  const alice = token({ text: activeText, surface: "Alice", tokenId: 0, head: 1, dep: "nsubj" });
  const loves = token({ text: activeText, surface: "loves", tokenId: 1, head: 1, dep: "ROOT", lemma: "love" });
  const bob = token({ text: activeText, surface: "Bob", tokenId: 2, head: 1, dep: "dobj" });
  const active = audit([alice, loves, bob], [
    mention({ evidenceId: "alice", characterKey: "alice", token: alice }),
    mention({ evidenceId: "bob", characterKey: "bob", token: bob }),
  ]);
  assert.equal(active.predicateHitCount, 1);
  assert.equal(active.supportedBinarySyntaxCount, 1);
  assert.equal(active.groundedObservationCount, 1);
  assert.equal(active.syntaxCategoryCounts.accepted_active_shape, 1);
  assert.equal(active.groundingCategoryCounts.grounded_distinct_characters, 1);

  const passiveText = "Bob was betrayed by Alice.";
  const passiveBob = token({ text: passiveText, surface: "Bob", tokenId: 10, head: 12, dep: "nsubjpass" });
  const was = token({ text: passiveText, surface: "was", tokenId: 11, head: 12, dep: "auxpass", lemma: "be" });
  const betrayed = token({ text: passiveText, surface: "betrayed", tokenId: 12, head: 12, dep: "ROOT", lemma: "betray" });
  const by = token({ text: passiveText, surface: "by", tokenId: 13, head: 12, dep: "agent" });
  const passiveAlice = token({ text: passiveText, surface: "Alice", tokenId: 14, head: 13, dep: "pobj" });
  const passive = audit([passiveBob, was, betrayed, by, passiveAlice], [
    mention({ evidenceId: "bob-passive", characterKey: "bob", token: passiveBob }),
    mention({ evidenceId: "alice-passive", characterKey: "alice", token: passiveAlice }),
  ]);
  assert.equal(passive.supportedBinarySyntaxCount, 1);
  assert.equal(passive.syntaxCategoryCounts.accepted_passive_shape, 1);
  assert.equal(passive.groundingCategoryCounts.grounded_distinct_characters, 1);
});

test("relationship audit separates common unsupported active syntax shapes", () => {
  const subjectOnlyText = "Alice loves deeply.";
  const alice = token({ text: subjectOnlyText, surface: "Alice", tokenId: 0, head: 1, dep: "nsubj" });
  const loves = token({ text: subjectOnlyText, surface: "loves", tokenId: 1, head: 1, dep: "ROOT", lemma: "love" });
  const deeply = token({ text: subjectOnlyText, surface: "deeply", tokenId: 2, head: 1, dep: "advmod" });
  const subjectOnly = audit([alice, loves, deeply], [mention({ evidenceId: "alice", characterKey: "alice", token: alice })]);
  assert.equal(subjectOnly.syntaxCategoryCounts.active_subject_only, 1);
  assert.equal(subjectOnly.supportedBinarySyntaxCount, 0);

  const objectOnlyText = "Loved Bob.";
  const loved = token({ text: objectOnlyText, surface: "Loved", tokenId: 10, head: 10, dep: "ROOT", lemma: "love" });
  const bob = token({ text: objectOnlyText, surface: "Bob", tokenId: 11, head: 10, dep: "dobj" });
  const objectOnly = audit([loved, bob], [mention({ evidenceId: "bob", characterKey: "bob", token: bob })]);
  assert.equal(objectOnly.syntaxCategoryCounts.active_object_only, 1);

  const noRoleText = "Love endured.";
  const love = token({ text: noRoleText, surface: "Love", tokenId: 20, head: 20, dep: "ROOT", lemma: "love" });
  const endured = token({ text: noRoleText, surface: "endured", tokenId: 21, head: 20, dep: "advcl" });
  const noRole = audit([love, endured], []);
  assert.equal(noRole.syntaxCategoryCounts.no_direct_role_shape, 1);
});

test("relationship audit separates multiplicity and mixed active-passive syntax", () => {
  const text = "Alice and Carol love Bob.";
  const alice = token({ text, surface: "Alice", tokenId: 0, head: 3, dep: "nsubj" });
  const carol = token({ text, surface: "Carol", tokenId: 1, head: 3, dep: "nsubj" });
  const love = token({ text, surface: "love", tokenId: 3, head: 3, dep: "ROOT", lemma: "love" });
  const bob = token({ text, surface: "Bob", tokenId: 4, head: 3, dep: "dobj" });
  const multiple = audit([alice, carol, love, bob], [
    mention({ evidenceId: "alice", characterKey: "alice", token: alice }),
    mention({ evidenceId: "carol", characterKey: "carol", token: carol }),
    mention({ evidenceId: "bob", characterKey: "bob", token: bob }),
  ]);
  assert.equal(multiple.syntaxCategoryCounts.multiple_active_subjects, 1);

  const mixedText = "Alice was loved Bob by Carol.";
  const mixedAlice = token({ text: mixedText, surface: "Alice", tokenId: 10, head: 12, dep: "nsubj" });
  const mixedBob = token({ text: mixedText, surface: "Bob", tokenId: 13, head: 12, dep: "dobj" });
  const loved = token({ text: mixedText, surface: "loved", tokenId: 12, head: 12, dep: "ROOT", lemma: "love" });
  const by = token({ text: mixedText, surface: "by", tokenId: 14, head: 12, dep: "agent" });
  const mixedCarol = token({ text: mixedText, surface: "Carol", tokenId: 15, head: 14, dep: "pobj" });
  const mixed = audit([mixedAlice, loved, mixedBob, by, mixedCarol], []);
  assert.equal(mixed.syntaxCategoryCounts.mixed_active_passive_roles, 1);
});

test("relationship audit separates passive role failures", () => {
  const text = "Bob was betrayed by.";
  const bob = token({ text, surface: "Bob", tokenId: 0, head: 2, dep: "nsubjpass" });
  const was = token({ text, surface: "was", tokenId: 1, head: 2, dep: "auxpass", lemma: "be" });
  const betrayed = token({ text, surface: "betrayed", tokenId: 2, head: 2, dep: "ROOT", lemma: "betray" });
  const by = token({ text, surface: "by", tokenId: 3, head: 2, dep: "agent" });
  const missingPobj = audit([bob, was, betrayed, by], [mention({ evidenceId: "bob", characterKey: "bob", token: bob })]);
  assert.equal(missingPobj.syntaxCategoryCounts.passive_agent_missing_pobj, 1);

  const subjectOnlyText = "Bob was betrayed.";
  const subjectBob = token({ text: subjectOnlyText, surface: "Bob", tokenId: 10, head: 12, dep: "nsubjpass" });
  const subjectWas = token({ text: subjectOnlyText, surface: "was", tokenId: 11, head: 12, dep: "auxpass", lemma: "be" });
  const subjectBetrayed = token({ text: subjectOnlyText, surface: "betrayed", tokenId: 12, head: 12, dep: "ROOT", lemma: "betray" });
  const subjectOnly = audit([subjectBob, subjectWas, subjectBetrayed], [mention({ evidenceId: "bob-2", characterKey: "bob", token: subjectBob })]);
  assert.equal(subjectOnly.syntaxCategoryCounts.passive_subject_only, 1);
});

test("relationship audit distinguishes self and missing-character grounding", () => {
  const text = "Alice loves herself.";
  const alice = token({ text, surface: "Alice", tokenId: 0, head: 1, dep: "nsubj" });
  const loves = token({ text, surface: "loves", tokenId: 1, head: 1, dep: "ROOT", lemma: "love" });
  const herself = token({ text, surface: "herself", tokenId: 2, head: 1, dep: "dobj", posTag: "PRON", finePosTag: "PRP" });
  const self = audit([alice, loves, herself], [
    mention({ evidenceId: "alice", characterKey: "alice", token: alice }),
    mention({ evidenceId: "self", characterKey: "alice", token: herself }),
  ]);
  assert.equal(self.groundingCategoryCounts.self_relation, 1);
  assert.equal(self.groundedObservationCount, 0);

  const missing = audit([alice, loves, herself], [mention({ evidenceId: "alice-only", characterKey: "alice", token: alice })]);
  assert.equal(missing.groundingCategoryCounts.object_no_linked_character, 1);
  assert.equal(missing.objectRoleStatusCounts.no_linked_character, 1);
  assert.equal(missing.noCharacterArgumentPosTags.PRON, 1);
  assert.equal(missing.noCharacterArgumentFinePosTags.PRP, 1);
});

test("relationship audit separates ambiguous identity from locator mismatch", () => {
  const text = "Alice trusts Bob.";
  const alice = token({ text, surface: "Alice", tokenId: 0, head: 1, dep: "nsubj" });
  const trusts = token({ text, surface: "trusts", tokenId: 1, head: 1, dep: "ROOT", lemma: "trust" });
  const bob = token({ text, surface: "Bob", tokenId: 2, head: 1, dep: "dobj" });
  const ambiguous = audit([alice, trusts, bob], [
    mention({ evidenceId: "alice", characterKey: "alice", token: alice }),
    mention({ evidenceId: "bob-1", characterKey: "bob", token: bob }),
    mention({ evidenceId: "bob-2", characterKey: "robert", token: bob }),
  ]);
  assert.equal(ambiguous.groundingCategoryCounts.object_ambiguous_character, 1);
  assert.equal(ambiguous.objectRoleStatusCounts.ambiguous_character, 1);

  const mismatch = audit([alice, trusts, bob], [
    mention({ evidenceId: "alice-2", characterKey: "alice", token: alice }),
    mention({ evidenceId: "bob-mismatch", characterKey: "bob", token: bob, structuralLocator: "elsewhere" }),
  ]);
  assert.equal(mismatch.groundingCategoryCounts.object_locator_mismatch, 1);
  assert.equal(mismatch.objectRoleStatusCounts.structural_locator_mismatch, 1);
});

test("relationship audit fails closed on missing syntax, fingerprint drift and malformed heads", () => {
  const text = "Alice loves Bob.";
  const alice = token({ text, surface: "Alice", tokenId: 0, head: 1, dep: "nsubj" });
  const loves = token({ text, surface: "loves", tokenId: 1, head: 1, dep: "ROOT", lemma: "love" });
  const bob = token({ text, surface: "Bob", tokenId: 2, head: 1, dep: "dobj" });
  const tokens = [alice, loves, bob];
  const mentions = [
    mention({ evidenceId: "alice", characterKey: "alice", token: alice }),
    mention({ evidenceId: "bob", characterKey: "bob", token: bob }),
  ];
  const resolvedIdentity = identity(mentions);
  const literaryEvidence = evidence(tokens);
  const relationships = deriveCharacterRelationshipEvidence({
    normalizedInputFingerprint: fingerprint,
    identity: resolvedIdentity,
    literaryEvidence,
  });

  const { syntaxTokens: _syntaxTokens, ...withoutSyntax } = literaryEvidence;
  assert.throws(
    () => auditCharacterRelationshipCoverage({ literaryEvidence: withoutSyntax, identity: resolvedIdentity, relationships }),
    /relationship_audit_missing_syntax/,
  );

  assert.throws(
    () => auditCharacterRelationshipCoverage({ literaryEvidence: evidence(tokens, "d".repeat(64)), identity: resolvedIdentity, relationships }),
    /relationship_audit_identity_fingerprint_mismatch/,
  );

  const malformed = tokens.map((item) => item.tokenId === 0 ? { ...item, syntacticHeadTokenId: 99 } : item);
  assert.throws(
    () => auditCharacterRelationshipCoverage({ literaryEvidence: evidence(malformed), identity: resolvedIdentity, relationships }),
    /relationship_audit_missing_syntax_head/,
  );
});
