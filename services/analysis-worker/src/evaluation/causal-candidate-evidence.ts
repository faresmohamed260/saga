import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import type { LocalLiteraryEvidenceBundle, SyntaxTokenEvidence } from "../local-analysis/types.js";
import {
  validateEventProviderResult,
  type EventProviderDescriptor,
  type EventProviderResult,
} from "./event-evaluation.js";
import {
  validateNarrativeTimelineEvidence,
  type NarrativeTimelineEvidenceResult,
} from "./narrative-timeline-evidence.js";

export const CAUSAL_CANDIDATE_EVIDENCE_VERSION = "saga-causal-candidate-evidence-v1";

export const CAUSAL_CUE_LEXICON = {
  because: "explicit_reason",
  therefore: "explicit_consequence",
  thus: "explicit_consequence",
  hence: "explicit_consequence",
  consequently: "explicit_consequence",
  thereby: "explicit_mechanism",
  accordingly: "explicit_consequence",
} as const;

export type CausalCueLemma = keyof typeof CAUSAL_CUE_LEXICON;
export type CausalCueFamily = typeof CAUSAL_CUE_LEXICON[CausalCueLemma];

export type CausalCueEvidence = {
  cueEvidenceId: string;
  syntaxEvidenceId: string;
  lemma: CausalCueLemma;
  family: CausalCueFamily;
  surfaceText: string;
  startOffset: number;
  endOffset: number;
  structuralLocator: string | null;
  paragraphId: number;
  sentenceId: number;
  tokenId: number;
  dependencyRelation: string;
  syntacticHeadTokenId: number;
  associatedEventIds: string[];
  associationPolicy: "same_sentence_unscoped";
};

export type CausalEventPairCandidate = {
  candidateId: string;
  firstEventId: string;
  secondEventId: string;
  firstNarrativeSequenceIndex: number;
  secondNarrativeSequenceIndex: number;
  structuralLocator: string | null;
  sentenceId: number;
  cueEvidenceIds: string[];
  sharedCharacterKeys: string[];
  pairPolicy: "exactly_two_events_same_sentence_with_explicit_causal_cue";
  causalRelationStatus: "unresolved";
  causalDirection: "unresolved";
  candidateStatus: "unverified_causal_pair_candidate";
};

export type AcceptedCausalEdge = never;

export type CausalCandidateEvidenceResult = {
  schemaVersion: typeof CAUSAL_CANDIDATE_EVIDENCE_VERSION;
  provider: EventProviderDescriptor;
  sourceProvider: EventProviderDescriptor;
  normalizedInputFingerprint: string;
  eventOutputFingerprint: string;
  timelineOutputFingerprint: string;
  configurationFingerprint: string;
  cues: CausalCueEvidence[];
  pairCandidates: CausalEventPairCandidate[];
  acceptedCausalEdges: AcceptedCausalEdge[];
  outputFingerprint: string;
};

function validateFingerprint(value: string, code: string) {
  if (!/^[0-9a-f]{64}$/u.test(value)) throw new Error(code);
}

function normalizeLemma(value: string) {
  return value.trim().toLocaleLowerCase("en-US");
}

function sentenceKey(locator: string | null, sentenceId: number) {
  return `${locator ?? "<null>"}:${sentenceId}`;
}

function buildSyntaxIndex(tokens: SyntaxTokenEvidence[]) {
  const byId = new Map<number, SyntaxTokenEvidence>();
  const bySentence = new Map<string, SyntaxTokenEvidence[]>();
  for (const token of tokens) {
    if (byId.has(token.tokenId)) throw new Error(`causal_duplicate_syntax_token:${token.tokenId}`);
    byId.set(token.tokenId, token);
    const key = sentenceKey(token.structuralLocator, token.sentenceId);
    const group = bySentence.get(key) ?? [];
    group.push(token);
    bySentence.set(key, group);
  }
  for (const token of tokens) {
    const head = byId.get(token.syntacticHeadTokenId);
    if (!head) throw new Error(`causal_missing_syntax_head:${token.evidenceId}`);
    if (head.sentenceId !== token.sentenceId || head.structuralLocator !== token.structuralLocator) {
      throw new Error(`causal_cross_sentence_syntax_head:${token.evidenceId}`);
    }
  }
  for (const group of bySentence.values()) {
    group.sort((left, right) => left.tokenId - right.tokenId || left.startOffset - right.startOffset || left.evidenceId.localeCompare(right.evidenceId));
  }
  return { byId, bySentence };
}

