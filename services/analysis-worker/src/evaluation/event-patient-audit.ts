import type { CharacterIdentityResult, ResolvedIdentityMention } from "../identity/types.js";
import type { EventProviderResult } from "./event-evaluation.js";
import type { GoldIdentityDocument } from "./types.js";
import type {
  LiteraryEntityCategory,
  LocalLiteraryEvidenceBundle,
  SyntaxTokenEvidence,
} from "../local-analysis/types.js";

export type PatientAuditCategory =
  | "grounded_character"
  | "linked_character_not_grounded"
  | "ambiguous_linked_character"
  | "structural_locator_mismatch"
  | "gold_linked_person_missing_identity"
  | "unresolved_person_gold"
  | "non_person_gold"
  | "provider_non_person"
  | "provider_person_only"
  | "no_entity_evidence";

export type PatientAuditCounts = {
  candidateTokenCount: number;
  byRelation: Record<string, number>;
  byCategory: Record<PatientAuditCategory, number>;
  byRelationAndCategory: Record<string, Record<PatientAuditCategory, number>>;
  providerNonPersonCategories: Partial<Record<LiteraryEntityCategory, number>>;
};

export type PatientAuditResult = PatientAuditCounts & {
  eventWithPatientCandidateCount: number;
  eventWithMultiplePatientCandidatesCount: number;
};

const PATIENT_RELATIONS = new Set(["dobj", "nsubjpass"]);

function spanKey(startOffset: number, endOffset: number) {
  return `${startOffset}:${endOffset}`;
}

function covers(span: { startOffset: number; endOffset: number }, token: SyntaxTokenEvidence) {
  return span.startOffset <= token.startOffset && span.endOffset >= token.endOffset;
}

function sameLocator(mention: ResolvedIdentityMention, token: SyntaxTokenEvidence) {
  return mention.structuralLocator === token.structuralLocator;
}

function emptyCategories(): Record<PatientAuditCategory, number> {
  return {
    grounded_character: 0,
    linked_character_not_grounded: 0,
    ambiguous_linked_character: 0,
    structural_locator_mismatch: 0,
    gold_linked_person_missing_identity: 0,
    unresolved_person_gold: 0,
    non_person_gold: 0,
    provider_non_person: 0,
    provider_person_only: 0,
    no_entity_evidence: 0,
  };
}

function classifyCandidate(input: {
  candidate: SyntaxTokenEvidence;
  patientEvidence: ResolvedIdentityMention[];
  identity: CharacterIdentityResult;
  gold: GoldIdentityDocument;
  evidence: LocalLiteraryEvidenceBundle;
  providerNonPersonCategories: Partial<Record<LiteraryEntityCategory, number>>;
}): PatientAuditCategory {
  if (input.patientEvidence.some((mention) => covers(mention, input.candidate) && sameLocator(mention, input.candidate))) {
    return "grounded_character";
  }

  const linkedCovering = input.identity.mentions.filter((mention) =>
    mention.resolutionState === "linked" && Boolean(mention.characterKey) && covers(mention, input.candidate)
  );
  const linkedMatchingLocator = linkedCovering.filter((mention) => sameLocator(mention, input.candidate));
  const characterKeys = new Set(linkedMatchingLocator.map((mention) => mention.characterKey!));
  if (characterKeys.size === 1) return "linked_character_not_grounded";
  if (characterKeys.size > 1) return "ambiguous_linked_character";
  if (linkedCovering.length > 0) return "structural_locator_mismatch";

  const goldCovering = input.gold.mentions.filter((mention) => covers(mention, input.candidate));
  const goldPerson = goldCovering.filter((mention) => mention.entityType === "person");
  if (goldPerson.some((mention) => Boolean(mention.goldCharacterId))) return "gold_linked_person_missing_identity";
  if (goldPerson.length > 0) return "unresolved_person_gold";
  if (goldCovering.some((mention) => mention.entityType === "non_person")) return "non_person_gold";

  const providerCovering = input.evidence.entities.filter((entity) => covers(entity, input.candidate));
  const providerNonPerson = providerCovering.filter((entity) => entity.category !== "person");
  if (providerNonPerson.length > 0) {
    for (const entity of providerNonPerson) {
      input.providerNonPersonCategories[entity.category] =
        (input.providerNonPersonCategories[entity.category] ?? 0) + 1;
    }
    return "provider_non_person";
  }
  if (providerCovering.some((entity) => entity.category === "person")) return "provider_person_only";
  return "no_entity_evidence";
}

