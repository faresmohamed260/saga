import type { CharacterIdentityResult, ResolvedIdentityMention } from "../identity/types.js";
import type { LocalLiteraryEvidenceBundle, SyntaxTokenEvidence } from "../local-analysis/types.js";
import {
  CHARACTER_RELATIONSHIP_PREDICATES,
  type CharacterRelationshipEvidenceResult,
} from "./character-relationship-evidence.js";

export const CHARACTER_RELATIONSHIP_AUDIT_VERSION = "saga-character-relationship-audit-v1";

export type RelationshipSyntaxAuditCategory =
  | "accepted_active_shape"
  | "accepted_passive_shape"
  | "active_subject_only"
  | "active_object_only"
  | "multiple_active_subjects"
  | "multiple_active_objects"
  | "passive_subject_only"
  | "passive_agent_only"
  | "passive_agent_missing_pobj"
  | "passive_agent_multiple_pobj"
  | "multiple_passive_subjects"
  | "multiple_passive_agents"
  | "mixed_active_passive_roles"
  | "no_direct_role_shape"
  | "other_unsupported_shape";

export type RelationshipRoleGroundingStatus =
  | "grounded"
  | "no_linked_character"
  | "ambiguous_character"
  | "structural_locator_mismatch";

export type RelationshipGroundingAuditCategory =
  | "grounded_distinct_characters"
  | "self_relation"
  | "subject_no_linked_character"
  | "object_no_linked_character"
  | "both_no_linked_character"
  | "subject_ambiguous_character"
  | "object_ambiguous_character"
  | "both_ambiguous_character"
  | "subject_locator_mismatch"
  | "object_locator_mismatch"
  | "both_locator_mismatch"
  | "mixed_role_failures";

export type RelationshipSyntaxAuditItem = {
  predicateEvidenceId: string;
  predicateTokenId: number;
  predicateLemma: string;
  category: RelationshipSyntaxAuditCategory;
  directChildSignature: string;
  subjectToken: SyntaxTokenEvidence | null;
  objectToken: SyntaxTokenEvidence | null;
};

export type RelationshipGroundingAuditItem = {
  predicateEvidenceId: string;
  predicateTokenId: number;
  predicateLemma: string;
  syntaxCategory: "accepted_active_shape" | "accepted_passive_shape";
  subjectStatus: RelationshipRoleGroundingStatus;
  objectStatus: RelationshipRoleGroundingStatus;
  category: RelationshipGroundingAuditCategory;
  subjectToken: SyntaxTokenEvidence;
  objectToken: SyntaxTokenEvidence;
};

export type CharacterRelationshipAuditResult = {
  predicateHitCount: number;
  supportedBinarySyntaxCount: number;
  groundedObservationCount: number;
  syntaxItems: RelationshipSyntaxAuditItem[];
  groundingItems: RelationshipGroundingAuditItem[];
  syntaxCategoryCounts: Record<RelationshipSyntaxAuditCategory, number>;
  groundingCategoryCounts: Record<RelationshipGroundingAuditCategory, number>;
  subjectRoleStatusCounts: Record<RelationshipRoleGroundingStatus, number>;
  objectRoleStatusCounts: Record<RelationshipRoleGroundingStatus, number>;
  directChildSignatureCounts: Record<string, number>;
  byPredicateAndSyntaxCategory: Record<string, Record<RelationshipSyntaxAuditCategory, number>>;
  byPredicateAndGroundingCategory: Record<string, Record<RelationshipGroundingAuditCategory, number>>;
  noCharacterArgumentPosTags: Record<string, number>;
  noCharacterArgumentFinePosTags: Record<string, number>;
};

type SyntaxIndex = {
  byId: Map<number, SyntaxTokenEvidence>;
  children: Map<number, SyntaxTokenEvidence[]>;
};

type GroundingInspection = {
  status: RelationshipRoleGroundingStatus;
  characterKey: string | null;
};

