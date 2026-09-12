import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import { codePointLength } from "../ingestion/text.js";
import type { NormalizedSection } from "../ingestion/types.js";
import type { CharacterIdentityResult, ResolvedIdentityMention } from "../identity/types.js";
import {
  eventPredictionFingerprint,
  type EventParticipantPrediction,
  type EventProviderResult,
  type EventPrediction,
} from "./event-evaluation.js";

export type DeterministicEventConfig = {
  participantContextCodePoints: number;
  includePronouns: boolean;
  eventVerbs: string[];
};

export const DEFAULT_DETERMINISTIC_EVENT_CONFIG: DeterministicEventConfig = {
  participantContextCodePoints: 64,
  includePronouns: false,
  eventVerbs: [
    "arrived",
    "attacked",
    "broke",
    "closed",
    "died",
    "entered",
    "escaped",
    "fell",
    "fled",
    "found",
    "gave",
    "grabbed",
    "hit",
    "killed",
    "kissed",
    "left",
    "lost",
    "met",
    "opened",
    "picked",
    "pulled",
    "pushed",
    "returned",
    "ran",
    "saved",
    "shot",
    "slapped",
    "stabbed",
    "stole",
    "struck",
    "took",
    "walked",
    "won"
  ],
};

const EVENT_BASELINE_VERSION = "saga-event-lexical-v1";
const SENTENCE_BARRIER = /[.!?;\n]/u;

type TriggerSpan = {
  eventId: string;
  sectionKey: string;
  startOffset: number;
  endOffset: number;
  verb: string;
};

function validateConfig(config: DeterministicEventConfig) {
  if (!Number.isSafeInteger(config.participantContextCodePoints) || config.participantContextCodePoints < 1 || config.participantContextCodePoints > 300) {
    throw new Error("invalid_event_participant_context");
  }
  if (config.eventVerbs.length === 0) throw new Error("empty_event_verb_lexicon");
  const seen = new Set<string>();
  for (const raw of config.eventVerbs) {
    const verb = raw.trim().toLocaleLowerCase("en-US");
    if (!/^[a-z]+$/u.test(verb)) throw new Error(`invalid_event_verb:${raw}`);
    if (seen.has(verb)) throw new Error(`duplicate_event_verb:${verb}`);
    seen.add(verb);
  }
}

export function deterministicEventConfigFingerprint(config: DeterministicEventConfig) {
  validateConfig(config);
  return sha256Hex(canonicalJson(config));
}

function escapeRegex(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&");
}

function extractTriggers(section: NormalizedSection, eventVerbs: string[]): TriggerSpan[] {
  const alternatives = eventVerbs.map(escapeRegex).join("|");
  const regex = new RegExp(`\\b(?:${alternatives})\\b`, "giu");
  const triggers: TriggerSpan[] = [];
  for (const match of section.normalized_text.matchAll(regex)) {
    if (match.index === undefined || !match[0]) continue;
    const localStart = codePointLength(section.normalized_text.slice(0, match.index));
    const localEnd = localStart + codePointLength(match[0]);
    const startOffset = section.start_offset + localStart;
    const endOffset = section.start_offset + localEnd;
    const verb = match[0].toLocaleLowerCase("en-US");
    triggers.push({
      eventId: `event-${sha256Hex(`${section.stable_key}:${startOffset}:${endOffset}:${verb}`).slice(0, 20)}`,
      sectionKey: section.stable_key,
      startOffset,
      endOffset,
      verb,
    });
  }
  return triggers;
}

function sliceAbsolute(section: NormalizedSection, startOffset: number, endOffset: number) {
  const chars = Array.from(section.normalized_text);
  const start = Math.max(0, startOffset - section.start_offset);
  const end = Math.max(start, endOffset - section.start_offset);
  return chars.slice(start, end).join("");
}

function eligibleMention(mention: ResolvedIdentityMention, includePronouns: boolean) {
  return mention.resolutionState === "linked" &&
    Boolean(mention.characterKey) &&
    (includePronouns || mention.mentionKind !== "pronoun");
}