function cueFromToken(token: SyntaxTokenEvidence, associatedEventIds: string[]): CausalCueEvidence | null {
  const lemma = normalizeLemma(token.lemma);
  if (!(lemma in CAUSAL_CUE_LEXICON)) return null;
  const typedLemma = lemma as CausalCueLemma;
  const family = CAUSAL_CUE_LEXICON[typedLemma];
  return {
    cueEvidenceId: `causal-cue-${sha256Hex(canonicalJson({
      syntaxEvidenceId: token.evidenceId,
      lemma: typedLemma,
      family,
      startOffset: token.startOffset,
      endOffset: token.endOffset,
      structuralLocator: token.structuralLocator,
      associatedEventIds,
    })).slice(0, 24)}`,
    syntaxEvidenceId: token.evidenceId,
    lemma: typedLemma,
    family,
    surfaceText: token.surfaceText,
    startOffset: token.startOffset,
    endOffset: token.endOffset,
    structuralLocator: token.structuralLocator,
    paragraphId: token.paragraphId,
    sentenceId: token.sentenceId,
    tokenId: token.tokenId,
    dependencyRelation: token.dependencyRelation,
    syntacticHeadTokenId: token.syntacticHeadTokenId,
    associatedEventIds,
    associationPolicy: "same_sentence_unscoped",
  };
}

function participantCharacters(event: EventProviderResult["events"][number]) {
  return new Set(event.participants.map((participant) => participant.characterKey));
}

export function causalCandidateEvidenceFingerprint(input: {
  provider: EventProviderDescriptor;
  sourceProvider: EventProviderDescriptor;
  normalizedInputFingerprint: string;
  eventOutputFingerprint: string;
  timelineOutputFingerprint: string;
  configurationFingerprint: string;
  cues: CausalCueEvidence[];
  pairCandidates: CausalEventPairCandidate[];
  acceptedCausalEdges: AcceptedCausalEdge[];
}) {
  return sha256Hex(canonicalJson(input));
}