const PREDICATE_SET = new Set<string>(CHARACTER_RELATIONSHIP_PREDICATES);

function validateFingerprint(value: string, code: string) {
  if (!/^[0-9a-f]{64}$/u.test(value)) throw new Error(code);
}

function normalizeLemma(value: string) {
  return value.trim().toLocaleLowerCase("en-US");
}

function increment(target: Record<string, number>, key: string, amount = 1) {
  target[key] = (target[key] ?? 0) + amount;
}

function emptySyntaxCounts(): Record<RelationshipSyntaxAuditCategory, number> {
  return {
    accepted_active_shape: 0,
    accepted_passive_shape: 0,
    active_subject_only: 0,
    active_object_only: 0,
    multiple_active_subjects: 0,
    multiple_active_objects: 0,
    passive_subject_only: 0,
    passive_agent_only: 0,
    passive_agent_missing_pobj: 0,
    passive_agent_multiple_pobj: 0,
    multiple_passive_subjects: 0,
    multiple_passive_agents: 0,
    mixed_active_passive_roles: 0,
    no_direct_role_shape: 0,
    other_unsupported_shape: 0,
  };
}

function emptyGroundingCounts(): Record<RelationshipGroundingAuditCategory, number> {
  return {
    grounded_distinct_characters: 0,
    self_relation: 0,
    subject_no_linked_character: 0,
    object_no_linked_character: 0,
    both_no_linked_character: 0,
    subject_ambiguous_character: 0,
    object_ambiguous_character: 0,
    both_ambiguous_character: 0,
    subject_locator_mismatch: 0,
    object_locator_mismatch: 0,
    both_locator_mismatch: 0,
    mixed_role_failures: 0,
  };
}

function emptyRoleCounts(): Record<RelationshipRoleGroundingStatus, number> {
  return {
    grounded: 0,
    no_linked_character: 0,
    ambiguous_character: 0,
    structural_locator_mismatch: 0,
  };
}

function syntaxIndex(tokens: SyntaxTokenEvidence[]): SyntaxIndex {
  const byId = new Map<number, SyntaxTokenEvidence>();
  const children = new Map<number, SyntaxTokenEvidence[]>();
  for (const token of tokens) {
    if (byId.has(token.tokenId)) throw new Error(`relationship_audit_duplicate_syntax_token:${token.tokenId}`);
    byId.set(token.tokenId, token);
  }
  for (const token of tokens) {
    const head = byId.get(token.syntacticHeadTokenId);
    if (!head) throw new Error(`relationship_audit_missing_syntax_head:${token.evidenceId}`);
    if (head.sentenceId !== token.sentenceId) {
      throw new Error(`relationship_audit_cross_sentence_syntax_head:${token.evidenceId}`);
    }
    if (token.tokenId === token.syntacticHeadTokenId) continue;
    const group = children.get(token.syntacticHeadTokenId) ?? [];
    group.push(token);
    children.set(token.syntacticHeadTokenId, group);
  }
  for (const group of children.values()) {
    group.sort((left, right) => left.tokenId - right.tokenId || left.evidenceId.localeCompare(right.evidenceId));
  }
  return { byId, children };
}

function directChildren(index: SyntaxIndex, tokenId: number, relation?: string) {
  const children = index.children.get(tokenId) ?? [];
  return relation === undefined ? children : children.filter((token) => token.dependencyRelation === relation);
}

function directChildSignature(index: SyntaxIndex, predicateTokenId: number) {
  const counts: Record<string, number> = {};
  for (const child of directChildren(index, predicateTokenId)) increment(counts, child.dependencyRelation);
  return Object.entries(counts)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([relation, count]) => `${relation}:${count}`)
    .join("|") || "none";
}

function passiveAgentPobjs(index: SyntaxIndex, agents: SyntaxTokenEvidence[]) {
  if (agents.length !== 1) return [];
  return directChildren(index, agents[0]!.tokenId, "pobj");
}

