import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import type { LocalLiteraryEvidenceBundle, SyntaxTokenEvidence } from "../local-analysis/types.js";
import {
  validateEventProviderResult,
  type EventProviderDescriptor,
  type EventProviderResult,
} from "./event-evaluation.js";

export const NARRATIVE_TIMELINE_EVIDENCE_VERSION = "saga-narrative-timeline-evidence-v1";

export const TEMPORAL_CUE_LEXICON = {
  before: "relative_sequence",
  after: "relative_sequence",
  then: "relative_sequence",
  later: "relative_sequence",
  earlier: "relative_sequence",
  previously: "relative_sequence",
  subsequently: "relative_sequence",
  eventually: "relative_sequence",
  soon: "relative_sequence",
  meanwhile: "simultaneity",
  simultaneously: "simultaneity",
  now: "deictic",
  today: "deictic",
  yesterday: "deictic",
  tomorrow: "deictic",
  during: "interval_boundary",
  since: "interval_boundary",
  until: "interval_boundary",
  ago: "relative_distance",
} as const;

export type TemporalCueLemma = keyof typeof TEMPORAL_CUE_LEXICON;
export type TemporalCueFamily = typeof TEMPORAL_CUE_LEXICON[TemporalCueLemma];

export type NarrativeTemporalCueEvidence = {
  cueEvidenceId: string;
  syntaxEvidenceId: string;
  family: TemporalCueFamily;
  lemma: TemporalCueLemma;
  surfaceText: string;
  startOffset: number;
  endOffset: number;
  structuralLocator: string | null;
  paragraphId: number;
  sentenceId: number;
  tokenId: number;
  dependencyRelation: string;
  associationPolicy: "same_sentence_unscoped";
};

export type NarrativeTimelineEntry = {
  timelineEntryId: string;
  eventId: string;
  eventSectionKey: string;
  eventStartOffset: number;
  eventEndOffset: number;
  triggerEvidenceId: string;
  syntaxEvidenceId: string;
  structuralLocator: string | null;
  paragraphId: number;
  sentenceId: number;
  tokenId: number;
  narrativeSequenceIndex: number;
  candidateStatus: "event_candidate";
  storyTimeStatus: "unresolved";
  temporalCueEvidenceIds: string[];
};

export type NarrativeStoryTimeRelation = never;

export type NarrativeTimelineEvidenceResult = {
  schemaVersion: typeof NARRATIVE_TIMELINE_EVIDENCE_VERSION;
  provider: EventProviderDescriptor;
  sourceProvider: EventProviderDescriptor;
  normalizedInputFingerprint: string;
  eventOutputFingerprint: string;
  configurationFingerprint: string;
  temporalCues: NarrativeTemporalCueEvidence[];
  entries: NarrativeTimelineEntry[];
  storyTimeRelations: NarrativeStoryTimeRelation[];
  outputFingerprint: string;
};

type SyntaxIndex = {
  byId: Map<number, SyntaxTokenEvidence>;
  bySentence: Map<string, SyntaxTokenEvidence[]>;
};

function validateFingerprint(value: string, code: string) {
  if (!/^[0-9a-f]{64}$/u.test(value)) throw new Error(code);
}

function normalizeLemma(value: string) {
  return value.trim().toLocaleLowerCase("en-US");
}

function sentenceKey(structuralLocator: string | null, sentenceId: number) {
  return `${structuralLocator ?? "<null>"}:${sentenceId}`;
}

function spanKey(startOffset: number, endOffset: number) {
  return `${startOffset}:${endOffset}`;
}

