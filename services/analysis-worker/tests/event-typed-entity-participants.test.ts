import assert from "node:assert/strict";
import test from "node:test";

import {
  collectTypedEntityEventParticipantEvidence,
  type TypedEntityParticipantCandidateStatus,
} from "../src/evaluation/event-typed-entity-participants.js";
import {
  eventPredictionFingerprint,
  type EventParticipantPrediction,
  type EventProviderResult,
} from "../src/evaluation/event-evaluation.js";
import type { CharacterIdentityResult, ResolvedIdentityMention } from "../src/identity/types.js";
import type {
  LiteraryEntityCategory,
  LiteraryEntityEvidence,
  LocalLiteraryEvidenceBundle,
  SyntaxTokenEvidence,
} from "../src/local-analysis/types.js";

const fingerprint = "a".repeat(64);
const identityProvider = { name: "fixture-identity", model: null, revision: "fixture" };
const literaryProvider = { name: "fixture-literary", model: null, revision: "fixture" };
const eventProvider = { name: "fixture-event", model: null, revision: "fixture" };
const locator = "section:source";

function syntaxToken(input: Partial<SyntaxTokenEvidence> & Pick<SyntaxTokenEvidence, "tokenId" | "surfaceText">): SyntaxTokenEvidence {
  return {
    evidenceId: `syntax:${input.tokenId}`,
    surfaceText: input.surfaceText,
    lemma: input.lemma ?? input.surfaceText.toLowerCase(),
    startOffset: input.startOffset ?? 10,
    endOffset: input.endOffset ?? 14,
    structuralLocator: input.structuralLocator === undefined ? locator : input.structuralLocator,
    paragraphId: input.paragraphId ?? 0,
    sentenceId: input.sentenceId ?? 0,
    tokenIdWithinSentence: input.tokenIdWithinSentence ?? input.tokenId,
    tokenId: input.tokenId,
    posTag: input.posTag ?? "NOUN",
    finePosTag: input.finePosTag ?? "NN",
    dependencyRelation: input.dependencyRelation ?? "dobj",
    syntacticHeadTokenId: input.syntacticHeadTokenId ?? 1,
  };
}

function entity(
  category: LiteraryEntityCategory,
  options: {
    id?: string;
    locator?: string | null;
    boundaryQuality?: "clean" | "malformed";
    startOffset?: number;
    endOffset?: number;
  } = {},
): LiteraryEntityEvidence {
  return {
    evidenceId: options.id ?? `entity:${category}`,
    surfaceText: "item",
    startOffset: options.startOffset ?? 10,
    endOffset: options.endOffset ?? 14,
    structuralLocator: options.locator === undefined ? locator : options.locator,
    mentionKind: "nominal",
    category,
    providerClusterId: null,
    boundaryQuality: options.boundaryQuality ?? "clean",
  };
}