export function classifyRelationshipPredicateSyntax(input: {
  predicate: SyntaxTokenEvidence;
  index: SyntaxIndex;
}): RelationshipSyntaxAuditItem {
  const activeSubjects = directChildren(input.index, input.predicate.tokenId, "nsubj");
  const activeObjects = directChildren(input.index, input.predicate.tokenId, "dobj");
  const passiveSubjects = directChildren(input.index, input.predicate.tokenId, "nsubjpass");
  const agents = directChildren(input.index, input.predicate.tokenId, "agent");
  const agentPobjs = passiveAgentPobjs(input.index, agents);

  const hasActive = activeSubjects.length > 0 || activeObjects.length > 0;
  const hasPassive = passiveSubjects.length > 0 || agents.length > 0 || agentPobjs.length > 0;
  let category: RelationshipSyntaxAuditCategory;
  let subjectToken: SyntaxTokenEvidence | null = null;
  let objectToken: SyntaxTokenEvidence | null = null;

  if (hasActive && hasPassive) {
    category = "mixed_active_passive_roles";
  } else if (!hasPassive && activeSubjects.length === 1 && activeObjects.length === 1) {
    category = "accepted_active_shape";
    subjectToken = activeSubjects[0]!;
    objectToken = activeObjects[0]!;
  } else if (!hasActive && passiveSubjects.length === 1 && agents.length === 1 && agentPobjs.length === 1) {
    category = "accepted_passive_shape";
    subjectToken = agentPobjs[0]!;
    objectToken = passiveSubjects[0]!;
  } else if (!hasPassive && activeSubjects.length > 1) {
    category = "multiple_active_subjects";
  } else if (!hasPassive && activeObjects.length > 1) {
    category = "multiple_active_objects";
  } else if (!hasPassive && activeSubjects.length === 1 && activeObjects.length === 0) {
    category = "active_subject_only";
  } else if (!hasPassive && activeSubjects.length === 0 && activeObjects.length === 1) {
    category = "active_object_only";
  } else if (!hasActive && passiveSubjects.length > 1) {
    category = "multiple_passive_subjects";
  } else if (!hasActive && agents.length > 1) {
    category = "multiple_passive_agents";
  } else if (!hasActive && agents.length === 1 && agentPobjs.length === 0) {
    category = "passive_agent_missing_pobj";
  } else if (!hasActive && agents.length === 1 && agentPobjs.length > 1) {
    category = "passive_agent_multiple_pobj";
  } else if (!hasActive && passiveSubjects.length === 1 && agents.length === 0) {
    category = "passive_subject_only";
  } else if (!hasActive && passiveSubjects.length === 0 && agents.length === 1 && agentPobjs.length === 1) {
    category = "passive_agent_only";
  } else if (!hasActive && !hasPassive) {
    category = "no_direct_role_shape";
  } else {
    category = "other_unsupported_shape";
  }

  return {
    predicateEvidenceId: input.predicate.evidenceId,
    predicateTokenId: input.predicate.tokenId,
    predicateLemma: normalizeLemma(input.predicate.lemma),
    category,
    directChildSignature: directChildSignature(input.index, input.predicate.tokenId),
    subjectToken,
    objectToken,
  };
}

function covers(mention: ResolvedIdentityMention, token: SyntaxTokenEvidence) {
  return mention.startOffset <= token.startOffset && mention.endOffset >= token.endOffset;
}

function inspectRoleGrounding(token: SyntaxTokenEvidence, identity: CharacterIdentityResult): GroundingInspection {
  const covering = identity.mentions.filter((mention) =>
    mention.resolutionState === "linked" && mention.characterKey !== null && covers(mention, token)
  );
  if (covering.length === 0) return { status: "no_linked_character", characterKey: null };
  const matchingLocator = covering.filter((mention) => mention.structuralLocator === token.structuralLocator);
  if (matchingLocator.length === 0) return { status: "structural_locator_mismatch", characterKey: null };
  const keys = [...new Set(matchingLocator.map((mention) => mention.characterKey!))];
  if (keys.length !== 1) return { status: "ambiguous_character", characterKey: null };
  return { status: "grounded", characterKey: keys[0]! };
}

