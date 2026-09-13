import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import type {
  EventTriggerEvidence,
  LocalLiteraryEvidenceBundle,
  SyntaxTokenEvidence,
} from "../local-analysis/types.js";
import {
  EVENT_CONDITIONAL_MARKERS,
  EVENT_MODAL_LEMMAS,
} from "./event-semantic-qualifiers.js";
import type { EventProviderDescriptor } from "./event-evaluation.js";

export const EVENT_SEMANTIC_QUALIFIER_AUDIT_VERSION = "saga-event-semantic-qualifier-audit-v1";

export const EVENT_NEGATION_AUDIT_LEMMAS = ["not", "never"] as const;

export type EventQualifierAuditCueFamily = "negation" | "modal" | "conditional";

export type EventQualifierAuditStructuralCategory =
  | "captured_direct_trigger_child"
  | "captured_auxiliary_child"
  | "direct_child_nonqualifying"
  | "descendant_depth_2_plus"
  | "parent_or_ancestor"
  | "sibling_shared_head"
  | "other_connected_same_sentence"
  | "disconnected_same_sentence";

export type EventQualifierAuditAssociation = {
  cueEvidenceId: string;
  cueFamily: EventQualifierAuditCueFamily;
  cueLemma: string;
  cueDependencyRelation: string;
  cueTokenId: number;
  triggerEvidenceId: string;
  triggerTokenId: number;
  sentenceId: number;
  dependencyDistance: number | null;
  structuralCategory: EventQualifierAuditStructuralCategory;
  capturedByCurrentPolicy: boolean;
};

export type EventSemanticQualifierAuditResult = {
  schemaVersion: typeof EVENT_SEMANTIC_QUALIFIER_AUDIT_VERSION;
  provider: EventProviderDescriptor;
  sourceProvider: EventProviderDescriptor;
  normalizedInputFingerprint: string;
  configurationFingerprint: string;
  eventTriggerCount: number;
  candidateCueTokenCount: number;
  cueTokenWithEventSentenceCount: number;
  cueTokenWithoutEventSentenceCount: number;
  sameSentenceCueTriggerPairCount: number;
  associations: EventQualifierAuditAssociation[];
  outputFingerprint: string;
};

type SyntaxIndex = {
  byId: Map<number, SyntaxTokenEvidence>;
  children: Map<number, SyntaxTokenEvidence[]>;
  bySentence: Map<number, SyntaxTokenEvidence[]>;
};

const MODAL_LEMMA_SET = new Set<string>(EVENT_MODAL_LEMMAS);
const CONDITIONAL_MARKER_SET = new Set<string>(EVENT_CONDITIONAL_MARKERS);
const NEGATION_LEMMA_SET = new Set<string>(EVENT_NEGATION_AUDIT_LEMMAS);
const AUXILIARY_RELATIONS = new Set(["aux", "auxpass"]);

function normalizeLemma(value: string) {
  return value.trim().toLocaleLowerCase("en-US");
}

function validateFingerprint(value: string, code: string) {
  if (!/^[0-9a-f]{64}$/u.test(value)) throw new Error(code);
}

function buildSyntaxIndex(tokens: SyntaxTokenEvidence[]): SyntaxIndex {
  const byId = new Map<number, SyntaxTokenEvidence>();
  const children = new Map<number, SyntaxTokenEvidence[]>();
  const bySentence = new Map<number, SyntaxTokenEvidence[]>();

  for (const token of tokens) {
    if (byId.has(token.tokenId)) throw new Error(`event_qualifier_audit_duplicate_syntax_token:${token.tokenId}`);
    byId.set(token.tokenId, token);
    const sentence = bySentence.get(token.sentenceId) ?? [];
    sentence.push(token);
    bySentence.set(token.sentenceId, sentence);
  }

  for (const token of tokens) {
    const head = byId.get(token.syntacticHeadTokenId);
    if (!head) throw new Error(`event_qualifier_audit_missing_syntax_head:${token.evidenceId}`);
    if (head.sentenceId !== token.sentenceId) {
      throw new Error(`event_qualifier_audit_cross_sentence_syntax_head:${token.evidenceId}`);
    }
    if (token.tokenId !== token.syntacticHeadTokenId) {
      const current = children.get(token.syntacticHeadTokenId) ?? [];
      current.push(token);
      children.set(token.syntacticHeadTokenId, current);
    }
  }

  for (const values of children.values()) values.sort(compareToken);
  for (const values of bySentence.values()) values.sort(compareToken);
  return { byId, children, bySentence };
}

