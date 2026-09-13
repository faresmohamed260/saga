import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import type { CharacterIdentityResult } from "../identity/types.js";
import type { LocalLiteraryEvidenceBundle } from "../local-analysis/types.js";
import {
  validateTypedEntityEvidenceSource,
  type TypedEntityEvidenceSource,
} from "../local-analysis/typed-entity-evidence.js";
import type { EventProviderResult } from "./event-evaluation.js";
import {
  collectTypedEntityEventParticipantEvidence,
  typedEntityParticipantFingerprint,
  type TypedEntityEventParticipantResult,
} from "./event-typed-entity-participants.js";

export const EXTERNAL_TYPED_ENTITY_EVENT_COMPOSITION_VERSION =
  "saga-event-external-typed-entity-composition-v1";

export function collectTypedEntityEventParticipantsFromSource(input: {
  normalizedInputFingerprint: string;
  identity: CharacterIdentityResult;
  syntaxAndEventEvidence: LocalLiteraryEvidenceBundle;
  entityEvidenceSource: TypedEntityEvidenceSource;
  eventPrediction: EventProviderResult;
}): TypedEntityEventParticipantResult {
  validateTypedEntityEvidenceSource(input.entityEvidenceSource);
  if (input.entityEvidenceSource.normalizedInputFingerprint !== input.normalizedInputFingerprint) {
    throw new Error("external_typed_entity_input_fingerprint_mismatch");
  }
  if (input.syntaxAndEventEvidence.normalizedInputFingerprint !== input.normalizedInputFingerprint) {
    throw new Error("external_typed_entity_syntax_input_fingerprint_mismatch");
  }

  const composedEvidence: LocalLiteraryEvidenceBundle = {
    ...input.syntaxAndEventEvidence,
    provider: input.entityEvidenceSource.provider,
    entities: input.entityEvidenceSource.entities,
  };
  const base = collectTypedEntityEventParticipantEvidence({
    normalizedInputFingerprint: input.normalizedInputFingerprint,
    identity: input.identity,
    literaryEvidence: composedEvidence,
    eventPrediction: input.eventPrediction,
  });

  const configurationFingerprint = sha256Hex(canonicalJson({
    version: EXTERNAL_TYPED_ENTITY_EVENT_COMPOSITION_VERSION,
    baseConfigurationFingerprint: base.configurationFingerprint,
    entityEvidenceProvider: input.entityEvidenceSource.provider,
    entityEvidenceConfigurationFingerprint: input.entityEvidenceSource.configurationFingerprint,
    entityEvidenceOutputFingerprint: input.entityEvidenceSource.outputFingerprint,
    syntaxAndEventEvidenceProvider: input.syntaxAndEventEvidence.provider,
    sourceEventProvider: input.eventPrediction.provider,
  }));
  const semantic = {
    schemaVersion: base.schemaVersion,
    provider: input.entityEvidenceSource.provider,
    sourceEventProvider: base.sourceEventProvider,
    normalizedInputFingerprint: base.normalizedInputFingerprint,
    configurationFingerprint,
    evidence: base.evidence,
    candidates: base.candidates,
  } satisfies Omit<TypedEntityEventParticipantResult, "outputFingerprint">;
  return { ...semantic, outputFingerprint: typedEntityParticipantFingerprint(semantic) };
}