function groundingCategory(
  subject: GroundingInspection,
  object: GroundingInspection,
): RelationshipGroundingAuditCategory {
  if (subject.status === "grounded" && object.status === "grounded") {
    return subject.characterKey === object.characterKey ? "self_relation" : "grounded_distinct_characters";
  }
  if (subject.status === "no_linked_character" && object.status === "no_linked_character") return "both_no_linked_character";
  if (subject.status === "ambiguous_character" && object.status === "ambiguous_character") return "both_ambiguous_character";
  if (subject.status === "structural_locator_mismatch" && object.status === "structural_locator_mismatch") return "both_locator_mismatch";
  if (subject.status === "no_linked_character" && object.status === "grounded") return "subject_no_linked_character";
  if (subject.status === "grounded" && object.status === "no_linked_character") return "object_no_linked_character";
  if (subject.status === "ambiguous_character" && object.status === "grounded") return "subject_ambiguous_character";
  if (subject.status === "grounded" && object.status === "ambiguous_character") return "object_ambiguous_character";
  if (subject.status === "structural_locator_mismatch" && object.status === "grounded") return "subject_locator_mismatch";
  if (subject.status === "grounded" && object.status === "structural_locator_mismatch") return "object_locator_mismatch";
  return "mixed_role_failures";
}