export function auditPatientGrounding(input: {
  evidence: LocalLiteraryEvidenceBundle;
  gold: GoldIdentityDocument;
  identity: CharacterIdentityResult;
  prediction: EventProviderResult;
}): PatientAuditResult {
  if (!input.evidence.syntaxTokens) throw new Error("patient_audit_missing_syntax");
  if (input.evidence.normalizedInputFingerprint !== input.identity.normalizedInputFingerprint) {
    throw new Error("patient_audit_identity_fingerprint_mismatch");
  }
  if (input.evidence.normalizedInputFingerprint !== input.prediction.normalizedInputFingerprint) {
    throw new Error("patient_audit_prediction_fingerprint_mismatch");
  }

  const syntaxById = new Map(input.evidence.syntaxTokens.map((token) => [token.tokenId, token]));
  const children = new Map<number, SyntaxTokenEvidence[]>();
  for (const token of input.evidence.syntaxTokens) {
    if (token.tokenId === token.syntacticHeadTokenId) continue;
    const current = children.get(token.syntacticHeadTokenId) ?? [];
    current.push(token);
    children.set(token.syntacticHeadTokenId, current);
  }

  const eventBySpan = new Map(input.prediction.events.map((event) => [spanKey(event.startOffset, event.endOffset), event]));
  const identityByEvidence = new Map(input.identity.mentions.map((mention) => [mention.evidenceId, mention]));
  const byRelation: Record<string, number> = {};
  const byCategory = emptyCategories();
  const byRelationAndCategory: Record<string, Record<PatientAuditCategory, number>> = {};
  const providerNonPersonCategories: Partial<Record<LiteraryEntityCategory, number>> = {};
  let candidateTokenCount = 0;
  let eventWithPatientCandidateCount = 0;
  let eventWithMultiplePatientCandidatesCount = 0;

  for (const trigger of input.evidence.eventTriggers) {
    const triggerToken = syntaxById.get(trigger.tokenId);
    if (!triggerToken) throw new Error(`patient_audit_missing_trigger_token:${trigger.evidenceId}`);
    const patientCandidates = (children.get(triggerToken.tokenId) ?? [])
      .filter((token) => PATIENT_RELATIONS.has(token.dependencyRelation));
    if (patientCandidates.length === 0) continue;
    eventWithPatientCandidateCount += 1;
    if (patientCandidates.length > 1) eventWithMultiplePatientCandidatesCount += 1;

    const event = eventBySpan.get(spanKey(trigger.startOffset, trigger.endOffset));
    if (!event) throw new Error(`patient_audit_missing_prediction_event:${trigger.evidenceId}`);
    const patientEvidence = event.participants
      .filter((participant) => participant.role === "patient" && participant.evidenceId)
      .map((participant) => identityByEvidence.get(participant.evidenceId!))
      .filter((mention): mention is ResolvedIdentityMention => Boolean(mention));

    for (const candidate of patientCandidates) {
      candidateTokenCount += 1;
      const relation = candidate.dependencyRelation;
      byRelation[relation] = (byRelation[relation] ?? 0) + 1;
      const category = classifyCandidate({
        candidate,
        patientEvidence,
        identity: input.identity,
        gold: input.gold,
        evidence: input.evidence,
        providerNonPersonCategories,
      });
      byCategory[category] += 1;
      const relationCategories = byRelationAndCategory[relation] ?? emptyCategories();
      relationCategories[category] += 1;
      byRelationAndCategory[relation] = relationCategories;
    }
  }

  const classified = Object.values(byCategory).reduce((sum, value) => sum + value, 0);
  if (classified !== candidateTokenCount) {
    throw new Error(`patient_audit_classification_mismatch:${classified}:${candidateTokenCount}`);
  }
  for (const [relation, count] of Object.entries(byRelation)) {
    const relationClassified = Object.values(byRelationAndCategory[relation] ?? {}).reduce((sum, value) => sum + value, 0);
    if (relationClassified !== count) {
      throw new Error(`patient_audit_relation_classification_mismatch:${relation}:${relationClassified}:${count}`);
    }
  }

  return {
    candidateTokenCount,
    eventWithPatientCandidateCount,
    eventWithMultiplePatientCandidatesCount,
    byRelation,
    byCategory,
    byRelationAndCategory,
    providerNonPersonCategories,
  };
}
