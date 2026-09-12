import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import { codePointLength } from "../ingestion/text.js";
import type { NormalizedSection } from "../ingestion/types.js";
import type { CharacterIdentityResult, ResolvedIdentityMention } from "../identity/types.js";
import {
  dialoguePredictionFingerprint,
  type DialogueProviderResult,
  type DialogueQuotePrediction,
} from "./dialogue-evaluation.js";

export type DeterministicDialogueConfig = {
  contextCodePoints: number;
  maxVerbMentionGapCodePoints: number;
  minimumScoreMargin: number;
  includePronouns: boolean;
  speechVerbs: string[];
};

export const DEFAULT_DETERMINISTIC_DIALOGUE_CONFIG: DeterministicDialogueConfig = {
  contextCodePoints: 120,
  maxVerbMentionGapCodePoints: 48,
  minimumScoreMargin: 4,
  includePronouns: false,
  speechVerbs: [
    "add",
    "added",
    "adds",
    "answer",
    "answered",
    "answers",
    "ask",
    "asked",
    "asks",
    "call",
    "called",
    "calls",
    "continue",
    "continued",
    "continues",
    "cry",
    "cried",
    "cries",
    "demand",
    "demanded",
    "demands",
    "exclaim",
    "exclaimed",
    "exclaims",
    "hiss",
    "hissed",
    "hisses",
    "insist",
    "insisted",
    "insists",
    "murmur",
    "murmured",
    "murmurs",
    "mutter",
    "muttered",
    "mutters",
    "remark",
    "remarked",
    "remarks",
    "reply",
    "replied",
    "replies",
    "say",
    "said",
    "says",
    "shout",
    "shouted",
    "shouts",
    "snap",
    "snapped",
    "snaps",
    "tell",
    "tells",
    "told",
    "whisper",
    "whispered",
    "whispers",
    "yell",
    "yelled",
    "yells"
  ],
};

const DIALOGUE_BASELINE_VERSION = "saga-dialogue-deterministic-v1";

type QuoteSpan = {
  quoteId: string;
  sectionKey: string;
  startOffset: number;
  endOffset: number;
};

type VerbSpan = {
  verb: string;
  startOffset: number;
  endOffset: number;
};

type AttributionCandidate = {
  characterKey: string;
  score: number;
  side: "before" | "after";
  verb: string;
  mention: ResolvedIdentityMention;
};

function validateConfig(config: DeterministicDialogueConfig) {
  if (!Number.isSafeInteger(config.contextCodePoints) || config.contextCodePoints < 1 || config.contextCodePoints > 500) {
    throw new Error("invalid_dialogue_context_window");
  }
  if (!Number.isSafeInteger(config.maxVerbMentionGapCodePoints) || config.maxVerbMentionGapCodePoints < 0 || config.maxVerbMentionGapCodePoints > 200) {
    throw new Error("invalid_dialogue_verb_mention_gap");
  }
  if (!Number.isSafeInteger(config.minimumScoreMargin) || config.minimumScoreMargin < 0 || config.minimumScoreMargin > 100) {
    throw new Error("invalid_dialogue_score_margin");
  }
  if (config.speechVerbs.length === 0) throw new Error("empty_dialogue_speech_verbs");
  const seen = new Set<string>();
  for (const verb of config.speechVerbs) {
    const normalized = verb.trim().toLocaleLowerCase("en-US");
    if (!/^[a-z]+$/u.test(normalized)) throw new Error(`invalid_dialogue_speech_verb:${verb}`);
    if (seen.has(normalized)) throw new Error(`duplicate_dialogue_speech_verb:${normalized}`);
    seen.add(normalized);
  }
}

export function deterministicDialogueConfigFingerprint(config: DeterministicDialogueConfig) {
  validateConfig(config);
  return sha256Hex(canonicalJson(config));
}

function makeQuote(section: NormalizedSection, localStart: number, localEndExclusive: number): QuoteSpan {
  const startOffset = section.start_offset + localStart;
  const endOffset = section.start_offset + localEndExclusive;
  const quoteId = `quote-${sha256Hex(`${section.stable_key}:${startOffset}:${endOffset}`).slice(0, 20)}`;
  return { quoteId, sectionKey: section.stable_key, startOffset, endOffset };
}