function bundle(input: {
  dependencyPath?: "nsubj" | "dobj" | "nsubjpass" | "agent->pobj";
  entities?: LiteraryEntityEvidence[];
} = {}): LocalLiteraryEvidenceBundle {
  const dependencyPath = input.dependencyPath ?? "dobj";
  const trigger = syntaxToken({
    tokenId: 1,
    surfaceText: "moved",
    lemma: "move",
    startOffset: 4,
    endOffset: 9,
    posTag: "VERB",
    finePosTag: "VBD",
    dependencyRelation: "ROOT",
    syntacticHeadTokenId: 1,
    tokenIdWithinSentence: 1,
  });
  const syntaxTokens = [trigger];
  if (dependencyPath === "agent->pobj") {
    syntaxTokens.push(syntaxToken({
      tokenId: 2,
      surfaceText: "by",
      startOffset: 9,
      endOffset: 10,
      dependencyRelation: "agent",
      syntacticHeadTokenId: 1,
      tokenIdWithinSentence: 2,
      posTag: "ADP",
      finePosTag: "IN",
    }));
    syntaxTokens.push(syntaxToken({
      tokenId: 3,
      surfaceText: "item",
      dependencyRelation: "pobj",
      syntacticHeadTokenId: 2,
      tokenIdWithinSentence: 3,
      posTag: "PROPN",
      finePosTag: "NNP",
    }));
  } else {
    syntaxTokens.push(syntaxToken({
      tokenId: 2,
      surfaceText: "item",
      dependencyRelation: dependencyPath,
      syntacticHeadTokenId: 1,
      tokenIdWithinSentence: 2,
      posTag: "PROPN",
      finePosTag: "NNP",
    }));
  }
  return {
    provider: literaryProvider,
    normalizedInputFingerprint: fingerprint,
    identityEvidence: {
      provider: literaryProvider,
      normalizedInputFingerprint: fingerprint,
      mentions: [],
    },
    entities: input.entities ?? [],
    quotes: [],
    eventTriggers: [{
      evidenceId: "event-trigger:1",
      surfaceText: trigger.surfaceText,
      lemma: trigger.lemma,
      startOffset: trigger.startOffset,
      endOffset: trigger.endOffset,
      structuralLocator: trigger.structuralLocator,
      sentenceId: trigger.sentenceId,
      tokenId: trigger.tokenId,
      dependencyRelation: trigger.dependencyRelation,
      syntacticHeadTokenId: trigger.syntacticHeadTokenId,
    }],
    syntaxTokens,
  };
}