function buildSyntaxIndex(tokens: SyntaxTokenEvidence[]): SyntaxIndex {
  const byId = new Map<number, SyntaxTokenEvidence>();
  const bySentence = new Map<string, SyntaxTokenEvidence[]>();
  for (const token of tokens) {
    if (byId.has(token.tokenId)) throw new Error(`timeline_duplicate_syntax_token:${token.tokenId}`);
    byId.set(token.tokenId, token);
    const key = sentenceKey(token.structuralLocator, token.sentenceId);
    const sentence = bySentence.get(key) ?? [];
    sentence.push(token);
    bySentence.set(key, sentence);
  }
  for (const token of tokens) {
    const head = byId.get(token.syntacticHeadTokenId);
    if (!head) throw new Error(`timeline_missing_syntax_head:${token.evidenceId}`);
    if (head.sentenceId !== token.sentenceId || head.structuralLocator !== token.structuralLocator) {
      throw new Error(`timeline_cross_sentence_syntax_head:${token.evidenceId}`);
    }
  }
  for (const sentence of bySentence.values()) {
    sentence.sort((left, right) =>
      left.tokenId - right.tokenId
      || left.startOffset - right.startOffset
      || left.evidenceId.localeCompare(right.evidenceId)
    );
  }
  return { byId, bySentence };
}

function cueFromToken(token: SyntaxTokenEvidence): NarrativeTemporalCueEvidence | null {
  const lemma = normalizeLemma(token.lemma);
  if (!(lemma in TEMPORAL_CUE_LEXICON)) return null;
  const typedLemma = lemma as TemporalCueLemma;
  const family = TEMPORAL_CUE_LEXICON[typedLemma];
  return {
    cueEvidenceId: `timeline-cue-${sha256Hex(canonicalJson({
      syntaxEvidenceId: token.evidenceId,
      family,
      lemma: typedLemma,
      startOffset: token.startOffset,
      endOffset: token.endOffset,
      structuralLocator: token.structuralLocator,
    })).slice(0, 24)}`,
    syntaxEvidenceId: token.evidenceId,
    family,
    lemma: typedLemma,
    surfaceText: token.surfaceText,
    startOffset: token.startOffset,
    endOffset: token.endOffset,
    structuralLocator: token.structuralLocator,
    paragraphId: token.paragraphId,
    sentenceId: token.sentenceId,
    tokenId: token.tokenId,
    dependencyRelation: token.dependencyRelation,
    associationPolicy: "same_sentence_unscoped",
  };
}

export function narrativeTimelineEvidenceFingerprint(input: {
  provider: EventProviderDescriptor;
  sourceProvider: EventProviderDescriptor;
  normalizedInputFingerprint: string;
  eventOutputFingerprint: string;
  configurationFingerprint: string;
  temporalCues: NarrativeTemporalCueEvidence[];
  entries: NarrativeTimelineEntry[];
  storyTimeRelations: NarrativeStoryTimeRelation[];
}) {
  return sha256Hex(canonicalJson(input));
}