function compareToken(left: SyntaxTokenEvidence, right: SyntaxTokenEvidence) {
  return left.tokenId - right.tokenId || left.evidenceId.localeCompare(right.evidenceId);
}

function sameTriggerAndSyntax(trigger: EventTriggerEvidence, token: SyntaxTokenEvidence) {
  return trigger.tokenId === token.tokenId
    && trigger.surfaceText === token.surfaceText
    && trigger.lemma === token.lemma
    && trigger.startOffset === token.startOffset
    && trigger.endOffset === token.endOffset
    && trigger.structuralLocator === token.structuralLocator
    && trigger.sentenceId === token.sentenceId
    && trigger.dependencyRelation === token.dependencyRelation
    && trigger.syntacticHeadTokenId === token.syntacticHeadTokenId;
}

function cueFamily(token: SyntaxTokenEvidence): EventQualifierAuditCueFamily | null {
  const lemma = normalizeLemma(token.lemma);
  if (token.dependencyRelation === "neg" || NEGATION_LEMMA_SET.has(lemma)) return "negation";
  if (MODAL_LEMMA_SET.has(lemma)) return "modal";
  if (CONDITIONAL_MARKER_SET.has(lemma)) return "conditional";
  return null;
}

function parentChain(index: SyntaxIndex, startTokenId: number) {
  const chain: number[] = [];
  const visited = new Set<number>();
  let current = index.byId.get(startTokenId);
  while (current && !visited.has(current.tokenId)) {
    visited.add(current.tokenId);
    const headId = current.syntacticHeadTokenId;
    if (headId === current.tokenId) break;
    chain.push(headId);
    current = index.byId.get(headId);
  }
  return chain;
}

function dependencyDistance(index: SyntaxIndex, leftTokenId: number, rightTokenId: number): number | null {
  if (leftTokenId === rightTokenId) return 0;
  const left = index.byId.get(leftTokenId);
  const right = index.byId.get(rightTokenId);
  if (!left || !right || left.sentenceId !== right.sentenceId) return null;

  const adjacency = new Map<number, number[]>();
  for (const token of index.bySentence.get(left.sentenceId) ?? []) {
    if (token.tokenId === token.syntacticHeadTokenId) continue;
    const from = adjacency.get(token.tokenId) ?? [];
    from.push(token.syntacticHeadTokenId);
    adjacency.set(token.tokenId, from);
    const to = adjacency.get(token.syntacticHeadTokenId) ?? [];
    to.push(token.tokenId);
    adjacency.set(token.syntacticHeadTokenId, to);
  }

  const queue: Array<{ tokenId: number; distance: number }> = [{ tokenId: leftTokenId, distance: 0 }];
  const seen = new Set<number>([leftTokenId]);
  while (queue.length > 0) {
    const current = queue.shift()!;
    for (const next of adjacency.get(current.tokenId) ?? []) {
      if (seen.has(next)) continue;
      if (next === rightTokenId) return current.distance + 1;
      seen.add(next);
      queue.push({ tokenId: next, distance: current.distance + 1 });
    }
  }
  return null;
}