function extractQuotesFromSection(section: NormalizedSection) {
  const chars = Array.from(section.normalized_text);
  const quotes: QuoteSpan[] = [];
  let curlyStart: number | null = null;
  let straightStart: number | null = null;

  for (let index = 0; index < chars.length; index += 1) {
    const char = chars[index];
    if (char === "“") {
      if (curlyStart === null) curlyStart = index;
      continue;
    }
    if (char === "”") {
      if (curlyStart !== null && index > curlyStart + 1) {
        const content = chars.slice(curlyStart + 1, index).join("").trim();
        if (content) quotes.push(makeQuote(section, curlyStart, index + 1));
      }
      curlyStart = null;
      continue;
    }
    if (char === "\"") {
      if (straightStart === null) straightStart = index;
      else {
        if (index > straightStart + 1) {
          const content = chars.slice(straightStart + 1, index).join("").trim();
          if (content) quotes.push(makeQuote(section, straightStart, index + 1));
        }
        straightStart = null;
      }
    }
  }

  return quotes.sort((left, right) => left.startOffset - right.startOffset || left.endOffset - right.endOffset);
}

export function extractDeterministicQuoteSpans(sections: NormalizedSection[]) {
  return sections
    .filter((section) => section.section_kind === "chapter" || section.section_kind === "document" || section.section_kind === "section")
    .flatMap(extractQuotesFromSection)
    .sort((left, right) => left.startOffset - right.startOffset || left.endOffset - right.endOffset);
}

function escapeRegex(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&");
}

function speechVerbSpans(section: NormalizedSection, verbs: string[]): VerbSpan[] {
  const alternatives = verbs.map((verb) => escapeRegex(verb)).join("|");
  const regex = new RegExp(`\\b(?:${alternatives})\\b`, "giu");
  const spans: VerbSpan[] = [];
  for (const match of section.normalized_text.matchAll(regex)) {
    if (match.index === undefined || !match[0]) continue;
    const localStart = codePointLength(section.normalized_text.slice(0, match.index));
    const localEnd = localStart + codePointLength(match[0]);
    spans.push({
      verb: match[0].toLocaleLowerCase("en-US"),
      startOffset: section.start_offset + localStart,
      endOffset: section.start_offset + localEnd,
    });
  }
  return spans;
}

function spanGap(left: { startOffset: number; endOffset: number }, right: { startOffset: number; endOffset: number }) {
  if (left.endOffset <= right.startOffset) return right.startOffset - left.endOffset;
  if (right.endOffset <= left.startOffset) return left.startOffset - right.endOffset;
  return 0;
}

function sideOfQuote(
  span: { startOffset: number; endOffset: number },
  quote: { startOffset: number; endOffset: number },
): "before" | "after" | null {
  if (span.endOffset <= quote.startOffset) return "before";
  if (span.startOffset >= quote.endOffset) return "after";
  return null;
}

function quoteDistance(
  span: { startOffset: number; endOffset: number },
  quote: { startOffset: number; endOffset: number },
) {
  const side = sideOfQuote(span, quote);
  if (side === "before") return quote.startOffset - span.endOffset;
  if (side === "after") return span.startOffset - quote.endOffset;
  return 0;
}

