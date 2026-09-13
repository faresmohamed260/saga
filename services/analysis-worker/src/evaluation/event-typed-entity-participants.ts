import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import type { CharacterIdentityResult, ResolvedIdentityMention } from "../identity/types.js";
import type {
  LiteraryEntityCategory,
  LiteraryEntityEvidence,
  LocalLiteraryEvidenceBundle,
  SyntaxTokenEvidence,
} from "../local-analysis/types.js";
import {
  validateEventProviderResult,
  type EventPrediction,
  type EventProviderDescriptor,
  type EventProviderResult,
} from "./event-evaluation.js";

export const TYPED_ENTITY_EVENT_PARTICIPANT_VERSION = "saga-event-typed-entity-participant-evidence-v1";

const ACTIVE_SUBJECT = "nsubj";
const DIRECT_OBJECT = "dobj";
const PASSIVE_SUBJECT = "nsubjpass";
const PASSIVE_AGENT = "agent";
const PREPOSITION_OBJECT = "pobj";

const TYPED_NON_PERSON_CATEGORIES = [
  "location",
  "facility",
  "geopolitical",
  "organization",
  "vehicle",
] as const satisfies readonly LiteraryEntityCategory[];

export type TypedEntityParticipantRole = "actor" | "patient";
export type TypedNonPersonEntityCategory = typeof TYPED_NON_PERSON_CATEGORIES[number];

export type TypedEntityParticipantCandidateStatus =
  | "character_grounded"
  | "typed_non_person"
  | "ambiguous_non_person"
  | "malformed_non_person"
  | "structural_locator_mismatch"
  | "person_only"
  | "unknown_only"
  | "no_entity_evidence";

export type TypedEntityEventParticipantEvidence = {
  evidenceId: string;
  eventId: string;
  triggerEvidenceId: string;
  role: TypedEntityParticipantRole;
  dependencyPath: string;
  syntaxTokenId: number;
  startOffset: number;
  endOffset: number;
  structuralLocator: string | null;
  entityEvidenceId: string;
  entityCategory: TypedNonPersonEntityCategory;
  entityStartOffset: number;
  entityEndOffset: number;
};

export type TypedEntityParticipantCandidate = {
  candidateId: string;
  eventId: string;
  triggerEvidenceId: string;
  role: TypedEntityParticipantRole;
  dependencyPath: string;
  syntaxTokenId: number;
  startOffset: number;
  endOffset: number;
  structuralLocator: string | null;
  status: TypedEntityParticipantCandidateStatus;
  entityEvidenceIds: string[];
  entityCategories: LiteraryEntityCategory[];
};

export type TypedEntityEventParticipantResult = {
  schemaVersion: "saga-event-typed-entity-participant-evidence-v1";
  provider: LocalLiteraryEvidenceBundle["provider"];
  sourceEventProvider: EventProviderDescriptor;
  normalizedInputFingerprint: string;
  configurationFingerprint: string;
  evidence: TypedEntityEventParticipantEvidence[];
  candidates: TypedEntityParticipantCandidate[];
  outputFingerprint: string;
};

type CandidateInput = {
  token: SyntaxTokenEvidence;
  role: TypedEntityParticipantRole;
  dependencyPath: string;
};

function covers(span: { startOffset: number; endOffset: number }, token: SyntaxTokenEvidence) {
  return span.startOffset <= token.startOffset && span.endOffset >= token.endOffset;
}

function identityLocatorCompatible(mention: ResolvedIdentityMention, token: SyntaxTokenEvidence) {
  if (mention.structuralLocator === null || token.structuralLocator === null) return true;
  return mention.structuralLocator === token.structuralLocator;
}

function exactEntityLocator(entity: LiteraryEntityEvidence, token: SyntaxTokenEvidence) {
  return entity.structuralLocator === token.structuralLocator;
}

function isTypedNonPersonCategory(category: LiteraryEntityCategory): category is TypedNonPersonEntityCategory {
  return (TYPED_NON_PERSON_CATEGORIES as readonly LiteraryEntityCategory[]).includes(category);
}