function capturedByCurrentPolicy(input: {
  family: EventQualifierAuditCueFamily;
  cue: SyntaxTokenEvidence;
  trigger: SyntaxTokenEvidence;
  index: SyntaxIndex;
}) {
  const { family, cue, trigger, index } = input;
  const lemma = normalizeLemma(cue.lemma);
  if (family === "negation") {
    if (cue.dependencyRelation !== "neg") return false;
    if (cue.syntacticHeadTokenId === trigger.tokenId) return true;
    const head = index.byId.get(cue.syntacticHeadTokenId);
    return Boolean(
      head
      && AUXILIARY_RELATIONS.has(head.dependencyRelation)
      && head.syntacticHeadTokenId === trigger.tokenId,
    );
  }
  if (family === "modal") {
    return MODAL_LEMMA_SET.has(lemma)
      && AUXILIARY_RELATIONS.has(cue.dependencyRelation)
      && cue.syntacticHeadTokenId === trigger.tokenId;
  }
  return CONDITIONAL_MARKER_SET.has(lemma)
    && cue.dependencyRelation === "mark"
    && cue.syntacticHeadTokenId === trigger.tokenId;
}

function structuralCategory(input: {
  family: EventQualifierAuditCueFamily;
  cue: SyntaxTokenEvidence;
  trigger: SyntaxTokenEvidence;
  index: SyntaxIndex;
  distance: number | null;
}): EventQualifierAuditStructuralCategory {
  const { family, cue, trigger, index, distance } = input;
  const captured = capturedByCurrentPolicy({ family, cue, trigger, index });
  if (captured && cue.syntacticHeadTokenId === trigger.tokenId) return "captured_direct_trigger_child";
  if (captured) return "captured_auxiliary_child";
  if (cue.syntacticHeadTokenId === trigger.tokenId) return "direct_child_nonqualifying";

  const cueAncestors = parentChain(index, cue.tokenId);
  const triggerIndex = cueAncestors.indexOf(trigger.tokenId);
  if (triggerIndex >= 1) return "descendant_depth_2_plus";

  const triggerAncestors = parentChain(index, trigger.tokenId);
  if (triggerAncestors.includes(cue.tokenId)) return "parent_or_ancestor";

  if (
    cue.tokenId !== trigger.tokenId
    && cue.syntacticHeadTokenId === trigger.syntacticHeadTokenId
    && cue.syntacticHeadTokenId !== cue.tokenId
  ) return "sibling_shared_head";

  return distance === null ? "disconnected_same_sentence" : "other_connected_same_sentence";
}

function compareTriggerCandidate(
  cue: SyntaxTokenEvidence,
  index: SyntaxIndex,
  left: EventTriggerEvidence,
  right: EventTriggerEvidence,
) {
  const leftDistance = dependencyDistance(index, cue.tokenId, left.tokenId);
  const rightDistance = dependencyDistance(index, cue.tokenId, right.tokenId);
  const leftRank = leftDistance ?? Number.MAX_SAFE_INTEGER;
  const rightRank = rightDistance ?? Number.MAX_SAFE_INTEGER;
  return leftRank - rightRank
    || Math.abs(cue.tokenId - left.tokenId) - Math.abs(cue.tokenId - right.tokenId)
    || left.tokenId - right.tokenId
    || left.evidenceId.localeCompare(right.evidenceId);
}

export function eventSemanticQualifierAuditFingerprint(input: {
  provider: EventProviderDescriptor;
  sourceProvider: EventProviderDescriptor;
  normalizedInputFingerprint: string;
  configurationFingerprint: string;
  eventTriggerCount: number;
  candidateCueTokenCount: number;
  cueTokenWithEventSentenceCount: number;
  cueTokenWithoutEventSentenceCount: number;
  sameSentenceCueTriggerPairCount: number;
  associations: EventQualifierAuditAssociation[];
}) {
  return sha256Hex(canonicalJson(input));
}