export function deriveNarrativeTimelineEvidence(input: {
  literaryEvidence: LocalLiteraryEvidenceBundle;
  events: EventProviderResult;
}): NarrativeTimelineEvidenceResult {
  validateEventProviderResult(input.events);
  validateFingerprint(input.events.normalizedInputFingerprint, "invalid_timeline_input_fingerprint");
  if (input.events.normalizedInputFingerprint !== input.literaryEvidence.normalizedInputFingerprint) {
    throw new Error("timeline_event_evidence_fingerprint_mismatch");
  }
  if (!input.literaryEvidence.syntaxTokens) throw new Error("timeline_syntax_evidence_missing");

  const syntax = buildSyntaxIndex(input.literaryEvidence.syntaxTokens);
  const triggersBySpan = new Map<string, typeof input.literaryEvidence.eventTriggers>();
  for (const trigger of input.literaryEvidence.eventTriggers) {
    const key = spanKey(trigger.startOffset, trigger.endOffset);
    const group = triggersBySpan.get(key) ?? [];
    group.push(trigger);
    triggersBySpan.set(key, group);
  }
  for (const group of triggersBySpan.values()) {
    group.sort((left, right) => left.evidenceId.localeCompare(right.evidenceId));
  }

  const configurationFingerprint = sha256Hex(canonicalJson({
    version: NARRATIVE_TIMELINE_EVIDENCE_VERSION,
    narrativeOrder: "normalized_source_offset",
    eventBinding: "exact_event_span_to_exactly_one_provider_trigger_and_syntax_token",
    temporalCueLexicon: TEMPORAL_CUE_LEXICON,
    cueAssociation: "same_sentence_unscoped",
    storyTimeStatus: "unresolved",
    storyTimeRelationInference: false,
    flashbackInference: false,
    totalChronologyInference: false,
  }));

  const cueById = new Map<string, NarrativeTemporalCueEvidence>();
  const provisionalEntries: Omit<NarrativeTimelineEntry, "narrativeSequenceIndex">[] = [];

  for (const event of input.events.events) {
    const matchingTriggers = triggersBySpan.get(spanKey(event.startOffset, event.endOffset)) ?? [];
    if (matchingTriggers.length !== 1) {
      throw new Error(`timeline_event_trigger_binding_count:${event.eventId}:${matchingTriggers.length}`);
    }
    const trigger = matchingTriggers[0]!;
    const triggerToken = syntax.byId.get(trigger.tokenId);
    if (!triggerToken) throw new Error(`timeline_missing_trigger_syntax:${event.eventId}`);
    if (
      triggerToken.startOffset !== trigger.startOffset
      || triggerToken.endOffset !== trigger.endOffset
      || triggerToken.sentenceId !== trigger.sentenceId
      || triggerToken.structuralLocator !== trigger.structuralLocator
    ) throw new Error(`timeline_trigger_syntax_drift:${event.eventId}`);

    const sentenceTokens = syntax.bySentence.get(sentenceKey(triggerToken.structuralLocator, triggerToken.sentenceId)) ?? [];
    const cues = sentenceTokens
      .map(cueFromToken)
      .filter((cue): cue is NarrativeTemporalCueEvidence => cue !== null)
      .sort((left, right) =>
        left.startOffset - right.startOffset
        || left.endOffset - right.endOffset
        || left.cueEvidenceId.localeCompare(right.cueEvidenceId)
      );
    for (const cue of cues) cueById.set(cue.cueEvidenceId, cue);

    provisionalEntries.push({
      timelineEntryId: `timeline-entry-${sha256Hex(canonicalJson({
        eventId: event.eventId,
        eventOutputFingerprint: input.events.outputFingerprint,
        triggerEvidenceId: trigger.evidenceId,
        startOffset: event.startOffset,
        endOffset: event.endOffset,
      })).slice(0, 24)}`,
      eventId: event.eventId,
      eventSectionKey: event.sectionKey,
      eventStartOffset: event.startOffset,
      eventEndOffset: event.endOffset,
      triggerEvidenceId: trigger.evidenceId,
      syntaxEvidenceId: triggerToken.evidenceId,
      structuralLocator: triggerToken.structuralLocator,
      paragraphId: triggerToken.paragraphId,
      sentenceId: triggerToken.sentenceId,
      tokenId: triggerToken.tokenId,
      candidateStatus: "event_candidate",
      storyTimeStatus: "unresolved",
      temporalCueEvidenceIds: cues.map((cue) => cue.cueEvidenceId),
    });
  }

  const entries = provisionalEntries
    .sort((left, right) =>
      left.eventStartOffset - right.eventStartOffset
      || left.eventEndOffset - right.eventEndOffset
      || left.eventId.localeCompare(right.eventId)
      || left.timelineEntryId.localeCompare(right.timelineEntryId)
    )
    .map((entry, narrativeSequenceIndex) => ({ ...entry, narrativeSequenceIndex }));
  const temporalCues = [...cueById.values()].sort((left, right) =>
    left.startOffset - right.startOffset
    || left.endOffset - right.endOffset
    || left.cueEvidenceId.localeCompare(right.cueEvidenceId)
  );
  const storyTimeRelations: NarrativeStoryTimeRelation[] = [];
  const provider: EventProviderDescriptor = {
    name: "saga-narrative-timeline",
    model: null,
    revision: NARRATIVE_TIMELINE_EVIDENCE_VERSION,
  };
  const semantic = {
    provider,
    sourceProvider: input.events.provider,
    normalizedInputFingerprint: input.events.normalizedInputFingerprint,
    eventOutputFingerprint: input.events.outputFingerprint,
    configurationFingerprint,
    temporalCues,
    entries,
    storyTimeRelations,
  };
  const result: NarrativeTimelineEvidenceResult = {
    schemaVersion: NARRATIVE_TIMELINE_EVIDENCE_VERSION,
    ...semantic,
    outputFingerprint: narrativeTimelineEvidenceFingerprint(semantic),
  };
  validateNarrativeTimelineEvidence(result);
  return result;
}