export function auditCharacterRelationshipCoverage(input: {
  literaryEvidence: LocalLiteraryEvidenceBundle;
  identity: CharacterIdentityResult;
  relationships: CharacterRelationshipEvidenceResult;
}): CharacterRelationshipAuditResult {
  validateFingerprint(input.literaryEvidence.normalizedInputFingerprint, "invalid_relationship_audit_input_fingerprint");
  validateFingerprint(input.identity.outputFingerprint, "invalid_relationship_audit_identity_output_fingerprint");
  if (input.identity.normalizedInputFingerprint !== input.literaryEvidence.normalizedInputFingerprint) {
    throw new Error("relationship_audit_identity_fingerprint_mismatch");
  }
  if (input.relationships.normalizedInputFingerprint !== input.literaryEvidence.normalizedInputFingerprint) {
    throw new Error("relationship_audit_result_fingerprint_mismatch");
  }
  if (input.relationships.identityOutputFingerprint !== input.identity.outputFingerprint) {
    throw new Error("relationship_audit_identity_output_fingerprint_mismatch");
  }
  if (!input.literaryEvidence.syntaxTokens) throw new Error("relationship_audit_missing_syntax");

  const index = syntaxIndex(input.literaryEvidence.syntaxTokens);
  const syntaxItems = input.literaryEvidence.syntaxTokens
    .filter((token) => PREDICATE_SET.has(normalizeLemma(token.lemma)))
    .map((predicate) => classifyRelationshipPredicateSyntax({ predicate, index }))
    .sort((left, right) => left.predicateTokenId - right.predicateTokenId || left.predicateEvidenceId.localeCompare(right.predicateEvidenceId));

  const syntaxCategoryCounts = emptySyntaxCounts();
  const groundingCategoryCounts = emptyGroundingCounts();
  const subjectRoleStatusCounts = emptyRoleCounts();
  const objectRoleStatusCounts = emptyRoleCounts();
  const directChildSignatureCounts: Record<string, number> = {};
  const byPredicateAndSyntaxCategory: Record<string, Record<RelationshipSyntaxAuditCategory, number>> = {};
  const byPredicateAndGroundingCategory: Record<string, Record<RelationshipGroundingAuditCategory, number>> = {};
  const noCharacterArgumentPosTags: Record<string, number> = {};
  const noCharacterArgumentFinePosTags: Record<string, number> = {};

  for (const item of syntaxItems) {
    syntaxCategoryCounts[item.category] += 1;
    increment(directChildSignatureCounts, item.directChildSignature);
    const predicateCounts = byPredicateAndSyntaxCategory[item.predicateLemma] ?? emptySyntaxCounts();
    predicateCounts[item.category] += 1;
    byPredicateAndSyntaxCategory[item.predicateLemma] = predicateCounts;
  }

  const groundingItems: RelationshipGroundingAuditItem[] = [];
  for (const item of syntaxItems) {
    if (item.category !== "accepted_active_shape" && item.category !== "accepted_passive_shape") continue;
    if (!item.subjectToken || !item.objectToken) throw new Error(`relationship_audit_supported_shape_missing_roles:${item.predicateEvidenceId}`);
    const subject = inspectRoleGrounding(item.subjectToken, input.identity);
    const object = inspectRoleGrounding(item.objectToken, input.identity);
    const category = groundingCategory(subject, object);
    const groundingItem: RelationshipGroundingAuditItem = {
      predicateEvidenceId: item.predicateEvidenceId,
      predicateTokenId: item.predicateTokenId,
      predicateLemma: item.predicateLemma,
      syntaxCategory: item.category,
      subjectStatus: subject.status,
      objectStatus: object.status,
      category,
      subjectToken: item.subjectToken,
      objectToken: item.objectToken,
    };
    groundingItems.push(groundingItem);
    groundingCategoryCounts[category] += 1;
    subjectRoleStatusCounts[subject.status] += 1;
    objectRoleStatusCounts[object.status] += 1;
    const predicateCounts = byPredicateAndGroundingCategory[item.predicateLemma] ?? emptyGroundingCounts();
    predicateCounts[category] += 1;
    byPredicateAndGroundingCategory[item.predicateLemma] = predicateCounts;
    if (subject.status === "no_linked_character") {
      increment(noCharacterArgumentPosTags, item.subjectToken.posTag);
      increment(noCharacterArgumentFinePosTags, item.subjectToken.finePosTag);
    }
    if (object.status === "no_linked_character") {
      increment(noCharacterArgumentPosTags, item.objectToken.posTag);
      increment(noCharacterArgumentFinePosTags, item.objectToken.finePosTag);
    }
  }

  const predicateHitCount = syntaxItems.length;
  const supportedBinarySyntaxCount = syntaxCategoryCounts.accepted_active_shape + syntaxCategoryCounts.accepted_passive_shape;
  const groundedObservationCount = groundingCategoryCounts.grounded_distinct_characters;
  const syntaxClassified = Object.values(syntaxCategoryCounts).reduce((sum, count) => sum + count, 0);
  const groundingClassified = Object.values(groundingCategoryCounts).reduce((sum, count) => sum + count, 0);
  if (syntaxClassified !== predicateHitCount) {
    throw new Error(`relationship_audit_syntax_accounting_mismatch:${syntaxClassified}:${predicateHitCount}`);
  }
  if (groundingClassified !== supportedBinarySyntaxCount) {
    throw new Error(`relationship_audit_grounding_accounting_mismatch:${groundingClassified}:${supportedBinarySyntaxCount}`);
  }
  if (groundingItems.length !== supportedBinarySyntaxCount) {
    throw new Error(`relationship_audit_grounding_item_mismatch:${groundingItems.length}:${supportedBinarySyntaxCount}`);
  }
  if (groundedObservationCount !== input.relationships.observations.length) {
    throw new Error(`relationship_audit_observation_mismatch:${groundedObservationCount}:${input.relationships.observations.length}`);
  }

  return {
    predicateHitCount,
    supportedBinarySyntaxCount,
    groundedObservationCount,
    syntaxItems,
    groundingItems,
    syntaxCategoryCounts,
    groundingCategoryCounts,
    subjectRoleStatusCounts,
    objectRoleStatusCounts,
    directChildSignatureCounts,
    byPredicateAndSyntaxCategory,
    byPredicateAndGroundingCategory,
    noCharacterArgumentPosTags,
    noCharacterArgumentFinePosTags,
  };
}
