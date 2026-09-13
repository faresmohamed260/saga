import assert from "node:assert/strict";
import test from "node:test";

import { auditPatientGrounding } from "../src/evaluation/event-patient-audit.js";
import type { EventProviderResult } from "../src/evaluation/event-evaluation.js";
import type { GoldIdentityDocument } from "../src/evaluation/types.js";
import type { CharacterIdentityResult, ResolvedIdentityMention } from "../src/identity/types.js";
import type { LiteraryEntityEvidence, LocalLiteraryEvidenceBundle } from "../src/local-analysis/types.js";

const fingerprint = "a".repeat(64);
const provider = { name: "fixture", model: null, revision: "fixture" };
const locator = "section:source";

function linkedMention(characterKey: string, structuralLocator = locator): ResolvedIdentityMention {
  return {
    evidenceId: `identity:${characterKey}:${structuralLocator}`,
    characterKey,
    surfaceText: "Bob",
    startOffset: 10,
    endOffset: 13,
    structuralLocator,
    mentionKind: "proper_name",
    resolutionState: "linked",
    evidenceTier: "canonical_seed",
    decisionReason: "fixture",
  };
}

function evidence(entities: LiteraryEntityEvidence[] = []): LocalLiteraryEvidenceBundle {
  return {
    provider,
    normalizedInputFingerprint: fingerprint,
    identityEvidence: { provider, normalizedInputFingerprint: fingerprint, mentions: [] },
    entities,
    quotes: [],
    eventTriggers: [{
      evidenceId: "event:1",
      surfaceText: "hit",
      lemma: "hit",
      startOffset: 6,
      endOffset: 9,
      structuralLocator: locator,
      sentenceId: 0,
      tokenId: 1,
      dependencyRelation: "ROOT",
      syntacticHeadTokenId: 1,
    }],
    syntaxTokens: [
      {
        evidenceId: "syntax:1",
        surfaceText: "hit",
        lemma: "hit",
        startOffset: 6,
        endOffset: 9,
        structuralLocator: locator,
        paragraphId: 0,
        sentenceId: 0,
        tokenIdWithinSentence: 1,
        tokenId: 1,
        posTag: "VERB",
        finePosTag: "VBD",
        dependencyRelation: "ROOT",
        syntacticHeadTokenId: 1,
      },
      {
        evidenceId: "syntax:2",
        surfaceText: "Bob",
        lemma: "Bob",
        startOffset: 10,
        endOffset: 13,
        structuralLocator: locator,
        paragraphId: 0,
        sentenceId: 0,
        tokenIdWithinSentence: 2,
        tokenId: 2,
        posTag: "PROPN",
        finePosTag: "NNP",
        dependencyRelation: "dobj",
        syntacticHeadTokenId: 1,
      },
    ],
  };
}

