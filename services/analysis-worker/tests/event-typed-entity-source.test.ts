import assert from "node:assert/strict";
import test from "node:test";

import { sha256Hex } from "../src/ingestion/hash.js";
import type { NormalizedSection } from "../src/ingestion/types.js";
import type { CharacterIdentityResult, ResolvedIdentityMention } from "../src/identity/types.js";
import {
  collectTypedEntityEventParticipantsFromSource,
} from "../src/evaluation/event-typed-entity-source.js";
import {
  eventPredictionFingerprint,
  type EventProviderResult,
} from "../src/evaluation/event-evaluation.js";
import type { LocalLiteraryEvidenceBundle } from "../src/local-analysis/types.js";
import {
  GLINER_RAW_ENTITY_SCHEMA,
  GLINER_TYPED_ENTITY_CONFIG,
  GLINER_TYPED_ENTITY_PROVIDER,
  normalizeGlinerEntityOutput,
} from "../src/local-analysis/typed-entity-evidence.js";

const text = "Alice moved Cairo.";
const fingerprint = sha256Hex(text);
const locator = "fixture:fixture:source";
const booknlpProvider = { name: "booknlp-small", model: "small", revision: "fixture" };
const eventProvider = { name: "saga_booknlp_dependency_grounded_event", model: "small", revision: "fixture" };
const section: NormalizedSection = {
  stable_key: "fixture",
  ordinal: 0,
  section_kind: "document",
  title: null,
  source_locator: "fixture:source",
  start_offset: 0,
  end_offset: Array.from(text).length,
  normalized_text: text,
};

function syntaxEvidence(): LocalLiteraryEvidenceBundle {
  return {
    provider: booknlpProvider,
    normalizedInputFingerprint: fingerprint,
    identityEvidence: { provider: booknlpProvider, normalizedInputFingerprint: fingerprint, mentions: [] },
    entities: [],
    quotes: [],
    eventTriggers: [{
      evidenceId: "trigger:move",
      surfaceText: "moved",
      lemma: "move",
      startOffset: 6,
      endOffset: 11,
      structuralLocator: locator,
      sentenceId: 0,
      tokenId: 1,
      dependencyRelation: "ROOT",
      syntacticHeadTokenId: 1,
    }],
    syntaxTokens: [
      {
        evidenceId: "syntax:moved",
        surfaceText: "moved",
        lemma: "move",
        startOffset: 6,
        endOffset: 11,
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
        evidenceId: "syntax:cairo",
        surfaceText: "Cairo",
        lemma: "Cairo",
        startOffset: 12,
        endOffset: 17,
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

function identity(mentions: ResolvedIdentityMention[] = []): CharacterIdentityResult {
  const keys = [...new Set(mentions.map((mention) => mention.characterKey).filter((value): value is string => value !== null))];
  return {
    resolverVersion: "fixture",
    resolverConfigFingerprint: "b".repeat(64),
    provider: booknlpProvider,
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

function eventPrediction(characterPatient: ResolvedIdentityMention | null = null): EventProviderResult {
  const participants = characterPatient === null ? [] : [{
    characterKey: characterPatient.characterKey!,
    role: "patient" as const,
    evidenceId: characterPatient.evidenceId,
  }];
  const events = [{
    eventId: "event:move",
    sectionKey: "fixture",
    startOffset: 6,
    endOffset: 11,
    participants,
    decisionReason: "fixture",
  }];
  const semantic = { provider: eventProvider, normalizedInputFingerprint: fingerprint, events };
  return {
    schemaVersion: "saga-event-prediction-v1",
    ...semantic,
    outputFingerprint: eventPredictionFingerprint(semantic),
  };
}

function glinerSource(label = "location") {
  return normalizeGlinerEntityOutput({
    normalizedText: text,
    normalizedInputFingerprint: fingerprint,
    sections: [section],
    raw: {
      schemaVersion: GLINER_RAW_ENTITY_SCHEMA,
      configuration: GLINER_TYPED_ENTITY_CONFIG,
      normalizedInputFingerprint: fingerprint,
      detections: [{
        startOffset: 12,
        endOffset: 17,
        surfaceText: "Cairo",
        label,
        score: 0.9,
      }],
    },
  });
}

test("external typed entity composition keeps GLiNER and event-provider provenance separate", () => {
  const result = collectTypedEntityEventParticipantsFromSource({
    normalizedInputFingerprint: fingerprint,
    identity: identity(),
    syntaxAndEventEvidence: syntaxEvidence(),
    entityEvidenceSource: glinerSource(),
    eventPrediction: eventPrediction(),
  });

  assert.deepEqual(result.provider, GLINER_TYPED_ENTITY_PROVIDER);
  assert.deepEqual(result.sourceEventProvider, eventProvider);
  assert.equal(result.evidence.length, 1);
  assert.equal(result.evidence[0]!.entityCategory, "location");
  assert.equal(result.evidence[0]!.role, "patient");
  assert.equal(result.candidates[0]!.status, "typed_non_person");
});

test("canonical character participant still wins over external GLiNER non-person evidence", () => {
  const mention: ResolvedIdentityMention = {
    evidenceId: "identity:cairo-character",
    characterKey: "cairo-character",
    surfaceText: "Cairo",
    startOffset: 12,
    endOffset: 17,
    structuralLocator: locator,
    mentionKind: "proper_name",
    resolutionState: "linked",
    evidenceTier: "canonical_seed",
    decisionReason: "fixture",
  };
  const result = collectTypedEntityEventParticipantsFromSource({
    normalizedInputFingerprint: fingerprint,
    identity: identity([mention]),
    syntaxAndEventEvidence: syntaxEvidence(),
    entityEvidenceSource: glinerSource(),
    eventPrediction: eventPrediction(mention),
  });

  assert.equal(result.evidence.length, 0);
  assert.equal(result.candidates[0]!.status, "character_grounded");
});

test("external typed entity composition fails closed on entity-source fingerprint drift", () => {
  const source = glinerSource();
  source.normalizedInputFingerprint = "f".repeat(64);
  assert.throws(
    () => collectTypedEntityEventParticipantsFromSource({
      normalizedInputFingerprint: fingerprint,
      identity: identity(),
      syntaxAndEventEvidence: syntaxEvidence(),
      entityEvidenceSource: source,
      eventPrediction: eventPrediction(),
    }),
    /typed_entity_output_fingerprint_mismatch|external_typed_entity_input_fingerprint_mismatch/u,
  );
});
