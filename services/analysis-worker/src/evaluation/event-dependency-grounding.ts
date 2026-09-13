import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import type { NormalizedSection } from "../ingestion/types.js";
import type { CharacterIdentityResult, ResolvedIdentityMention } from "../identity/types.js";
import type {
  EventTriggerEvidence,
  LocalLiteraryEvidenceBundle,
  SyntaxTokenEvidence,
} from "../local-analysis/types.js";
import {
  eventPredictionFingerprint,
  type EventParticipantPrediction,
  type EventParticipantRole,
  type EventProviderResult,
  type EventPrediction,
} from "./event-evaluation.js";

export const DEPENDENCY_EVENT_GROUNDING_VERSION = "saga-event-dependency-grounding-v1";

const ACTIVE_SUBJECT = "nsubj";
const DIRECT_OBJECT = "dobj";
const PASSIVE_SUBJECT = "nsubjpass";
const PASSIVE_AGENT = "agent";
const PREPOSITION_OBJECT = "pobj";

type GroundedMention = {
  characterKey: string;
  evidenceId: string;
};

function containingSection(
  sections: NormalizedSection[],
  startOffset: number,
  endOffset: number,
) {
  const matches = sections.filter(
    (section) => startOffset >= section.start_offset && endOffset <= section.end_offset,
  );
  if (matches.length !== 1) return null;
  return matches[0]!;
}

function syntaxIndex(tokens: SyntaxTokenEvidence[]) {
  const byId = new Map<number, SyntaxTokenEvidence>();
  const children = new Map<number, SyntaxTokenEvidence[]>();
  for (const token of tokens) {
    if (byId.has(token.tokenId)) throw new Error(`event_dependency_duplicate_syntax_token:${token.tokenId}`);
    byId.set(token.tokenId, token);
  }
  for (const token of tokens) {
    const head = byId.get(token.syntacticHeadTokenId);
    if (!head) throw new Error(`event_dependency_missing_syntax_head:${token.evidenceId}`);
    if (head.sentenceId !== token.sentenceId) {
      throw new Error(`event_dependency_cross_sentence_syntax_head:${token.evidenceId}`);
    }
    if (token.tokenId === token.syntacticHeadTokenId) continue;
    const current = children.get(token.syntacticHeadTokenId) ?? [];
    current.push(token);
    children.set(token.syntacticHeadTokenId, current);
  }
  for (const group of children.values()) {
    group.sort((left, right) => left.tokenId - right.tokenId);
  }
  return { byId, children };
}

function sameTriggerAndSyntax(trigger: EventTriggerEvidence, token: SyntaxTokenEvidence) {
  return trigger.tokenId === token.tokenId
    && trigger.surfaceText === token.surfaceText
    && trigger.lemma === token.lemma
    && trigger.startOffset === token.startOffset
    && trigger.endOffset === token.endOffset
    && trigger.sentenceId === token.sentenceId
    && trigger.dependencyRelation === token.dependencyRelation
    && trigger.syntacticHeadTokenId === token.syntacticHeadTokenId;
}

function eligibleMention(mention: ResolvedIdentityMention) {
  return mention.resolutionState === "linked" && mention.characterKey !== null;
}

function groundTokenToIdentity(
  token: SyntaxTokenEvidence,
  identity: CharacterIdentityResult,
): GroundedMention | null {
  const covering = identity.mentions
    .filter(eligibleMention)
    .filter((mention) => mention.startOffset <= token.startOffset && mention.endOffset >= token.endOffset)
    .filter((mention) => {
      if (mention.structuralLocator === null || token.structuralLocator === null) return true;
      return mention.structuralLocator === token.structuralLocator;
    });

  const characterKeys = [...new Set(covering.map((mention) => mention.characterKey!))];
  if (characterKeys.length !== 1) return null;
  const characterKey = characterKeys[0]!;
  const evidence = covering
    .filter((mention) => mention.characterKey === characterKey)
    .sort((left, right) => {
      const leftWidth = left.endOffset - left.startOffset;
      const rightWidth = right.endOffset - right.startOffset;
      return leftWidth - rightWidth
        || left.startOffset - right.startOffset
        || left.evidenceId.localeCompare(right.evidenceId);
    })[0];
  if (!evidence) return null;
  return { characterKey, evidenceId: evidence.evidenceId };
}

function participantFromToken(
  token: SyntaxTokenEvidence,
  role: EventParticipantRole,
  identity: CharacterIdentityResult,
): EventParticipantPrediction | null {
  const grounded = groundTokenToIdentity(token, identity);
  if (!grounded) return null;
  return {
    characterKey: grounded.characterKey,
    role,
    evidenceId: grounded.evidenceId,
  };
}

function addParticipant(
  target: EventParticipantPrediction[],
  participant: EventParticipantPrediction | null,
) {
  if (!participant) return;
  if (target.some((existing) =>
    existing.characterKey === participant.characterKey && existing.role === participant.role
  )) return;
  target.push(participant);
}

function directChildren(
  children: Map<number, SyntaxTokenEvidence[]>,
  tokenId: number,
  relation: string,
) {
  return (children.get(tokenId) ?? []).filter((token) => token.dependencyRelation === relation);
}

