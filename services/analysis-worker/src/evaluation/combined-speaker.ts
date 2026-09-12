import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import type { NormalizedSection } from "../ingestion/types.js";
import type { CharacterIdentityResult } from "../identity/types.js";
import type { LocalLiteraryEvidenceBundle, QuoteSpeakerEvidence } from "../local-analysis/types.js";
import {
  DEFAULT_DETERMINISTIC_DIALOGUE_CONFIG,
  deterministicDialogueConfigFingerprint,
  predictDeterministicDialogue,
  type DeterministicDialogueConfig,
} from "./dialogue-deterministic-baseline.js";
import {
  dialoguePredictionFingerprint,
  type DialogueProviderResult,
  type DialogueQuotePrediction,
} from "./dialogue-evaluation.js";

export const COMBINED_SPEAKER_VERSION = "saga-dialogue-combined-speaker-v1";

function spanKey(startOffset: number, endOffset: number) {
  return `${startOffset}:${endOffset}`;
}

function exactIdentityBySpan(identity: CharacterIdentityResult) {
  const candidates = new Map<string, Set<string>>();
  for (const mention of identity.mentions) {
    if (mention.resolutionState !== "linked" || !mention.characterKey) continue;
    const key = spanKey(mention.startOffset, mention.endOffset);
    const current = candidates.get(key) ?? new Set<string>();
    current.add(mention.characterKey);
    candidates.set(key, current);
  }
  return new Map(
    [...candidates.entries()].map(([key, characterKeys]) => [
      key,
      characterKeys.size === 1 ? [...characterKeys][0]! : null,
    ]),
  );
}

function exactProviderQuotes(evidence: LocalLiteraryEvidenceBundle) {
  const bySpan = new Map<string, QuoteSpeakerEvidence[]>();
  for (const quote of evidence.quotes) {
    const key = spanKey(quote.startOffset, quote.endOffset);
    const current = bySpan.get(key) ?? [];
    current.push(quote);
    bySpan.set(key, current);
  }
  return bySpan;
}

function providerSpeaker(input: {
  quote: DialogueQuotePrediction;
  providerQuotes: Map<string, QuoteSpeakerEvidence[]>;
  identityBySpan: Map<string, string | null>;
}) {
  const matches = input.providerQuotes.get(spanKey(input.quote.startOffset, input.quote.endOffset)) ?? [];
  if (matches.length !== 1) {
    return {
      speakerKey: null as string | null,
      reason: matches.length === 0 ? "provider_quote_no_exact_match" : "provider_quote_exact_match_ambiguous",
    };
  }
  const evidence = matches[0]!;
  if (evidence.speakerStartOffset === null || evidence.speakerEndOffset === null) {
    return { speakerKey: null as string | null, reason: "provider_speaker_span_missing" };
  }
  const speakerKey = input.identityBySpan.get(spanKey(evidence.speakerStartOffset, evidence.speakerEndOffset)) ?? null;
  if (speakerKey === null) {
    return { speakerKey: null as string | null, reason: "provider_speaker_not_uniquely_resolved" };
  }
  return { speakerKey, reason: "provider_speaker_exact_quote_resolved_identity" };
}

function fuseSpeaker(input: {
  deterministic: DialogueQuotePrediction;
  providerSpeakerKey: string | null;
  providerReason: string;
}): Pick<DialogueQuotePrediction, "speakerKey" | "decisionReason"> {
  const deterministicSpeakerKey = input.deterministic.speakerKey;
  if (deterministicSpeakerKey && input.providerSpeakerKey) {
    if (deterministicSpeakerKey === input.providerSpeakerKey) {
      return {
        speakerKey: deterministicSpeakerKey,
        decisionReason: `combined_agreement:${input.deterministic.decisionReason}:${input.providerReason}`,
      };
    }
    return {
      speakerKey: null,
      decisionReason: `combined_conflict_unresolved:${input.deterministic.decisionReason}:${input.providerReason}`,
    };
  }
  if (input.providerSpeakerKey) {
    return {
      speakerKey: input.providerSpeakerKey,
      decisionReason: `combined_provider_fallback:${input.providerReason}`,
    };
  }
  if (deterministicSpeakerKey) {
    return {
      speakerKey: deterministicSpeakerKey,
      decisionReason: `combined_deterministic_only:${input.deterministic.decisionReason}:${input.providerReason}`,
    };
  }
  return {
    speakerKey: null,
    decisionReason: `combined_unresolved:${input.deterministic.decisionReason}:${input.providerReason}`,
  };
}

export function predictCombinedSpeakerDialogue(input: {
  sections: NormalizedSection[];
  normalizedInputFingerprint: string;
  identity: CharacterIdentityResult;
  literaryEvidence: LocalLiteraryEvidenceBundle;
  deterministicConfig?: DeterministicDialogueConfig;
}): DialogueProviderResult {
  if (!/^[0-9a-f]{64}$/u.test(input.normalizedInputFingerprint)) {
    throw new Error("invalid_combined_speaker_input_fingerprint");
  }
  if (input.identity.normalizedInputFingerprint !== input.normalizedInputFingerprint) {
    throw new Error("combined_speaker_identity_input_fingerprint_mismatch");
  }
  if (input.literaryEvidence.normalizedInputFingerprint !== input.normalizedInputFingerprint) {
    throw new Error("combined_speaker_provider_input_fingerprint_mismatch");
  }

  const deterministicConfig = input.deterministicConfig ?? DEFAULT_DETERMINISTIC_DIALOGUE_CONFIG;
  const deterministic = predictDeterministicDialogue({
    sections: input.sections,
    normalizedInputFingerprint: input.normalizedInputFingerprint,
    identity: input.identity,
    config: deterministicConfig,
  });
  const providerQuotes = exactProviderQuotes(input.literaryEvidence);
  const identityBySpan = exactIdentityBySpan(input.identity);

  const quotes = deterministic.quotes.map((quote) => {
    const provider = providerSpeaker({ quote, providerQuotes, identityBySpan });
    const fused = fuseSpeaker({
      deterministic: quote,
      providerSpeakerKey: provider.speakerKey,
      providerReason: provider.reason,
    });
    return { ...quote, ...fused };
  });

  const configFingerprint = sha256Hex(canonicalJson({
    version: COMBINED_SPEAKER_VERSION,
    matching: "exact_quote_span_exact_speaker_span",
    conflictPolicy: "unresolved",
    providerOnlyPolicy: "fallback_when_deterministic_unresolved",
    deterministicConfigFingerprint: deterministicDialogueConfigFingerprint(deterministicConfig),
    literaryProvider: input.literaryEvidence.provider,
  }));
  const provider = {
    name: "saga_combined_speaker",
    model: null,
    revision: `${COMBINED_SPEAKER_VERSION}:${configFingerprint.slice(0, 16)}`,
  };
  return {
    schemaVersion: "saga-dialogue-prediction-v1",
    provider,
    normalizedInputFingerprint: input.normalizedInputFingerprint,
    quotes,
    outputFingerprint: dialoguePredictionFingerprint({
      provider,
      normalizedInputFingerprint: input.normalizedInputFingerprint,
      quotes,
    }),
  };
}
