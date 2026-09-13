import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import type { LocalLiteraryEvidenceBundle } from "../local-analysis/types.js";
import {
  validateEventProviderResult,
  type EventParticipantRole,
  type EventProviderDescriptor,
  type EventProviderResult,
} from "./event-evaluation.js";
import {
  validateEventSemanticQualifierResult,
  type EventSemanticQualifierResult,
} from "./event-semantic-qualifiers.js";
import {
  validateNarrativeTimelineEvidence,
  type NarrativeTimelineEvidenceResult,
} from "./narrative-timeline-evidence.js";

export const CHARACTER_LIFE_STATE_EVIDENCE_VERSION = "saga-character-life-state-evidence-v1";

export const CHARACTER_LIFE_STATE_PREDICATES = {
  die: "actor",
  kill: "patient",
} as const;

export type CharacterLifeStatePredicate = keyof typeof CHARACTER_LIFE_STATE_PREDICATES;
export type CharacterLifeStateTargetRole = typeof CHARACTER_LIFE_STATE_PREDICATES[CharacterLifeStatePredicate];

export type CharacterLifeStateCandidate = {
  candidateId: string;
  sourceEventId: string;
  triggerEvidenceId: string;
  targetCharacterKey: string;
  targetMentionEvidenceId: string;
  predicate: CharacterLifeStatePredicate;
  targetRole: CharacterLifeStateTargetRole;
  stateDimension: "life_status";
  candidateValue: "dead";
  triggerStartOffset: number;
  triggerEndOffset: number;
  structuralLocator: string | null;
  narrativeSequenceIndex: number;
  storyTimeStatus: "unresolved";
  polarity: "negated" | "undetermined";
  modality: "modalized" | "undetermined";
  realis: "irrealis_cued" | "undetermined";
  qualifierCueEvidenceIds: string[];
  candidateStatus: "unverified_state_change_candidate";
  applicationStatus: "not_applied_candidate_only";
};

export type CharacterLifeStateApplication = never;

export type CharacterLifeStateEvidenceResult = {
  schemaVersion: typeof CHARACTER_LIFE_STATE_EVIDENCE_VERSION;
  provider: EventProviderDescriptor;
  eventProvider: EventProviderDescriptor;
  normalizedInputFingerprint: string;
  eventOutputFingerprint: string;
  qualifierOutputFingerprint: string;
  timelineOutputFingerprint: string;
  configurationFingerprint: string;
  candidates: CharacterLifeStateCandidate[];
  stateApplications: CharacterLifeStateApplication[];
  outputFingerprint: string;
};

function validateFingerprint(value: string, code: string) {
  if (!/^[0-9a-f]{64}$/u.test(value)) throw new Error(code);
}

function normalizeLemma(value: string) {
  return value.trim().toLocaleLowerCase("en-US");
}

function spanKey(startOffset: number, endOffset: number) {
  return `${startOffset}:${endOffset}`;
}

export function characterLifeStateEvidenceFingerprint(input: {
  provider: EventProviderDescriptor;
  eventProvider: EventProviderDescriptor;
  normalizedInputFingerprint: string;
  eventOutputFingerprint: string;
  qualifierOutputFingerprint: string;
  timelineOutputFingerprint: string;
  configurationFingerprint: string;
  candidates: CharacterLifeStateCandidate[];
  stateApplications: CharacterLifeStateApplication[];
}) {
  return sha256Hex(canonicalJson(input));
}