function syntaxIndex(tokens: SyntaxTokenEvidence[]) {
  const byId = new Map<number, SyntaxTokenEvidence>();
  const children = new Map<number, SyntaxTokenEvidence[]>();
  for (const token of tokens) {
    if (byId.has(token.tokenId)) throw new Error(`typed_entity_participant_duplicate_syntax_token:${token.tokenId}`);
    byId.set(token.tokenId, token);
  }
  for (const token of tokens) {
    const head = byId.get(token.syntacticHeadTokenId);
    if (!head) throw new Error(`typed_entity_participant_missing_syntax_head:${token.evidenceId}`);
    if (head.sentenceId !== token.sentenceId) {
      throw new Error(`typed_entity_participant_cross_sentence_syntax_head:${token.evidenceId}`);
    }
    if (token.tokenId === token.syntacticHeadTokenId) continue;
    const current = children.get(token.syntacticHeadTokenId) ?? [];
    current.push(token);
    children.set(token.syntacticHeadTokenId, current);
  }
  for (const group of children.values()) group.sort((left, right) => left.tokenId - right.tokenId);
  return { byId, children };
}

function sameTriggerAndSyntax(
  trigger: LocalLiteraryEvidenceBundle["eventTriggers"][number],
  token: SyntaxTokenEvidence,
) {
  return trigger.tokenId === token.tokenId
    && trigger.surfaceText === token.surfaceText
    && trigger.lemma === token.lemma
    && trigger.startOffset === token.startOffset
    && trigger.endOffset === token.endOffset
    && trigger.sentenceId === token.sentenceId
    && trigger.dependencyRelation === token.dependencyRelation
    && trigger.syntacticHeadTokenId === token.syntacticHeadTokenId;
}

function spanKey(value: { startOffset: number; endOffset: number }) {
  return `${value.startOffset}:${value.endOffset}`;
}

function eventByTriggerSpan(prediction: EventProviderResult) {
  const bySpan = new Map<string, EventPrediction>();
  for (const event of prediction.events) {
    const key = spanKey(event);
    if (bySpan.has(key)) throw new Error(`typed_entity_participant_duplicate_event_span:${key}`);
    bySpan.set(key, event);
  }
  return bySpan;
}

function directChildren(
  children: Map<number, SyntaxTokenEvidence[]>,
  tokenId: number,
  relation: string,
) {
  return (children.get(tokenId) ?? []).filter((token) => token.dependencyRelation === relation);
}

function candidatesForTrigger(
  triggerToken: SyntaxTokenEvidence,
  children: Map<number, SyntaxTokenEvidence[]>,
) {
  const candidates: CandidateInput[] = [];
  for (const token of directChildren(children, triggerToken.tokenId, ACTIVE_SUBJECT)) {
    candidates.push({ token, role: "actor", dependencyPath: ACTIVE_SUBJECT });
  }
  for (const agent of directChildren(children, triggerToken.tokenId, PASSIVE_AGENT)) {
    for (const token of directChildren(children, agent.tokenId, PREPOSITION_OBJECT)) {
      candidates.push({ token, role: "actor", dependencyPath: `${PASSIVE_AGENT}->${PREPOSITION_OBJECT}` });
    }
  }
  for (const token of directChildren(children, triggerToken.tokenId, DIRECT_OBJECT)) {
    candidates.push({ token, role: "patient", dependencyPath: DIRECT_OBJECT });
  }
  for (const token of directChildren(children, triggerToken.tokenId, PASSIVE_SUBJECT)) {
    candidates.push({ token, role: "patient", dependencyPath: PASSIVE_SUBJECT });
  }
  candidates.sort((left, right) =>
    left.token.tokenId - right.token.tokenId
    || left.role.localeCompare(right.role)
    || left.dependencyPath.localeCompare(right.dependencyPath)
  );
  return candidates;
}

function candidateAlreadyCharacterGrounded(input: {
  candidate: CandidateInput;
  event: EventPrediction;
  identity: CharacterIdentityResult;
}) {
  const participants = input.event.participants.filter((participant) => participant.role === input.candidate.role);
  if (participants.length === 0) return false;

  const identityByEvidence = new Map(input.identity.mentions.map((mention) => [mention.evidenceId, mention]));
  for (const participant of participants) {
    if (!participant.evidenceId) continue;
    const mention = identityByEvidence.get(participant.evidenceId);
    if (
      mention
      && mention.resolutionState === "linked"
      && mention.characterKey === participant.characterKey
      && covers(mention, input.candidate.token)
      && identityLocatorCompatible(mention, input.candidate.token)
    ) return true;
  }

  const covering = input.identity.mentions
    .filter((mention) => mention.resolutionState === "linked" && mention.characterKey !== null)
    .filter((mention) => covers(mention, input.candidate.token))
    .filter((mention) => identityLocatorCompatible(mention, input.candidate.token));
  const characterKeys = [...new Set(covering.map((mention) => mention.characterKey!))];
  return characterKeys.length === 1
    && participants.some((participant) => participant.characterKey === characterKeys[0]);
}