function nearestBefore(input: {
  trigger: TriggerSpan;
  section: NormalizedSection;
  mentions: ResolvedIdentityMention[];
  config: DeterministicEventConfig;
}) {
  return input.mentions
    .filter((mention) => eligibleMention(mention, input.config.includePronouns))
    .filter((mention) => mention.endOffset <= input.trigger.startOffset)
    .map((mention) => ({ mention, gap: input.trigger.startOffset - mention.endOffset }))
    .filter(({ mention, gap }) =>
      gap <= input.config.participantContextCodePoints &&
      !SENTENCE_BARRIER.test(sliceAbsolute(input.section, mention.endOffset, input.trigger.startOffset)))
    .sort((left, right) => left.gap - right.gap || left.mention.evidenceId.localeCompare(right.mention.evidenceId))[0]?.mention ?? null;
}

function nearestAfter(input: {
  trigger: TriggerSpan;
  section: NormalizedSection;
  mentions: ResolvedIdentityMention[];
  config: DeterministicEventConfig;
}) {
  return input.mentions
    .filter((mention) => eligibleMention(mention, input.config.includePronouns))
    .filter((mention) => mention.startOffset >= input.trigger.endOffset)
    .map((mention) => ({ mention, gap: mention.startOffset - input.trigger.endOffset }))
    .filter(({ mention, gap }) =>
      gap <= input.config.participantContextCodePoints &&
      !SENTENCE_BARRIER.test(sliceAbsolute(input.section, input.trigger.endOffset, mention.startOffset)))
    .sort((left, right) => left.gap - right.gap || left.mention.evidenceId.localeCompare(right.mention.evidenceId))[0]?.mention ?? null;
}

function participantsForTrigger(input: {
  trigger: TriggerSpan;
  section: NormalizedSection;
  mentions: ResolvedIdentityMention[];
  config: DeterministicEventConfig;
}): EventParticipantPrediction[] {
  const participants: EventParticipantPrediction[] = [];
  const actor = nearestBefore(input);
  if (actor?.characterKey) {
    participants.push({
      characterKey: actor.characterKey,
      role: "actor",
      evidenceId: actor.evidenceId,
    });
  }
  const patient = nearestAfter(input);
  if (patient?.characterKey && patient.characterKey !== actor?.characterKey) {
    participants.push({
      characterKey: patient.characterKey,
      role: "patient",
      evidenceId: patient.evidenceId,
    });
  }
  return participants;
}

export function predictDeterministicEventCandidates(input: {
  sections: NormalizedSection[];
  normalizedInputFingerprint: string;
  identity: CharacterIdentityResult;
  config?: DeterministicEventConfig;
}): EventProviderResult {
  if (!/^[0-9a-f]{64}$/u.test(input.normalizedInputFingerprint)) {
    throw new Error("invalid_event_baseline_input_fingerprint");
  }
  if (input.identity.normalizedInputFingerprint !== input.normalizedInputFingerprint) {
    throw new Error("event_identity_input_fingerprint_mismatch");
  }
  const config = input.config ?? DEFAULT_DETERMINISTIC_EVENT_CONFIG;
  validateConfig(config);
  const configFingerprint = deterministicEventConfigFingerprint(config);
  const mentionsBySection = new Map<string, ResolvedIdentityMention[]>();

  for (const mention of input.identity.mentions) {
    const section = input.sections.find(
      (candidate) => mention.startOffset >= candidate.start_offset && mention.endOffset <= candidate.end_offset,
    );
    if (!section) continue;
    const current = mentionsBySection.get(section.stable_key) ?? [];
    current.push(mention);
    mentionsBySection.set(section.stable_key, current);
  }

  const events: EventPrediction[] = [];
  for (const section of input.sections) {
    const mentions = mentionsBySection.get(section.stable_key) ?? [];
    for (const trigger of extractTriggers(section, config.eventVerbs)) {
      events.push({
        eventId: trigger.eventId,
        sectionKey: trigger.sectionKey,
        startOffset: trigger.startOffset,
        endOffset: trigger.endOffset,
        participants: participantsForTrigger({ trigger, section, mentions, config }),
        decisionReason: `lexical_event_verb:${trigger.verb}`,
      });
    }
  }
  events.sort((left, right) => left.startOffset - right.startOffset || left.endOffset - right.endOffset || left.eventId.localeCompare(right.eventId));

  const provider = {
    name: "saga_deterministic_event_lexicon_floor",
    model: null,
    revision: `${EVENT_BASELINE_VERSION}:${configFingerprint.slice(0, 16)}`,
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
