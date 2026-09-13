import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import type {
  EventTriggerEvidence,
  LocalLiteraryEvidenceBundle,
  SyntaxTokenEvidence,
} from "../local-analysis/types.js";
import type { EventProviderDescriptor } from "./event-evaluation.js";

export const EVENT_SEMANTIC_QUALIFIER_VERSION = "saga-event-semantic-qualifier-v1";

export const EVENT_MODAL_LEMMAS = [
  "can",
  "could",
  "may",
  "might",
  "must",
  "shall",
  "should",
  "will",
  "would",
] as const;

export const EVENT_CONDITIONAL_MARKERS = ["if", "unless"] as const;

const NEGATION_RELATION = "neg";
const AUXILIARY_RELATIONS = new Set(["aux", "auxpass"]);
const CONDITIONAL_MARKER_RELATION = "mark";
const MODAL_LEMMA_SET = new Set<string>(EVENT_MODAL_LEMMAS);
const CONDITIONAL_MARKER_SET = new Set<string>(EVENT_CONDITIONAL_MARKERS);

export type EventQualifierCueKind = "negation" | "modal_auxiliary" | "conditional_marker";

export type EventQualifierCue = {
  evidenceId: string;
  kind: EventQualifierCueKind;
  surfaceText: string;
  lemma: string;
  startOffset: number;
  endOffset: number;
  structuralLocator: string | null;
  sentenceId: number;
  tokenId: number;
  dependencyRelation: string;
};

export type EventSemanticQualifierEvidence = {
  eventEvidenceId: string;
  triggerTokenId: number;
  triggerStartOffset: number;
  triggerEndOffset: number;
  triggerStructuralLocator: string | null;
  polarity: "negated" | "undetermined";
  modality: "modalized" | "undetermined";
  realis: "irrealis_cued" | "undetermined";
  cues: EventQualifierCue[];
};

export type EventSemanticQualifierResult = {
  schemaVersion: typeof EVENT_SEMANTIC_QUALIFIER_VERSION;
  provider: EventProviderDescriptor;
  sourceProvider: EventProviderDescriptor;
  normalizedInputFingerprint: string;
  configurationFingerprint: string;
  events: EventSemanticQualifierEvidence[];
  outputFingerprint: string;
};

type SyntaxIndex = {
  byId: Map<number, SyntaxTokenEvidence>;
  children: Map<number, SyntaxTokenEvidence[]>;
};

function validateFingerprint(value: string, errorCode: string) {
  if (!/^[0-9a-f]{64}$/u.test(value)) throw new Error(errorCode);
}

function normalizeLemma(value: string) {
  return value.trim().toLocaleLowerCase("en-US");
}