function entitySummary(entities: LiteraryEntityEvidence[]) {
  return {
    entityEvidenceIds: entities.map((entity) => entity.evidenceId).sort(),
    entityCategories: [...new Set(entities.map((entity) => entity.category))].sort(),
  };
}

function classifyCandidate(input: {
  candidate: CandidateInput;
  event: EventPrediction;
  identity: CharacterIdentityResult;
  entities: LiteraryEntityEvidence[];
}) {
  if (candidateAlreadyCharacterGrounded(input)) {
    return { status: "character_grounded" as const, matched: null, related: [] as LiteraryEntityEvidence[] };
  }

  const covering = input.entities.filter((entity) => covers(entity, input.candidate.token));
  const typedNonPerson = covering.filter((entity) => isTypedNonPersonCategory(entity.category));
  const matchingTyped = typedNonPerson.filter((entity) => exactEntityLocator(entity, input.candidate.token));
  const cleanMatchingTyped = matchingTyped.filter((entity) => entity.boundaryQuality === "clean");

  if (cleanMatchingTyped.length === 1) {
    return { status: "typed_non_person" as const, matched: cleanMatchingTyped[0]!, related: cleanMatchingTyped };
  }
  if (cleanMatchingTyped.length > 1) {
    return { status: "ambiguous_non_person" as const, matched: null, related: cleanMatchingTyped };
  }
  if (matchingTyped.some((entity) => entity.boundaryQuality === "malformed")) {
    return { status: "malformed_non_person" as const, matched: null, related: matchingTyped };
  }
  if (typedNonPerson.length > 0) {
    return { status: "structural_locator_mismatch" as const, matched: null, related: typedNonPerson };
  }

  const matchingPerson = covering.filter(
    (entity) => entity.category === "person" && exactEntityLocator(entity, input.candidate.token),
  );
  if (matchingPerson.length > 0) {
    return { status: "person_only" as const, matched: null, related: matchingPerson };
  }
  const matchingUnknown = covering.filter(
    (entity) => entity.category === "unknown" && exactEntityLocator(entity, input.candidate.token),
  );
  if (matchingUnknown.length > 0) {
    return { status: "unknown_only" as const, matched: null, related: matchingUnknown };
  }
  return { status: "no_entity_evidence" as const, matched: null, related: [] as LiteraryEntityEvidence[] };
}

export function typedEntityParticipantFingerprint(input: Omit<TypedEntityEventParticipantResult, "outputFingerprint">) {
  return sha256Hex(canonicalJson(input));
}