function identity(mentions: ResolvedIdentityMention[]): CharacterIdentityResult {
  const keys = [...new Set(mentions.map((mention) => mention.characterKey).filter((key): key is string => Boolean(key)))];
  return {
    resolverVersion: "fixture",
    resolverConfigFingerprint: "b".repeat(64),
    provider,
    normalizedInputFingerprint: fingerprint,
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

function gold(mentions: GoldIdentityDocument["mentions"]): GoldIdentityDocument {
  return { documentId: "fixture", text: "Alice hit Bob.", mentions };
}

function prediction(patientEvidenceId: string | null = null): EventProviderResult {
  const participants = patientEvidenceId === null ? [] : [{
    characterKey: "bob",
    role: "patient" as const,
    evidenceId: patientEvidenceId,
  }];
  return {
    schemaVersion: "saga-event-prediction-v1",
    provider,
    normalizedInputFingerprint: fingerprint,
    events: [{
      eventId: "event-prediction:1",
      sectionKey: "section",
      startOffset: 6,
      endOffset: 9,
      participants,
      decisionReason: "fixture",
    }],
    outputFingerprint: "d".repeat(64),
  };
}

function personGold(characterId: string | null): GoldIdentityDocument["mentions"][number] {
  return {
    mentionId: "gold:person",
    surfaceText: "Bob",
    startOffset: 10,
    endOffset: 13,
    mentionKind: "proper_name",
    entityType: "person",
    goldCharacterId: characterId,
  };
}

test("patient audit recognizes an actually grounded character candidate", () => {
  const mention = linkedMention("bob");
  const result = auditPatientGrounding({
    evidence: evidence(),
    gold: gold([personGold("bob")]),
    identity: identity([mention]),
    prediction: prediction(mention.evidenceId),
  });
  assert.equal(result.candidateTokenCount, 1);
  assert.equal(result.byCategory.grounded_character, 1);
  assert.equal(result.byRelation.dobj, 1);
});

test("patient audit exposes a linked character that the grounding policy failed to emit", () => {
  const mention = linkedMention("bob");
  const result = auditPatientGrounding({
    evidence: evidence(),
    gold: gold([personGold("bob")]),
    identity: identity([mention]),
    prediction: prediction(),
  });
  assert.equal(result.byCategory.linked_character_not_grounded, 1);
});

test("patient audit distinguishes ambiguous identities from structural-locator mismatch", () => {
  const ambiguous = auditPatientGrounding({
    evidence: evidence(),
    gold: gold([personGold("bob")]),
    identity: identity([linkedMention("bob"), linkedMention("other")]),
    prediction: prediction(),
  });
  assert.equal(ambiguous.byCategory.ambiguous_linked_character, 1);

  const mismatch = auditPatientGrounding({
    evidence: evidence(),
    gold: gold([personGold("bob")]),
    identity: identity([linkedMention("bob", "different:locator")]),
    prediction: prediction(),
  });
  assert.equal(mismatch.byCategory.structural_locator_mismatch, 1);
});

test("patient audit separates unresolved people and missing oracle links", () => {
  const unresolved = auditPatientGrounding({
    evidence: evidence(),
    gold: gold([personGold(null)]),
    identity: identity([]),
    prediction: prediction(),
  });
  assert.equal(unresolved.byCategory.unresolved_person_gold, 1);

  const missing = auditPatientGrounding({
    evidence: evidence(),
    gold: gold([personGold("bob")]),
    identity: identity([]),
    prediction: prediction(),
  });
  assert.equal(missing.byCategory.gold_linked_person_missing_identity, 1);
});

test("patient audit separates gold non-person and provider-only entity evidence", () => {
  const nonPersonGold = auditPatientGrounding({
    evidence: evidence(),
    gold: gold([{
      mentionId: "gold:object",
      surfaceText: "Bob",
      startOffset: 10,
      endOffset: 13,
      mentionKind: "nominal",
      entityType: "non_person",
      goldCharacterId: null,
    }]),
    identity: identity([]),
    prediction: prediction(),
  });
  assert.equal(nonPersonGold.byCategory.non_person_gold, 1);

  const providerEntity: LiteraryEntityEvidence = {
    evidenceId: "provider:entity",
    surfaceText: "Bob",
    startOffset: 10,
    endOffset: 13,
    structuralLocator: locator,
    mentionKind: "proper_name",
    category: "organization",
    providerClusterId: null,
    boundaryQuality: "clean",
  };
  const providerOnly = auditPatientGrounding({
    evidence: evidence([providerEntity]),
    gold: gold([]),
    identity: identity([]),
    prediction: prediction(),
  });
  assert.equal(providerOnly.byCategory.provider_non_person, 1);
  assert.equal(providerOnly.providerNonPersonCategories.organization, 1);
});

test("patient audit distinguishes provider-only person evidence and no entity evidence", () => {
  const providerPerson: LiteraryEntityEvidence = {
    evidenceId: "provider:person",
    surfaceText: "Bob",
    startOffset: 10,
    endOffset: 13,
    structuralLocator: locator,
    mentionKind: "proper_name",
    category: "person",
    providerClusterId: "ignored",
    boundaryQuality: "clean",
  };
  const providerOnly = auditPatientGrounding({
    evidence: evidence([providerPerson]),
    gold: gold([]),
    identity: identity([]),
    prediction: prediction(),
  });
  assert.equal(providerOnly.byCategory.provider_person_only, 1);

  const none = auditPatientGrounding({
    evidence: evidence(),
    gold: gold([]),
    identity: identity([]),
    prediction: prediction(),
  });
  assert.equal(none.byCategory.no_entity_evidence, 1);
});

test("patient audit fails closed on missing syntax or fingerprint drift", () => {
  const noSyntax = evidence();
  delete noSyntax.syntaxTokens;
  assert.throws(
    () => auditPatientGrounding({ evidence: noSyntax, gold: gold([]), identity: identity([]), prediction: prediction() }),
    /patient_audit_missing_syntax/u,
  );

  const wrongIdentity = identity([]);
  wrongIdentity.normalizedInputFingerprint = "e".repeat(64);
  assert.throws(
    () => auditPatientGrounding({ evidence: evidence(), gold: gold([]), identity: wrongIdentity, prediction: prediction() }),
    /patient_audit_identity_fingerprint_mismatch/u,
  );
});