export function deriveCharacterLifeStateEvidence(input: {
  literaryEvidence: LocalLiteraryEvidenceBundle;
  events: EventProviderResult;
  qualifiers: EventSemanticQualifierResult;
  timeline: NarrativeTimelineEvidenceResult;
}): CharacterLifeStateEvidenceResult {
  validateEventProviderResult(input.events);
  validateEventSemanticQualifierResult(input.qualifiers);
  validateNarrativeTimelineEvidence(input.timeline);

  const fingerprint = input.events.normalizedInputFingerprint;
  validateFingerprint(fingerprint, "invalid_life_state_input_fingerprint");
  if (input.literaryEvidence.normalizedInputFingerprint !== fingerprint) {
    throw new Error("life_state_literary_input_fingerprint_mismatch");
  }
  if (input.qualifiers.normalizedInputFingerprint !== fingerprint) {
    throw new Error("life_state_qualifier_input_fingerprint_mismatch");
  }
  if (input.timeline.normalizedInputFingerprint !== fingerprint) {
    throw new Error("life_state_timeline_input_fingerprint_mismatch");
  }
  if (input.timeline.eventOutputFingerprint !== input.events.outputFingerprint) {
    throw new Error("life_state_timeline_event_fingerprint_mismatch");
  }

  const triggersBySpan = new Map<string, typeof input.literaryEvidence.eventTriggers>();
  for (const trigger of input.literaryEvidence.eventTriggers) {
    const key = spanKey(trigger.startOffset, trigger.endOffset);
    const group = triggersBySpan.get(key) ?? [];
    group.push(trigger);
    triggersBySpan.set(key, group);
  }
  const qualifierByTrigger = new Map(input.qualifiers.events.map((event) => [event.eventEvidenceId, event]));
  const timelineByEvent = new Map(input.timeline.entries.map((entry) => [entry.eventId, entry]));

  const configurationFingerprint = sha256Hex(canonicalJson({
    version: CHARACTER_LIFE_STATE_EVIDENCE_VERSION,
    predicates: CHARACTER_LIFE_STATE_PREDICATES,
    stateDimension: "life_status",
    candidateValue: "dead",
    targetPolicy: "exactly_one_grounded_character_in_required_event_role",
    qualifierPolicy: "preserve_strict_event_qualifier_evidence_without_assertion",
    narrativeOrder: "reuse_validated_timeline_sequence_index",
    storyTimeStatus: "unresolved",
    persistentStateApplication: false,
    alivePredecessorInference: false,
    validTimeInference: false,
    resurrectionInference: false,
    contradictionResolution: false,
  }));
  const provider: EventProviderDescriptor = {
    name: "saga-character-life-state-evidence",
    model: null,
    revision: CHARACTER_LIFE_STATE_EVIDENCE_VERSION,
  };

  const candidates: CharacterLifeStateCandidate[] = [];
  for (const event of input.events.events) {
    const triggers = triggersBySpan.get(spanKey(event.startOffset, event.endOffset)) ?? [];
    if (triggers.length !== 1) {
      throw new Error(`life_state_event_trigger_binding_count:${event.eventId}:${triggers.length}`);
    }
    const trigger = triggers[0]!;
    const lemma = normalizeLemma(trigger.lemma);
    if (!(lemma in CHARACTER_LIFE_STATE_PREDICATES)) continue;
    const predicate = lemma as CharacterLifeStatePredicate;
    const targetRole = CHARACTER_LIFE_STATE_PREDICATES[predicate] as CharacterLifeStateTargetRole;

    const timelineEntry = timelineByEvent.get(event.eventId);
    if (!timelineEntry) throw new Error(`life_state_timeline_entry_missing:${event.eventId}`);
    if (
      timelineEntry.triggerEvidenceId !== trigger.evidenceId
      || timelineEntry.eventStartOffset !== event.startOffset
      || timelineEntry.eventEndOffset !== event.endOffset
      || timelineEntry.storyTimeStatus !== "unresolved"
    ) throw new Error(`life_state_timeline_binding_drift:${event.eventId}`);

    const qualifier = qualifierByTrigger.get(trigger.evidenceId);
    if (!qualifier) throw new Error(`life_state_qualifier_missing:${trigger.evidenceId}`);
    if (
      qualifier.triggerStartOffset !== trigger.startOffset
      || qualifier.triggerEndOffset !== trigger.endOffset
      || qualifier.triggerStructuralLocator !== trigger.structuralLocator
    ) throw new Error(`life_state_qualifier_binding_drift:${trigger.evidenceId}`);

    const targets = event.participants.filter((participant) => participant.role === targetRole);
    if (targets.length !== 1) continue;
    const target = targets[0]!;
    if (!target.evidenceId) continue;

    const candidateId = `life-state-${sha256Hex(canonicalJson({
      sourceEventId: event.eventId,
      triggerEvidenceId: trigger.evidenceId,
      targetCharacterKey: target.characterKey,
      targetMentionEvidenceId: target.evidenceId,
      predicate,
      narrativeSequenceIndex: timelineEntry.narrativeSequenceIndex,
    })).slice(0, 24)}`;
    candidates.push({
      candidateId,
      sourceEventId: event.eventId,
      triggerEvidenceId: trigger.evidenceId,
      targetCharacterKey: target.characterKey,
      targetMentionEvidenceId: target.evidenceId,
      predicate,
      targetRole,
      stateDimension: "life_status",
      candidateValue: "dead",
      triggerStartOffset: trigger.startOffset,
      triggerEndOffset: trigger.endOffset,
      structuralLocator: trigger.structuralLocator,
      narrativeSequenceIndex: timelineEntry.narrativeSequenceIndex,
      storyTimeStatus: "unresolved",
      polarity: qualifier.polarity,
      modality: qualifier.modality,
      realis: qualifier.realis,
      qualifierCueEvidenceIds: qualifier.cues.map((cue) => cue.evidenceId).sort(),
      candidateStatus: "unverified_state_change_candidate",
      applicationStatus: "not_applied_candidate_only",
    });
  }

  candidates.sort((left, right) =>
    left.narrativeSequenceIndex - right.narrativeSequenceIndex
    || left.triggerStartOffset - right.triggerStartOffset
    || left.candidateId.localeCompare(right.candidateId)
  );

  const stateApplications: CharacterLifeStateApplication[] = [];
  const semantic = {
    provider,
    eventProvider: input.events.provider,
    normalizedInputFingerprint: fingerprint,
    eventOutputFingerprint: input.events.outputFingerprint,
    qualifierOutputFingerprint: input.qualifiers.outputFingerprint,
    timelineOutputFingerprint: input.timeline.outputFingerprint,
    configurationFingerprint,
    candidates,
    stateApplications,
  };
  const result: CharacterLifeStateEvidenceResult = {
    schemaVersion: CHARACTER_LIFE_STATE_EVIDENCE_VERSION,
    ...semantic,
    outputFingerprint: characterLifeStateEvidenceFingerprint(semantic),
  };
  validateCharacterLifeStateEvidence(result);
  return result;
}