export function validateNarrativeTimelineEvidence(result: NarrativeTimelineEvidenceResult) {
  if (result.schemaVersion !== NARRATIVE_TIMELINE_EVIDENCE_VERSION) throw new Error("unsupported_narrative_timeline_evidence");
  validateFingerprint(result.normalizedInputFingerprint, "invalid_timeline_input_fingerprint");
  validateFingerprint(result.eventOutputFingerprint, "invalid_timeline_event_output_fingerprint");
  validateFingerprint(result.configurationFingerprint, "invalid_timeline_configuration_fingerprint");
  validateFingerprint(result.outputFingerprint, "invalid_timeline_output_fingerprint");
  if (result.provider.name !== "saga-narrative-timeline" || result.provider.revision !== NARRATIVE_TIMELINE_EVIDENCE_VERSION) {
    throw new Error("invalid_timeline_provider");
  }
  if (result.storyTimeRelations.length !== 0) throw new Error("timeline_story_time_relations_not_allowed_v1");

  const cueById = new Map<string, NarrativeTemporalCueEvidence>();
  for (const cue of result.temporalCues) {
    if (cueById.has(cue.cueEvidenceId)) throw new Error(`duplicate_timeline_cue:${cue.cueEvidenceId}`);
    if (cue.associationPolicy !== "same_sentence_unscoped") throw new Error(`invalid_timeline_cue_policy:${cue.cueEvidenceId}`);
    if (TEMPORAL_CUE_LEXICON[cue.lemma] !== cue.family) throw new Error(`invalid_timeline_cue_family:${cue.cueEvidenceId}`);
    cueById.set(cue.cueEvidenceId, cue);
  }

  const entryIds = new Set<string>();
  const eventIds = new Set<string>();
  for (let index = 0; index < result.entries.length; index += 1) {
    const entry = result.entries[index]!;
    if (entryIds.has(entry.timelineEntryId)) throw new Error(`duplicate_timeline_entry:${entry.timelineEntryId}`);
    if (eventIds.has(entry.eventId)) throw new Error(`duplicate_timeline_event:${entry.eventId}`);
    entryIds.add(entry.timelineEntryId);
    eventIds.add(entry.eventId);
    if (entry.narrativeSequenceIndex !== index) throw new Error(`timeline_sequence_index_drift:${entry.eventId}`);
    if (entry.candidateStatus !== "event_candidate" || entry.storyTimeStatus !== "unresolved") {
      throw new Error(`timeline_invalid_event_status:${entry.eventId}`);
    }
    if (index > 0) {
      const previous = result.entries[index - 1]!;
      const ordered =
        previous.eventStartOffset < entry.eventStartOffset
        || (
          previous.eventStartOffset === entry.eventStartOffset
          && (
            previous.eventEndOffset < entry.eventEndOffset
            || (previous.eventEndOffset === entry.eventEndOffset && previous.eventId.localeCompare(entry.eventId) <= 0)
          )
        );
      if (!ordered) throw new Error(`timeline_source_order_drift:${entry.eventId}`);
    }
    for (const cueId of entry.temporalCueEvidenceIds) {
      const cue = cueById.get(cueId);
      if (!cue) throw new Error(`timeline_missing_cue_reference:${entry.eventId}:${cueId}`);
      if (cue.sentenceId !== entry.sentenceId || cue.structuralLocator !== entry.structuralLocator) {
        throw new Error(`timeline_cross_sentence_cue_reference:${entry.eventId}:${cueId}`);
      }
    }
  }

  const expected = narrativeTimelineEvidenceFingerprint({
    provider: result.provider,
    sourceProvider: result.sourceProvider,
    normalizedInputFingerprint: result.normalizedInputFingerprint,
    eventOutputFingerprint: result.eventOutputFingerprint,
    configurationFingerprint: result.configurationFingerprint,
    temporalCues: result.temporalCues,
    entries: result.entries,
    storyTimeRelations: result.storyTimeRelations,
  });
  if (expected !== result.outputFingerprint) throw new Error("timeline_output_fingerprint_mismatch");
}