function participantsForTrigger(input: {
  trigger: EventTriggerEvidence;
  syntaxToken: SyntaxTokenEvidence;
  children: Map<number, SyntaxTokenEvidence[]>;
  identity: CharacterIdentityResult;
}) {
  const participants: EventParticipantPrediction[] = [];

  for (const subject of directChildren(input.children, input.syntaxToken.tokenId, ACTIVE_SUBJECT)) {
    addParticipant(participants, participantFromToken(subject, "actor", input.identity));
  }
  for (const object of directChildren(input.children, input.syntaxToken.tokenId, DIRECT_OBJECT)) {
    addParticipant(participants, participantFromToken(object, "patient", input.identity));
  }
  for (const passiveSubject of directChildren(input.children, input.syntaxToken.tokenId, PASSIVE_SUBJECT)) {
    addParticipant(participants, participantFromToken(passiveSubject, "patient", input.identity));
  }
  for (const agent of directChildren(input.children, input.syntaxToken.tokenId, PASSIVE_AGENT)) {
    for (const object of directChildren(input.children, agent.tokenId, PREPOSITION_OBJECT)) {
      addParticipant(participants, participantFromToken(object, "actor", input.identity));
    }
  }

  participants.sort((left, right) =>
    left.role.localeCompare(right.role)
    || left.characterKey.localeCompare(right.characterKey)
    || (left.evidenceId ?? "").localeCompare(right.evidenceId ?? "")
  );
  return participants;
}

export function predictDependencyGroundedEvents(input: {
  sections: NormalizedSection[];
  normalizedInputFingerprint: string;
  identity: CharacterIdentityResult;
  literaryEvidence: LocalLiteraryEvidenceBundle;
}): EventProviderResult {
  if (!/^[0-9a-f]{64}$/u.test(input.normalizedInputFingerprint)) {
    throw new Error("invalid_event_dependency_input_fingerprint");
  }
  if (input.identity.normalizedInputFingerprint !== input.normalizedInputFingerprint) {
    throw new Error("event_dependency_identity_input_fingerprint_mismatch");
  }
  if (input.literaryEvidence.normalizedInputFingerprint !== input.normalizedInputFingerprint) {
    throw new Error("event_dependency_provider_input_fingerprint_mismatch");
  }
  if (!input.literaryEvidence.syntaxTokens) {
    throw new Error("event_dependency_syntax_evidence_missing");
  }

  const syntax = syntaxIndex(input.literaryEvidence.syntaxTokens);
  const events: EventPrediction[] = input.literaryEvidence.eventTriggers.map((trigger) => {
    const token = syntax.byId.get(trigger.tokenId);
    if (!token) throw new Error(`event_dependency_trigger_token_missing:${trigger.evidenceId}`);
    if (!sameTriggerAndSyntax(trigger, token)) {
      throw new Error(`event_dependency_trigger_syntax_mismatch:${trigger.evidenceId}`);
    }
    const section = containingSection(input.sections, trigger.startOffset, trigger.endOffset);
    if (!section) throw new Error(`event_dependency_trigger_section_ambiguous:${trigger.evidenceId}`);
    const participants = participantsForTrigger({
      trigger,
      syntaxToken: token,
      children: syntax.children,
      identity: input.identity,
    });
    const actorCount = participants.filter((participant) => participant.role === "actor").length;
    const patientCount = participants.filter((participant) => participant.role === "patient").length;
    return {
      eventId: `event-${sha256Hex(`${section.stable_key}:${trigger.startOffset}:${trigger.endOffset}:${trigger.lemma}`).slice(0, 20)}`,
      sectionKey: section.stable_key,
      startOffset: trigger.startOffset,
      endOffset: trigger.endOffset,
      participants,
      decisionReason: `booknlp_dependency_direct:v1:actor=${actorCount}:patient=${patientCount}`,
    };
  }).sort((left, right) =>
    left.startOffset - right.startOffset
    || left.endOffset - right.endOffset
    || left.eventId.localeCompare(right.eventId)
  );

  const configurationFingerprint = sha256Hex(canonicalJson({
    version: DEPENDENCY_EVENT_GROUNDING_VERSION,
    triggerProvider: input.literaryEvidence.provider,
    actorRelations: [ACTIVE_SUBJECT, `${PASSIVE_AGENT}->${PREPOSITION_OBJECT}`],
    patientRelations: [DIRECT_OBJECT, PASSIVE_SUBJECT],
    identityGrounding: "unique_character_covering_syntax_token",
    conjunctionInheritance: false,
    dativeGrounding: false,
    providerClustersCanonical: false,
  }));
  const provider = {
    name: "saga_booknlp_dependency_grounded_event",
    model: input.literaryEvidence.provider.model,
    revision: `${DEPENDENCY_EVENT_GROUNDING_VERSION}:${configurationFingerprint.slice(0, 16)}`,
  };
  return {
    schemaVersion: "saga-event-prediction-v1",
    provider,
    normalizedInputFingerprint: input.normalizedInputFingerprint,
    events,
    outputFingerprint: eventPredictionFingerprint({
      provider,
      normalizedInputFingerprint: input.normalizedInputFingerprint,
      events,
    }),
  };
}