export function auditEventSemanticQualifierCoverage(input: {
  normalizedInputFingerprint: string;
  literaryEvidence: LocalLiteraryEvidenceBundle;
}): EventSemanticQualifierAuditResult {
  validateFingerprint(input.normalizedInputFingerprint, "invalid_event_qualifier_audit_input_fingerprint");
  if (input.literaryEvidence.normalizedInputFingerprint !== input.normalizedInputFingerprint) {
    throw new Error("event_qualifier_audit_provider_input_fingerprint_mismatch");
  }
  if (!input.literaryEvidence.syntaxTokens) throw new Error("event_qualifier_audit_syntax_evidence_missing");

  const index = buildSyntaxIndex(input.literaryEvidence.syntaxTokens);
  const triggersBySentence = new Map<number, EventTriggerEvidence[]>();
  for (const trigger of input.literaryEvidence.eventTriggers) {
    const token = index.byId.get(trigger.tokenId);
    if (!token) throw new Error(`event_qualifier_audit_trigger_token_missing:${trigger.evidenceId}`);
    if (!sameTriggerAndSyntax(trigger, token)) {
      throw new Error(`event_qualifier_audit_trigger_syntax_mismatch:${trigger.evidenceId}`);
    }
    const current = triggersBySentence.get(trigger.sentenceId) ?? [];
    current.push(trigger);
    triggersBySentence.set(trigger.sentenceId, current);
  }
  for (const triggers of triggersBySentence.values()) {
    triggers.sort((left, right) => left.tokenId - right.tokenId || left.evidenceId.localeCompare(right.evidenceId));
  }

  const candidateCues = input.literaryEvidence.syntaxTokens
    .map((token) => ({ token, family: cueFamily(token) }))
    .filter((entry): entry is { token: SyntaxTokenEvidence; family: EventQualifierAuditCueFamily } => entry.family !== null)
    .sort((left, right) => compareToken(left.token, right.token));

  const associations: EventQualifierAuditAssociation[] = [];
  let cueTokenWithoutEventSentenceCount = 0;
  let sameSentenceCueTriggerPairCount = 0;

  for (const candidate of candidateCues) {
    const triggers = triggersBySentence.get(candidate.token.sentenceId) ?? [];
    if (triggers.length === 0) {
      cueTokenWithoutEventSentenceCount += 1;
      continue;
    }
    sameSentenceCueTriggerPairCount += triggers.length;
    const nearest = [...triggers].sort((left, right) => compareTriggerCandidate(candidate.token, index, left, right))[0]!;
    const triggerToken = index.byId.get(nearest.tokenId)!;
    const distance = dependencyDistance(index, candidate.token.tokenId, nearest.tokenId);
    const captured = capturedByCurrentPolicy({
      family: candidate.family,
      cue: candidate.token,
      trigger: triggerToken,
      index,
    });
    associations.push({
      cueEvidenceId: candidate.token.evidenceId,
      cueFamily: candidate.family,
      cueLemma: normalizeLemma(candidate.token.lemma),
      cueDependencyRelation: candidate.token.dependencyRelation,
      cueTokenId: candidate.token.tokenId,
      triggerEvidenceId: nearest.evidenceId,
      triggerTokenId: nearest.tokenId,
      sentenceId: candidate.token.sentenceId,
      dependencyDistance: distance,
      structuralCategory: structuralCategory({
        family: candidate.family,
        cue: candidate.token,
        trigger: triggerToken,
        index,
        distance,
      }),
      capturedByCurrentPolicy: captured,
    });
  }

  associations.sort((left, right) =>
    left.sentenceId - right.sentenceId
    || left.cueTokenId - right.cueTokenId
    || left.triggerTokenId - right.triggerTokenId
    || left.cueEvidenceId.localeCompare(right.cueEvidenceId)
  );

  const sourceProvider: EventProviderDescriptor = {
    name: input.literaryEvidence.provider.name,
    model: input.literaryEvidence.provider.model,
    revision: input.literaryEvidence.provider.revision,
  };
  const configurationFingerprint = sha256Hex(canonicalJson({
    version: EVENT_SEMANTIC_QUALIFIER_AUDIT_VERSION,
    sourceProvider,
    cueFamilies: {
      negation: { relations: ["neg"], lemmas: [...EVENT_NEGATION_AUDIT_LEMMAS] },
      modal: { lemmas: [...EVENT_MODAL_LEMMAS] },
      conditional: { lemmas: [...EVENT_CONDITIONAL_MARKERS] },
    },
    association: "nearest_event_trigger_in_same_sentence_by_undirected_dependency_distance",
    tieBreak: ["dependency_distance", "absolute_token_distance", "trigger_token_id", "trigger_evidence_id"],
    policyMutation: false,
  }));
  const provider: EventProviderDescriptor = {
    name: "saga_event_semantic_qualifier_audit",
    model: null,
    revision: `${EVENT_SEMANTIC_QUALIFIER_AUDIT_VERSION}:${configurationFingerprint.slice(0, 16)}`,
  };
  const semantic = {
    provider,
    sourceProvider,
    normalizedInputFingerprint: input.normalizedInputFingerprint,
    configurationFingerprint,
    eventTriggerCount: input.literaryEvidence.eventTriggers.length,
    candidateCueTokenCount: candidateCues.length,
    cueTokenWithEventSentenceCount: associations.length,
    cueTokenWithoutEventSentenceCount,
    sameSentenceCueTriggerPairCount,
    associations,
  };
  return {
    schemaVersion: EVENT_SEMANTIC_QUALIFIER_AUDIT_VERSION,
    ...semantic,
    outputFingerprint: eventSemanticQualifierAuditFingerprint(semantic),
  };
}