function syntaxIndex(tokens: SyntaxTokenEvidence[]): SyntaxIndex {
  const byId = new Map<number, SyntaxTokenEvidence>();
  const children = new Map<number, SyntaxTokenEvidence[]>();

  for (const token of tokens) {
    if (byId.has(token.tokenId)) {
      throw new Error(`event_qualifier_duplicate_syntax_token:${token.tokenId}`);
    }
    byId.set(token.tokenId, token);
  }

  for (const token of tokens) {
    const head = byId.get(token.syntacticHeadTokenId);
    if (!head) throw new Error(`event_qualifier_missing_syntax_head:${token.evidenceId}`);
    if (head.sentenceId !== token.sentenceId) {
      throw new Error(`event_qualifier_cross_sentence_syntax_head:${token.evidenceId}`);
    }
    if (token.tokenId === token.syntacticHeadTokenId) continue;
    const current = children.get(token.syntacticHeadTokenId) ?? [];
    current.push(token);
    children.set(token.syntacticHeadTokenId, current);
  }

  for (const group of children.values()) {
    group.sort((left, right) => left.tokenId - right.tokenId || left.evidenceId.localeCompare(right.evidenceId));
  }

  return { byId, children };
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

function directChildren(index: SyntaxIndex, tokenId: number) {
  return index.children.get(tokenId) ?? [];
}

function cueFromToken(token: SyntaxTokenEvidence, kind: EventQualifierCueKind): EventQualifierCue {
  return {
    evidenceId: token.evidenceId,
    kind,
    surfaceText: token.surfaceText,
    lemma: token.lemma,
    startOffset: token.startOffset,
    endOffset: token.endOffset,
    structuralLocator: token.structuralLocator,
    sentenceId: token.sentenceId,
    tokenId: token.tokenId,
    dependencyRelation: token.dependencyRelation,
  };
}

function qualifierCues(triggerToken: SyntaxTokenEvidence, index: SyntaxIndex) {
  const children = directChildren(index, triggerToken.tokenId);
  const auxiliaries = children.filter((token) => AUXILIARY_RELATIONS.has(token.dependencyRelation));
  const cues: EventQualifierCue[] = [];

  for (const child of children) {
    if (child.dependencyRelation === NEGATION_RELATION) {
      cues.push(cueFromToken(child, "negation"));
    }
    if (AUXILIARY_RELATIONS.has(child.dependencyRelation) && MODAL_LEMMA_SET.has(normalizeLemma(child.lemma))) {
      cues.push(cueFromToken(child, "modal_auxiliary"));
    }
    if (
      child.dependencyRelation === CONDITIONAL_MARKER_RELATION
      && CONDITIONAL_MARKER_SET.has(normalizeLemma(child.lemma))
    ) {
      cues.push(cueFromToken(child, "conditional_marker"));
    }
  }

  for (const auxiliary of auxiliaries) {
    for (const child of directChildren(index, auxiliary.tokenId)) {
      if (child.dependencyRelation === NEGATION_RELATION) {
        cues.push(cueFromToken(child, "negation"));
      }
    }
  }

  const deduplicated = new Map<string, EventQualifierCue>();
  for (const cue of cues) deduplicated.set(`${cue.kind}:${cue.evidenceId}`, cue);
  return [...deduplicated.values()].sort((left, right) =>
    left.tokenId - right.tokenId
    || left.kind.localeCompare(right.kind)
    || left.evidenceId.localeCompare(right.evidenceId)
  );
}

export function eventSemanticQualifierFingerprint(input: {
  provider: EventProviderDescriptor;
  sourceProvider: EventProviderDescriptor;
  normalizedInputFingerprint: string;
  configurationFingerprint: string;
  events: EventSemanticQualifierEvidence[];
}) {
  return sha256Hex(canonicalJson(input));
}

export function deriveEventSemanticQualifiers(input: {
  normalizedInputFingerprint: string;
  literaryEvidence: LocalLiteraryEvidenceBundle;
}): EventSemanticQualifierResult {
  validateFingerprint(input.normalizedInputFingerprint, "invalid_event_qualifier_input_fingerprint");
  if (input.literaryEvidence.normalizedInputFingerprint !== input.normalizedInputFingerprint) {
    throw new Error("event_qualifier_provider_input_fingerprint_mismatch");
  }
  if (!input.literaryEvidence.syntaxTokens) {
    throw new Error("event_qualifier_syntax_evidence_missing");
  }

  const syntax = syntaxIndex(input.literaryEvidence.syntaxTokens);
  const sourceProvider: EventProviderDescriptor = {
    name: input.literaryEvidence.provider.name,
    model: input.literaryEvidence.provider.model,
    revision: input.literaryEvidence.provider.revision,
  };
  const configurationFingerprint = sha256Hex(canonicalJson({
    version: EVENT_SEMANTIC_QUALIFIER_VERSION,
    sourceProvider,
    negation: {
      relation: NEGATION_RELATION,
      scope: "trigger_or_direct_auxiliary_child",
    },
    modality: {
      auxiliaryRelations: [...AUXILIARY_RELATIONS].sort(),
      lemmas: [...EVENT_MODAL_LEMMAS],
    },
    irrealis: {
      modalAuxiliaryImpliesCue: true,
      conditionalRelation: CONDITIONAL_MARKER_RELATION,
      conditionalMarkers: [...EVENT_CONDITIONAL_MARKERS],
      unmarkedState: "undetermined",
    },
    traversal: "same_sentence_direct_dependency_only",
  }));
  const provider: EventProviderDescriptor = {
    name: "saga_event_semantic_qualifier",
    model: null,
    revision: `${EVENT_SEMANTIC_QUALIFIER_VERSION}:${configurationFingerprint.slice(0, 16)}`,
  };

  const events = input.literaryEvidence.eventTriggers.map((trigger) => {
    const token = syntax.byId.get(trigger.tokenId);
    if (!token) throw new Error(`event_qualifier_trigger_token_missing:${trigger.evidenceId}`);
    if (!sameTriggerAndSyntax(trigger, token)) {
      throw new Error(`event_qualifier_trigger_syntax_mismatch:${trigger.evidenceId}`);
    }

    const cues = qualifierCues(token, syntax);
    const hasNegation = cues.some((cue) => cue.kind === "negation");
    const hasModal = cues.some((cue) => cue.kind === "modal_auxiliary");
    const hasConditional = cues.some((cue) => cue.kind === "conditional_marker");

    return {
      eventEvidenceId: trigger.evidenceId,
      triggerTokenId: trigger.tokenId,
      triggerStartOffset: trigger.startOffset,
      triggerEndOffset: trigger.endOffset,
      triggerStructuralLocator: trigger.structuralLocator,
      polarity: hasNegation ? "negated" as const : "undetermined" as const,
      modality: hasModal ? "modalized" as const : "undetermined" as const,
      realis: hasModal || hasConditional ? "irrealis_cued" as const : "undetermined" as const,
      cues,
    };
  }).sort((left, right) =>
    left.triggerStartOffset - right.triggerStartOffset
    || left.triggerEndOffset - right.triggerEndOffset
    || left.eventEvidenceId.localeCompare(right.eventEvidenceId)
  );

  const semantic = {
    provider,
    sourceProvider,
    normalizedInputFingerprint: input.normalizedInputFingerprint,
    configurationFingerprint,
    events,
  };

  return {
    schemaVersion: EVENT_SEMANTIC_QUALIFIER_VERSION,
    ...semantic,
    outputFingerprint: eventSemanticQualifierFingerprint(semantic),
  };
}

export function validateEventSemanticQualifierResult(result: EventSemanticQualifierResult) {
  if (result.schemaVersion !== EVENT_SEMANTIC_QUALIFIER_VERSION) {
    throw new Error("unsupported_event_qualifier_result");
  }
  validateFingerprint(result.normalizedInputFingerprint, "invalid_event_qualifier_result_input_fingerprint");
  validateFingerprint(result.configurationFingerprint, "invalid_event_qualifier_configuration_fingerprint");
  validateFingerprint(result.outputFingerprint, "invalid_event_qualifier_output_fingerprint");

  const eventIds = new Set<string>();
  for (const event of result.events) {
    if (!event.eventEvidenceId.trim()) throw new Error("invalid_event_qualifier_event_evidence_id");
    if (eventIds.has(event.eventEvidenceId)) {
      throw new Error(`duplicate_event_qualifier_event:${event.eventEvidenceId}`);
    }
    eventIds.add(event.eventEvidenceId);
    if (!Number.isSafeInteger(event.triggerTokenId) || event.triggerTokenId < 0) {
      throw new Error(`invalid_event_qualifier_trigger_token:${event.eventEvidenceId}`);
    }
    if (!Number.isSafeInteger(event.triggerStartOffset) || event.triggerStartOffset < 0) {
      throw new Error(`invalid_event_qualifier_start_offset:${event.eventEvidenceId}`);
    }
    if (!Number.isSafeInteger(event.triggerEndOffset) || event.triggerEndOffset <= event.triggerStartOffset) {
      throw new Error(`invalid_event_qualifier_end_offset:${event.eventEvidenceId}`);
    }
    const cueIds = new Set<string>();
    for (const cue of event.cues) {
      const key = `${cue.kind}:${cue.evidenceId}`;
      if (cueIds.has(key)) throw new Error(`duplicate_event_qualifier_cue:${event.eventEvidenceId}:${key}`);
      cueIds.add(key);
      if (cue.sentenceId < 0 || cue.tokenId < 0 || cue.endOffset <= cue.startOffset) {
        throw new Error(`invalid_event_qualifier_cue:${event.eventEvidenceId}:${cue.evidenceId}`);
      }
    }
    if (event.polarity === "negated" && !event.cues.some((cue) => cue.kind === "negation")) {
      throw new Error(`event_qualifier_negation_without_cue:${event.eventEvidenceId}`);
    }
    if (event.modality === "modalized" && !event.cues.some((cue) => cue.kind === "modal_auxiliary")) {
      throw new Error(`event_qualifier_modality_without_cue:${event.eventEvidenceId}`);
    }
    if (
      event.realis === "irrealis_cued"
      && !event.cues.some((cue) => cue.kind === "modal_auxiliary" || cue.kind === "conditional_marker")
    ) {
      throw new Error(`event_qualifier_irrealis_without_cue:${event.eventEvidenceId}`);
    }
  }

  const expected = eventSemanticQualifierFingerprint({
    provider: result.provider,
    sourceProvider: result.sourceProvider,
    normalizedInputFingerprint: result.normalizedInputFingerprint,
    configurationFingerprint: result.configurationFingerprint,
    events: result.events,
  });
  if (expected !== result.outputFingerprint) throw new Error("event_qualifier_output_fingerprint_mismatch");
}