export function deriveCausalCandidateEvidence(input: {
  literaryEvidence: LocalLiteraryEvidenceBundle;
  events: EventProviderResult;
  timeline: NarrativeTimelineEvidenceResult;
}): CausalCandidateEvidenceResult {
  validateEventProviderResult(input.events);
  validateNarrativeTimelineEvidence(input.timeline);
  const fingerprint = input.events.normalizedInputFingerprint;
  validateFingerprint(fingerprint, "invalid_causal_input_fingerprint");
  if (input.literaryEvidence.normalizedInputFingerprint !== fingerprint) throw new Error("causal_literary_input_fingerprint_mismatch");
  if (input.timeline.normalizedInputFingerprint !== fingerprint) throw new Error("causal_timeline_input_fingerprint_mismatch");
  if (input.timeline.eventOutputFingerprint !== input.events.outputFingerprint) throw new Error("causal_timeline_event_fingerprint_mismatch");
  if (!input.literaryEvidence.syntaxTokens) throw new Error("causal_syntax_evidence_missing");

  const syntax = buildSyntaxIndex(input.literaryEvidence.syntaxTokens);
  const eventById = new Map(input.events.events.map((event) => [event.eventId, event]));
  if (eventById.size !== input.events.events.length) throw new Error("causal_duplicate_event_id");

  const entriesBySentence = new Map<string, typeof input.timeline.entries>();
  for (const entry of input.timeline.entries) {
    const sourceEvent = eventById.get(entry.eventId);
    if (!sourceEvent) throw new Error(`causal_timeline_event_missing:${entry.eventId}`);
    if (sourceEvent.startOffset !== entry.eventStartOffset || sourceEvent.endOffset !== entry.eventEndOffset) {
      throw new Error(`causal_timeline_event_span_drift:${entry.eventId}`);
    }
    const key = sentenceKey(entry.structuralLocator, entry.sentenceId);
    const group = entriesBySentence.get(key) ?? [];
    group.push(entry);
    entriesBySentence.set(key, group);
  }
  for (const group of entriesBySentence.values()) group.sort((a, b) => a.narrativeSequenceIndex - b.narrativeSequenceIndex || a.eventId.localeCompare(b.eventId));

  const configurationFingerprint = sha256Hex(canonicalJson({
    version: CAUSAL_CANDIDATE_EVIDENCE_VERSION,
    causalCueLexicon: CAUSAL_CUE_LEXICON,
    cueAssociation: "same_sentence_unscoped",
    pairPolicy: "exactly_two_events_same_sentence_with_explicit_causal_cue",
    causalRelationStatus: "unresolved",
    causalDirection: "unresolved",
    acceptedEdgeInference: false,
    crossSentencePairing: false,
    temporalOrderCausalInference: false,
    sharedParticipantCausalInference: false,
    transitiveClosure: false,
  }));

  const cues: CausalCueEvidence[] = [];
  const pairCandidates: CausalEventPairCandidate[] = [];

  for (const [key, entries] of entriesBySentence) {
    const sentenceTokens = syntax.bySentence.get(key) ?? [];
    const eventIds = entries.map((entry) => entry.eventId);
    const sentenceCues = sentenceTokens
      .map((token) => cueFromToken(token, eventIds))
      .filter((cue): cue is CausalCueEvidence => cue !== null)
      .sort((a, b) => a.startOffset - b.startOffset || a.endOffset - b.endOffset || a.cueEvidenceId.localeCompare(b.cueEvidenceId));
    if (sentenceCues.length === 0) continue;
    cues.push(...sentenceCues);

    if (entries.length !== 2) continue;
    const first = entries[0]!;
    const second = entries[1]!;
    const firstEvent = eventById.get(first.eventId)!;
    const secondEvent = eventById.get(second.eventId)!;
    const firstCharacters = participantCharacters(firstEvent);
    const secondCharacters = participantCharacters(secondEvent);
    const sharedCharacterKeys = [...firstCharacters].filter((keyValue) => secondCharacters.has(keyValue)).sort();
    const cueEvidenceIds = sentenceCues.map((cue) => cue.cueEvidenceId);
    pairCandidates.push({
      candidateId: `causal-pair-${sha256Hex(canonicalJson({
        firstEventId: first.eventId,
        secondEventId: second.eventId,
        cueEvidenceIds,
        timelineOutputFingerprint: input.timeline.outputFingerprint,
      })).slice(0, 24)}`,
      firstEventId: first.eventId,
      secondEventId: second.eventId,
      firstNarrativeSequenceIndex: first.narrativeSequenceIndex,
      secondNarrativeSequenceIndex: second.narrativeSequenceIndex,
      structuralLocator: first.structuralLocator,
      sentenceId: first.sentenceId,
      cueEvidenceIds,
      sharedCharacterKeys,
      pairPolicy: "exactly_two_events_same_sentence_with_explicit_causal_cue",
      causalRelationStatus: "unresolved",
      causalDirection: "unresolved",
      candidateStatus: "unverified_causal_pair_candidate",
    });
  }

  cues.sort((a, b) => a.startOffset - b.startOffset || a.endOffset - b.endOffset || a.cueEvidenceId.localeCompare(b.cueEvidenceId));
  pairCandidates.sort((a, b) => a.firstNarrativeSequenceIndex - b.firstNarrativeSequenceIndex || a.secondNarrativeSequenceIndex - b.secondNarrativeSequenceIndex || a.candidateId.localeCompare(b.candidateId));

  const acceptedCausalEdges: AcceptedCausalEdge[] = [];
  const provider: EventProviderDescriptor = { name: "saga-causal-candidate-evidence", model: null, revision: CAUSAL_CANDIDATE_EVIDENCE_VERSION };
  const semantic = {
    provider,
    sourceProvider: input.events.provider,
    normalizedInputFingerprint: fingerprint,
    eventOutputFingerprint: input.events.outputFingerprint,
    timelineOutputFingerprint: input.timeline.outputFingerprint,
    configurationFingerprint,
    cues,
    pairCandidates,
    acceptedCausalEdges,
  };
  const result: CausalCandidateEvidenceResult = {
    schemaVersion: CAUSAL_CANDIDATE_EVIDENCE_VERSION,
    ...semantic,
    outputFingerprint: causalCandidateEvidenceFingerprint(semantic),
  };
  validateCausalCandidateEvidence(result);
  return result;
}