export function validateEventSemanticQualifierAuditResult(result: EventSemanticQualifierAuditResult) {
  if (result.schemaVersion !== EVENT_SEMANTIC_QUALIFIER_AUDIT_VERSION) {
    throw new Error("unsupported_event_qualifier_audit_result");
  }
  validateFingerprint(result.normalizedInputFingerprint, "invalid_event_qualifier_audit_result_input_fingerprint");
  validateFingerprint(result.configurationFingerprint, "invalid_event_qualifier_audit_configuration_fingerprint");
  validateFingerprint(result.outputFingerprint, "invalid_event_qualifier_audit_output_fingerprint");
  if (result.candidateCueTokenCount !== result.cueTokenWithEventSentenceCount + result.cueTokenWithoutEventSentenceCount) {
    throw new Error("event_qualifier_audit_cue_count_mismatch");
  }
  const cueIds = new Set<string>();
  for (const association of result.associations) {
    if (cueIds.has(association.cueEvidenceId)) {
      throw new Error(`event_qualifier_audit_duplicate_cue_association:${association.cueEvidenceId}`);
    }
    cueIds.add(association.cueEvidenceId);
    if (!Number.isSafeInteger(association.cueTokenId) || association.cueTokenId < 0) {
      throw new Error(`invalid_event_qualifier_audit_cue_token:${association.cueEvidenceId}`);
    }
    if (!Number.isSafeInteger(association.triggerTokenId) || association.triggerTokenId < 0) {
      throw new Error(`invalid_event_qualifier_audit_trigger_token:${association.triggerEvidenceId}`);
    }
    if (association.dependencyDistance !== null && (!Number.isSafeInteger(association.dependencyDistance) || association.dependencyDistance < 0)) {
      throw new Error(`invalid_event_qualifier_audit_distance:${association.cueEvidenceId}`);
    }
    if (association.structuralCategory.startsWith("captured_") !== association.capturedByCurrentPolicy) {
      throw new Error(`event_qualifier_audit_capture_category_mismatch:${association.cueEvidenceId}`);
    }
  }
  const expected = eventSemanticQualifierAuditFingerprint({
    provider: result.provider,
    sourceProvider: result.sourceProvider,
    normalizedInputFingerprint: result.normalizedInputFingerprint,
    configurationFingerprint: result.configurationFingerprint,
    eventTriggerCount: result.eventTriggerCount,
    candidateCueTokenCount: result.candidateCueTokenCount,
    cueTokenWithEventSentenceCount: result.cueTokenWithEventSentenceCount,
    cueTokenWithoutEventSentenceCount: result.cueTokenWithoutEventSentenceCount,
    sameSentenceCueTriggerPairCount: result.sameSentenceCueTriggerPairCount,
    associations: result.associations,
  });
  if (expected !== result.outputFingerprint) throw new Error("event_qualifier_audit_output_fingerprint_mismatch");
}