function identity(mentions: ResolvedIdentityMention[] = []): CharacterIdentityResult {
  const keys = [...new Set(mentions.map((mention) => mention.characterKey).filter((key): key is string => key !== null))];
  return {
    resolverVersion: "fixture",
    resolverConfigFingerprint: "b".repeat(64),
    provider: identityProvider,
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

function linkedMention(characterKey = "alice"): ResolvedIdentityMention {
  return {
    evidenceId: `identity:${characterKey}`,
    characterKey,
    surfaceText: "item",
    startOffset: 10,
    endOffset: 14,
    structuralLocator: locator,
    mentionKind: "proper_name",
    resolutionState: "linked",
    evidenceTier: "canonical_seed",
    decisionReason: "fixture",
  };
}

function prediction(participants: EventParticipantPrediction[] = []): EventProviderResult {
  const events = [{
    eventId: "event:1",
    sectionKey: "section",
    startOffset: 4,
    endOffset: 9,
    participants,
    decisionReason: "fixture",
  }];
  const core = { provider: eventProvider, normalizedInputFingerprint: fingerprint, events };
  return {
    schemaVersion: "saga-event-prediction-v1",
    ...core,
    outputFingerprint: eventPredictionFingerprint(core),
  };
}

function collect(input: {
  dependencyPath?: "nsubj" | "dobj" | "nsubjpass" | "agent->pobj";
  entities?: LiteraryEntityEvidence[];
  identity?: CharacterIdentityResult;
  prediction?: EventProviderResult;
} = {}) {
  const bundleInput: NonNullable<Parameters<typeof bundle>[0]> = {};
  if (input.dependencyPath !== undefined) bundleInput.dependencyPath = input.dependencyPath;
  if (input.entities !== undefined) bundleInput.entities = input.entities;
  return collectTypedEntityEventParticipantEvidence({
    normalizedInputFingerprint: fingerprint,
    identity: input.identity ?? identity(),
    literaryEvidence: bundle(bundleInput),
    eventPrediction: input.prediction ?? prediction(),
  });
}

function onlyStatus(result: ReturnType<typeof collect>): TypedEntityParticipantCandidateStatus {
  assert.equal(result.candidates.length, 1);
  return result.candidates[0]!.status;
}

test("typed entity participant layer records a clean organization as direct actor evidence", () => {
  const result = collect({ dependencyPath: "nsubj", entities: [entity("organization")] });
  assert.equal(result.evidence.length, 1);
  assert.equal(result.evidence[0]!.role, "actor");
  assert.equal(result.evidence[0]!.dependencyPath, "nsubj");
  assert.equal(result.evidence[0]!.entityCategory, "organization");
  assert.equal(onlyStatus(result), "typed_non_person");
});

test("typed entity participant layer records a clean location as direct patient evidence", () => {
  const result = collect({ dependencyPath: "dobj", entities: [entity("location")] });
  assert.equal(result.evidence.length, 1);
  assert.equal(result.evidence[0]!.role, "patient");
  assert.equal(result.evidence[0]!.entityCategory, "location");
});

test("typed entity participant layer follows passive agent to pobj without enabling general pobj inheritance", () => {
  const result = collect({ dependencyPath: "agent->pobj", entities: [entity("facility")] });
  assert.equal(result.evidence.length, 1);
  assert.equal(result.evidence[0]!.role, "actor");
  assert.equal(result.evidence[0]!.dependencyPath, "agent->pobj");
  assert.equal(result.evidence[0]!.syntaxTokenId, 3);
});

test("canonical character grounding wins over overlapping non-person provider evidence", () => {
  const mention = linkedMention();
  const result = collect({
    dependencyPath: "nsubj",
    entities: [entity("organization")],
    identity: identity([mention]),
    prediction: prediction([{ characterKey: "alice", role: "actor", evidenceId: mention.evidenceId }]),
  });
  assert.equal(result.evidence.length, 0);
  assert.equal(onlyStatus(result), "character_grounded");
});

test("overlapping clean non-person provider entities remain ambiguous rather than being chosen arbitrarily", () => {
  const result = collect({
    entities: [
      entity("location", { id: "entity:location" }),
      entity("facility", { id: "entity:facility" }),
    ],
  });
  assert.equal(result.evidence.length, 0);
  assert.equal(onlyStatus(result), "ambiguous_non_person");
  assert.deepEqual(result.candidates[0]!.entityEvidenceIds, ["entity:facility", "entity:location"]);
  assert.deepEqual(result.candidates[0]!.entityCategories, ["facility", "location"]);
});

test("malformed and structurally mislocated non-person evidence is rejected explicitly", () => {
  const malformed = collect({ entities: [entity("vehicle", { boundaryQuality: "malformed" })] });
  assert.equal(malformed.evidence.length, 0);
  assert.equal(onlyStatus(malformed), "malformed_non_person");

  const mismatch = collect({ entities: [entity("vehicle", { locator: "different:locator" })] });
  assert.equal(mismatch.evidence.length, 0);
  assert.equal(onlyStatus(mismatch), "structural_locator_mismatch");
});

test("person and unknown provider evidence never becomes typed non-character participant evidence", () => {
  const person = collect({ entities: [entity("person")] });
  assert.equal(person.evidence.length, 0);
  assert.equal(onlyStatus(person), "person_only");

  const unknown = collect({ entities: [entity("unknown")] });
  assert.equal(unknown.evidence.length, 0);
  assert.equal(onlyStatus(unknown), "unknown_only");
});

test("typed entity participant layer fails closed on missing syntax and fingerprint drift", () => {
  const noSyntax = bundle({ entities: [entity("organization")] });
  delete noSyntax.syntaxTokens;
  assert.throws(
    () => collectTypedEntityEventParticipantEvidence({
      normalizedInputFingerprint: fingerprint,
      identity: identity(),
      literaryEvidence: noSyntax,
      eventPrediction: prediction(),
    }),
    /typed_entity_participant_syntax_missing/u,
  );

  const wrongIdentity = identity();
  wrongIdentity.normalizedInputFingerprint = "f".repeat(64);
  assert.throws(
    () => collect({ identity: wrongIdentity }),
    /typed_entity_participant_identity_fingerprint_mismatch/u,
  );
});