export function validateCausalCandidateEvidence(result: CausalCandidateEvidenceResult) {
  if (result.schemaVersion !== CAUSAL_CANDIDATE_EVIDENCE_VERSION) throw new Error("unsupported_causal_candidate_evidence");
  validateFingerprint(result.normalizedInputFingerprint, "invalid_causal_result_input_fingerprint");
  validateFingerprint(result.eventOutputFingerprint, "invalid_causal_event_output_fingerprint");
  validateFingerprint(result.timelineOutputFingerprint, "invalid_causal_timeline_output_fingerprint");
  validateFingerprint(result.configurationFingerprint, "invalid_causal_configuration_fingerprint");
  validateFingerprint(result.outputFingerprint, "invalid_causal_output_fingerprint");
  if (result.provider.name !== "saga-causal-candidate-evidence" || result.provider.revision !== CAUSAL_CANDIDATE_EVIDENCE_VERSION) {
    throw new Error("invalid_causal_provider");
  }
  if (result.acceptedCausalEdges.length !== 0) throw new Error("accepted_causal_edges_not_allowed_v1");

  const cueById = new Map<string, CausalCueEvidence>();
  for (const cue of result.cues) {
    if (cueById.has(cue.cueEvidenceId)) throw new Error(`duplicate_causal_cue:${cue.cueEvidenceId}`);
    if (cue.associationPolicy !== "same_sentence_unscoped") throw new Error(`invalid_causal_cue_policy:${cue.cueEvidenceId}`);
    if (CAUSAL_CUE_LEXICON[cue.lemma] !== cue.family) throw new Error(`invalid_causal_cue_family:${cue.cueEvidenceId}`);
    if (cue.associatedEventIds.length === 0) throw new Error(`causal_cue_without_events:${cue.cueEvidenceId}`);
    cueById.set(cue.cueEvidenceId, cue);
  }

  const candidateIds = new Set<string>();
  const pairKeys = new Set<string>();
  let previousFirstIndex = -1;
  for (const candidate of result.pairCandidates) {
    if (candidateIds.has(candidate.candidateId)) throw new Error(`duplicate_causal_candidate:${candidate.candidateId}`);
    candidateIds.add(candidate.candidateId);
    if (candidate.firstEventId === candidate.secondEventId) throw new Error(`causal_candidate_self_pair:${candidate.candidateId}`);
    if (candidate.firstNarrativeSequenceIndex >= candidate.secondNarrativeSequenceIndex) throw new Error(`causal_candidate_order_drift:${candidate.candidateId}`);
    if (candidate.firstNarrativeSequenceIndex < previousFirstIndex) throw new Error(`causal_candidate_source_order_drift:${candidate.candidateId}`);
    previousFirstIndex = candidate.firstNarrativeSequenceIndex;
    if (candidate.causalRelationStatus !== "unresolved" || candidate.causalDirection !== "unresolved") {
      throw new Error(`causal_candidate_relation_resolved:${candidate.candidateId}`);
    }
    if (candidate.candidateStatus !== "unverified_causal_pair_candidate") throw new Error(`invalid_causal_candidate_status:${candidate.candidateId}`);
    if (candidate.pairPolicy !== "exactly_two_events_same_sentence_with_explicit_causal_cue") throw new Error(`invalid_causal_pair_policy:${candidate.candidateId}`);
    const pairKey = `${candidate.firstEventId}:${candidate.secondEventId}`;
    if (pairKeys.has(pairKey)) throw new Error(`duplicate_causal_event_pair:${pairKey}`);
    pairKeys.add(pairKey);
    if (candidate.cueEvidenceIds.length === 0) throw new Error(`causal_candidate_without_cue:${candidate.candidateId}`);
    for (const cueId of candidate.cueEvidenceIds) {
      const cue = cueById.get(cueId);
      if (!cue) throw new Error(`causal_candidate_missing_cue:${candidate.candidateId}:${cueId}`);
      if (cue.sentenceId !== candidate.sentenceId || cue.structuralLocator !== candidate.structuralLocator) {
        throw new Error(`causal_candidate_cross_sentence_cue:${candidate.candidateId}:${cueId}`);
      }
      if (!cue.associatedEventIds.includes(candidate.firstEventId) || !cue.associatedEventIds.includes(candidate.secondEventId)) {
        throw new Error(`causal_candidate_cue_event_mismatch:${candidate.candidateId}:${cueId}`);
      }
    }
  }

  const expected = causalCandidateEvidenceFingerprint({
    provider: result.provider,
    sourceProvider: result.sourceProvider,
    normalizedInputFingerprint: result.normalizedInputFingerprint,
    eventOutputFingerprint: result.eventOutputFingerprint,
    timelineOutputFingerprint: result.timelineOutputFingerprint,
    configurationFingerprint: result.configurationFingerprint,
    cues: result.cues,
    pairCandidates: result.pairCandidates,
    acceptedCausalEdges: result.acceptedCausalEdges,
  });
  if (expected !== result.outputFingerprint) throw new Error("causal_output_fingerprint_mismatch");
}