export function validateCharacterLifeStateEvidence(result: CharacterLifeStateEvidenceResult) {
  if (result.schemaVersion !== CHARACTER_LIFE_STATE_EVIDENCE_VERSION) {
    throw new Error("unsupported_character_life_state_evidence");
  }
  validateFingerprint(result.normalizedInputFingerprint, "invalid_life_state_result_input_fingerprint");
  validateFingerprint(result.eventOutputFingerprint, "invalid_life_state_event_output_fingerprint");
  validateFingerprint(result.qualifierOutputFingerprint, "invalid_life_state_qualifier_output_fingerprint");
  validateFingerprint(result.timelineOutputFingerprint, "invalid_life_state_timeline_output_fingerprint");
  validateFingerprint(result.configurationFingerprint, "invalid_life_state_configuration_fingerprint");
  validateFingerprint(result.outputFingerprint, "invalid_life_state_output_fingerprint");
  if (result.provider.name !== "saga-character-life-state-evidence") throw new Error("invalid_life_state_provider");
  if (result.provider.revision !== CHARACTER_LIFE_STATE_EVIDENCE_VERSION) throw new Error("invalid_life_state_provider_revision");
  if (result.stateApplications.length !== 0) throw new Error("life_state_applications_not_allowed_v1");

  const candidateIds = new Set<string>();
  const sourceEvents = new Set<string>();
  let previousSequence = -1;
  for (const candidate of result.candidates) {
    if (candidateIds.has(candidate.candidateId)) throw new Error(`duplicate_life_state_candidate:${candidate.candidateId}`);
    if (sourceEvents.has(candidate.sourceEventId)) throw new Error(`duplicate_life_state_source_event:${candidate.sourceEventId}`);
    candidateIds.add(candidate.candidateId);
    sourceEvents.add(candidate.sourceEventId);
    if (!candidate.targetCharacterKey.trim() || !candidate.targetMentionEvidenceId.trim()) {
      throw new Error(`invalid_life_state_target:${candidate.candidateId}`);
    }
    if (CHARACTER_LIFE_STATE_PREDICATES[candidate.predicate] !== candidate.targetRole) {
      throw new Error(`invalid_life_state_target_role:${candidate.candidateId}`);
    }
    if (candidate.stateDimension !== "life_status" || candidate.candidateValue !== "dead") {
      throw new Error(`invalid_life_state_value:${candidate.candidateId}`);
    }
    if (candidate.storyTimeStatus !== "unresolved") throw new Error(`life_state_story_time_not_unresolved:${candidate.candidateId}`);
    if (candidate.candidateStatus !== "unverified_state_change_candidate") {
      throw new Error(`invalid_life_state_candidate_status:${candidate.candidateId}`);
    }
    if (candidate.applicationStatus !== "not_applied_candidate_only") {
      throw new Error(`life_state_candidate_applied:${candidate.candidateId}`);
    }
    if (!Number.isSafeInteger(candidate.narrativeSequenceIndex) || candidate.narrativeSequenceIndex < 0) {
      throw new Error(`invalid_life_state_sequence_index:${candidate.candidateId}`);
    }
    if (candidate.narrativeSequenceIndex < previousSequence) throw new Error(`life_state_source_order_drift:${candidate.candidateId}`);
    previousSequence = candidate.narrativeSequenceIndex;
    if (candidate.triggerEndOffset <= candidate.triggerStartOffset || candidate.triggerStartOffset < 0) {
      throw new Error(`invalid_life_state_trigger_span:${candidate.candidateId}`);
    }
  }

  const expected = characterLifeStateEvidenceFingerprint({
    provider: result.provider,
    eventProvider: result.eventProvider,
    normalizedInputFingerprint: result.normalizedInputFingerprint,
    eventOutputFingerprint: result.eventOutputFingerprint,
    qualifierOutputFingerprint: result.qualifierOutputFingerprint,
    timelineOutputFingerprint: result.timelineOutputFingerprint,
    configurationFingerprint: result.configurationFingerprint,
    candidates: result.candidates,
    stateApplications: result.stateApplications,
  });
  if (expected !== result.outputFingerprint) throw new Error("life_state_output_fingerprint_mismatch");
}