export function collectTypedEntityEventParticipantEvidence(input: {
  normalizedInputFingerprint: string;
  identity: CharacterIdentityResult;
  literaryEvidence: LocalLiteraryEvidenceBundle;
  eventPrediction: EventProviderResult;
}): TypedEntityEventParticipantResult {
  if (!/^[0-9a-f]{64}$/u.test(input.normalizedInputFingerprint)) {
    throw new Error("invalid_typed_entity_participant_input_fingerprint");
  }
  if (input.identity.normalizedInputFingerprint !== input.normalizedInputFingerprint) {
    throw new Error("typed_entity_participant_identity_fingerprint_mismatch");
  }
  if (input.literaryEvidence.normalizedInputFingerprint !== input.normalizedInputFingerprint) {
    throw new Error("typed_entity_participant_provider_fingerprint_mismatch");
  }
  if (input.eventPrediction.normalizedInputFingerprint !== input.normalizedInputFingerprint) {
    throw new Error("typed_entity_participant_event_fingerprint_mismatch");
  }
  if (!input.literaryEvidence.syntaxTokens) {
    throw new Error("typed_entity_participant_syntax_missing");
  }
  validateEventProviderResult(input.eventPrediction);

  const syntax = syntaxIndex(input.literaryEvidence.syntaxTokens);
  const predictionBySpan = eventByTriggerSpan(input.eventPrediction);
  const candidates: TypedEntityParticipantCandidate[] = [];
  const evidence: TypedEntityEventParticipantEvidence[] = [];

  for (const trigger of input.literaryEvidence.eventTriggers) {
    const triggerToken = syntax.byId.get(trigger.tokenId);
    if (!triggerToken) throw new Error(`typed_entity_participant_trigger_token_missing:${trigger.evidenceId}`);
    if (!sameTriggerAndSyntax(trigger, triggerToken)) {
      throw new Error(`typed_entity_participant_trigger_syntax_mismatch:${trigger.evidenceId}`);
    }
    const event = predictionBySpan.get(spanKey(trigger));
    if (!event) throw new Error(`typed_entity_participant_event_missing:${trigger.evidenceId}`);

    for (const candidate of candidatesForTrigger(triggerToken, syntax.children)) {
      const candidateId = `entity-participant-candidate-${sha256Hex(
        `${event.eventId}:${candidate.role}:${candidate.dependencyPath}:${candidate.token.tokenId}`,
      ).slice(0, 20)}`;
      const classification = classifyCandidate({
        candidate,
        event,
        identity: input.identity,
        entities: input.literaryEvidence.entities,
      });
      const related = entitySummary(classification.related);
      candidates.push({
        candidateId,
        eventId: event.eventId,
        triggerEvidenceId: trigger.evidenceId,
        role: candidate.role,
        dependencyPath: candidate.dependencyPath,
        syntaxTokenId: candidate.token.tokenId,
        startOffset: candidate.token.startOffset,
        endOffset: candidate.token.endOffset,
        structuralLocator: candidate.token.structuralLocator,
        status: classification.status,
        ...related,
      });
      if (!classification.matched || !isTypedNonPersonCategory(classification.matched.category)) continue;
      evidence.push({
        evidenceId: `entity-participant-${sha256Hex(`${candidateId}:${classification.matched.evidenceId}`).slice(0, 20)}`,
        eventId: event.eventId,
        triggerEvidenceId: trigger.evidenceId,
        role: candidate.role,
        dependencyPath: candidate.dependencyPath,
        syntaxTokenId: candidate.token.tokenId,
        startOffset: candidate.token.startOffset,
        endOffset: candidate.token.endOffset,
        structuralLocator: candidate.token.structuralLocator,
        entityEvidenceId: classification.matched.evidenceId,
        entityCategory: classification.matched.category,
        entityStartOffset: classification.matched.startOffset,
        entityEndOffset: classification.matched.endOffset,
      });
    }
  }

  candidates.sort((left, right) =>
    left.startOffset - right.startOffset
    || left.endOffset - right.endOffset
    || left.role.localeCompare(right.role)
    || left.candidateId.localeCompare(right.candidateId)
  );
  evidence.sort((left, right) =>
    left.startOffset - right.startOffset
    || left.endOffset - right.endOffset
    || left.role.localeCompare(right.role)
    || left.evidenceId.localeCompare(right.evidenceId)
  );

  const configurationFingerprint = sha256Hex(canonicalJson({
    version: TYPED_ENTITY_EVENT_PARTICIPANT_VERSION,
    actorRelations: [ACTIVE_SUBJECT, `${PASSIVE_AGENT}->${PREPOSITION_OBJECT}`],
    patientRelations: [DIRECT_OBJECT, PASSIVE_SUBJECT],
    typedNonPersonCategories: TYPED_NON_PERSON_CATEGORIES,
    characterParticipantsExcluded: true,
    entityBoundaryQuality: "clean_only",
    structuralLocatorPolicy: "exact",
    ambiguityPolicy: "unresolved",
    providerClustersCanonical: false,
    dativeGrounding: false,
    conjunctionInheritance: false,
    evidenceProvider: input.literaryEvidence.provider,
    sourceEventProvider: input.eventPrediction.provider,
  }));
  const semantic = {
    schemaVersion: TYPED_ENTITY_EVENT_PARTICIPANT_VERSION,
    provider: input.literaryEvidence.provider,
    sourceEventProvider: input.eventPrediction.provider,
    normalizedInputFingerprint: input.normalizedInputFingerprint,
    configurationFingerprint,
    evidence,
    candidates,
  } satisfies Omit<TypedEntityEventParticipantResult, "outputFingerprint">;
  return { ...semantic, outputFingerprint: typedEntityParticipantFingerprint(semantic) };
}