function chooseSpeaker(input: {
  quote: QuoteSpan;
  section: NormalizedSection;
  mentions: ResolvedIdentityMention[];
  verbs: VerbSpan[];
  config: DeterministicDialogueConfig;
}): Pick<DialogueQuotePrediction, "speakerKey" | "decisionReason"> {
  const candidates: AttributionCandidate[] = [];

  for (const mention of input.mentions) {
    if (mention.resolutionState !== "linked" || !mention.characterKey) continue;
    if (!input.config.includePronouns && mention.mentionKind === "pronoun") continue;
    const mentionSide = sideOfQuote(mention, input.quote);
    if (!mentionSide) continue;
    const mentionQuoteGap = quoteDistance(mention, input.quote);
    if (mentionQuoteGap > input.config.contextCodePoints) continue;

    for (const verb of input.verbs) {
      const verbSide = sideOfQuote(verb, input.quote);
      if (verbSide !== mentionSide) continue;
      const verbQuoteGap = quoteDistance(verb, input.quote);
      if (verbQuoteGap > input.config.contextCodePoints) continue;
      const verbMentionGap = spanGap(mention, verb);
      if (verbMentionGap > input.config.maxVerbMentionGapCodePoints) continue;

      const score = verbMentionGap * 8 + verbQuoteGap * 2 + mentionQuoteGap + (mention.mentionKind === "pronoun" ? 12 : 0);
      candidates.push({
        characterKey: mention.characterKey,
        score,
        side: mentionSide,
        verb: verb.verb,
        mention,
      });
    }
  }

  if (candidates.length === 0) {
    return { speakerKey: null, decisionReason: "no_speech_verb_character_pair" };
  }

  const bestByCharacter = new Map<string, AttributionCandidate>();
  for (const candidate of candidates) {
    const existing = bestByCharacter.get(candidate.characterKey);
    if (!existing || candidate.score < existing.score) bestByCharacter.set(candidate.characterKey, candidate);
  }
  const ranked = [...bestByCharacter.values()].sort((left, right) => left.score - right.score || left.characterKey.localeCompare(right.characterKey));
  const best = ranked[0]!;
  const second = ranked[1] ?? null;
  if (second && second.score - best.score < input.config.minimumScoreMargin) {
    return { speakerKey: null, decisionReason: "ambiguous_speech_verb_character_pair" };
  }

  return {
    speakerKey: best.characterKey,
    decisionReason: `speech_verb_linked_mention:${best.side}:${best.verb}:${best.mention.mentionKind}`,
  };
}

export function predictDeterministicDialogue(input: {
  sections: NormalizedSection[];
  normalizedInputFingerprint: string;
  identity: CharacterIdentityResult;
  config?: DeterministicDialogueConfig;
}): DialogueProviderResult {
  if (!/^[0-9a-f]{64}$/u.test(input.normalizedInputFingerprint)) {
    throw new Error("invalid_dialogue_baseline_input_fingerprint");
  }
  if (input.identity.normalizedInputFingerprint !== input.normalizedInputFingerprint) {
    throw new Error("dialogue_identity_input_fingerprint_mismatch");
  }
  const config = input.config ?? DEFAULT_DETERMINISTIC_DIALOGUE_CONFIG;
  validateConfig(config);
  const configFingerprint = deterministicDialogueConfigFingerprint(config);
  const quotes = extractDeterministicQuoteSpans(input.sections);
  const sectionsByKey = new Map(input.sections.map((section) => [section.stable_key, section]));
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

  const verbSpansBySection = new Map(
    input.sections.map((section) => [section.stable_key, speechVerbSpans(section, config.speechVerbs)]),
  );
  const predictedQuotes: DialogueQuotePrediction[] = quotes.map((quote) => {
    const section = sectionsByKey.get(quote.sectionKey);
    if (!section) throw new Error(`dialogue_quote_section_missing:${quote.sectionKey}`);
    const attribution = chooseSpeaker({
      quote,
      section,
      mentions: mentionsBySection.get(quote.sectionKey) ?? [],
      verbs: verbSpansBySection.get(quote.sectionKey) ?? [],
      config,
    });
    return { ...quote, ...attribution };
  });

  const provider = {
    name: "saga_deterministic_dialogue_baseline",
    model: null,
    revision: `${DIALOGUE_BASELINE_VERSION}:${configFingerprint.slice(0, 16)}`,
  };
  return {
    schemaVersion: "saga-dialogue-prediction-v1",
    provider,
    normalizedInputFingerprint: input.normalizedInputFingerprint,
    quotes: predictedQuotes,
    outputFingerprint: dialoguePredictionFingerprint({
      provider,
      normalizedInputFingerprint: input.normalizedInputFingerprint,
      quotes: predictedQuotes,
    }),
  };
}
