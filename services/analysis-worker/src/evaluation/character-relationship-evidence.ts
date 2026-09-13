import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import type { CharacterIdentityResult, ResolvedIdentityMention } from "../identity/types.js";
import type { LocalLiteraryEvidenceBundle, SyntaxTokenEvidence } from "../local-analysis/types.js";

export const CHARACTER_RELATIONSHIP_EVIDENCE_VERSION = "saga-character-relationship-evidence-v1";

export const CHARACTER_RELATIONSHIP_PREDICATES = [
  "love",
  "hate",
  "trust",
  "distrust",
  "marry",
  "divorce",
  "befriend",
  "betray",
] as const;

export const RELATIONSHIP_MODAL_LEMMAS = [
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

export const RELATIONSHIP_CONDITIONAL_MARKERS = ["if", "unless"] as const;

export type CharacterRelationshipPredicate = typeof CHARACTER_RELATIONSHIP_PREDICATES[number];
export type CharacterRelationshipVoice = "active" | "passive";
export type CharacterRelationshipQualifierKind = "negation" | "modal_auxiliary" | "conditional_marker";

export type CharacterRelationshipQualifierCue = {
  evidenceId: string;
  kind: CharacterRelationshipQualifierKind;
  surfaceText: string;
  lemma: string;
  startOffset: number;
  endOffset: number;
  structuralLocator: string | null;
  sentenceId: number;
  tokenId: number;
  dependencyRelation: string;
};

export type CharacterRelationshipObservation = {
  observationId: string;
  subjectCharacterKey: string;
  objectCharacterKey: string;
  predicate: CharacterRelationshipPredicate;
  predicateEvidenceId: string;
  predicateSurfaceText: string;
  predicateStartOffset: number;
  predicateEndOffset: number;
  structuralLocator: string | null;
  sentenceId: number;
  predicateTokenId: number;
  voice: CharacterRelationshipVoice;
  subjectMentionEvidenceId: string;
  objectMentionEvidenceId: string;
  polarity: "negated" | "unmarked";
  modality: "modalized" | "unmarked";
  conditionality: "conditional_cued" | "unmarked";
  qualifierCues: CharacterRelationshipQualifierCue[];
};

export type CharacterRelationshipSourceOrderLedgerEntry = {
  ledgerKey: string;
  subjectCharacterKey: string;
  objectCharacterKey: string;
  predicate: CharacterRelationshipPredicate;
  observationIds: string[];
  observationCount: number;
  firstSourceOffset: number;
  lastSourceOffset: number;
};

export type CharacterRelationshipEvidenceResult = {
  schemaVersion: typeof CHARACTER_RELATIONSHIP_EVIDENCE_VERSION;
  provider: {
    name: string;
    model: string | null;
    revision: string;
  };
  sourceProvider: {
    name: string;
    model: string | null;
    revision: string;
  };
  identityResolverVersion: string;
  identityOutputFingerprint: string;
  normalizedInputFingerprint: string;
  configurationFingerprint: string;
  observations: CharacterRelationshipObservation[];
  sourceOrderLedger: CharacterRelationshipSourceOrderLedgerEntry[];
  outputFingerprint: string;
};

type SyntaxIndex = {
  byId: Map<number, SyntaxTokenEvidence>;
  children: Map<number, SyntaxTokenEvidence[]>;
};

type GroundedCharacter = {
  characterKey: string;
  evidenceId: string;
};

const PREDICATE_SET = new Set<string>(CHARACTER_RELATIONSHIP_PREDICATES);
const MODAL_LEMMA_SET = new Set<string>(RELATIONSHIP_MODAL_LEMMAS);
const CONDITIONAL_MARKER_SET = new Set<string>(RELATIONSHIP_CONDITIONAL_MARKERS);
const AUXILIARY_RELATIONS = new Set(["aux", "auxpass"]);

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
    if (byId.has(token.tokenId)) throw new Error(`relationship_duplicate_syntax_token:${token.tokenId}`);
    byId.set(token.tokenId, token);
  }
  for (const token of tokens) {
    const head = byId.get(token.syntacticHeadTokenId);
    if (!head) throw new Error(`relationship_missing_syntax_head:${token.evidenceId}`);
    if (head.sentenceId !== token.sentenceId) {
      throw new Error(`relationship_cross_sentence_syntax_head:${token.evidenceId}`);
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

function eligibleMention(mention: ResolvedIdentityMention) {
  return mention.resolutionState === "linked" && mention.characterKey !== null;
}

function groundToken(token: SyntaxTokenEvidence, identity: CharacterIdentityResult): GroundedCharacter | null {
  const covering = identity.mentions
    .filter(eligibleMention)
    .filter((mention) => mention.startOffset <= token.startOffset && mention.endOffset >= token.endOffset)
    .filter((mention) => mention.structuralLocator === token.structuralLocator);
  const keys = [...new Set(covering.map((mention) => mention.characterKey!))];
  if (keys.length !== 1) return null;
  const characterKey = keys[0]!;
  const evidence = covering
    .filter((mention) => mention.characterKey === characterKey)
    .sort((left, right) =>
      (left.endOffset - left.startOffset) - (right.endOffset - right.startOffset)
      || left.startOffset - right.startOffset
      || left.evidenceId.localeCompare(right.evidenceId)
    )[0];
  return evidence ? { characterKey, evidenceId: evidence.evidenceId } : null;
}

function singleGroundedRole(tokens: SyntaxTokenEvidence[], identity: CharacterIdentityResult) {
  if (tokens.length !== 1) return null;
  return groundToken(tokens[0]!, identity);
}

function directChildren(index: SyntaxIndex, tokenId: number, relation?: string) {
  const children = index.children.get(tokenId) ?? [];
  return relation === undefined ? children : children.filter((token) => token.dependencyRelation === relation);
}

function passiveAgentObjects(index: SyntaxIndex, predicateTokenId: number) {
  const agents = directChildren(index, predicateTokenId, "agent");
  if (agents.length !== 1) return [];
  return directChildren(index, agents[0]!.tokenId, "pobj");
}

function cueFromToken(token: SyntaxTokenEvidence, kind: CharacterRelationshipQualifierKind): CharacterRelationshipQualifierCue {
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

function qualifierCues(predicate: SyntaxTokenEvidence, index: SyntaxIndex) {
  const children = directChildren(index, predicate.tokenId);
  const auxiliaries = children.filter((token) => AUXILIARY_RELATIONS.has(token.dependencyRelation));
  const cues: CharacterRelationshipQualifierCue[] = [];
  for (const child of children) {
    const lemma = normalizeLemma(child.lemma);
    if (child.dependencyRelation === "neg") cues.push(cueFromToken(child, "negation"));
    if (AUXILIARY_RELATIONS.has(child.dependencyRelation) && MODAL_LEMMA_SET.has(lemma)) {
      cues.push(cueFromToken(child, "modal_auxiliary"));
    }
    if (child.dependencyRelation === "mark" && CONDITIONAL_MARKER_SET.has(lemma)) {
      cues.push(cueFromToken(child, "conditional_marker"));
    }
  }
  for (const auxiliary of auxiliaries) {
    for (const child of directChildren(index, auxiliary.tokenId)) {
      if (child.dependencyRelation === "neg") cues.push(cueFromToken(child, "negation"));
    }
  }
  const deduped = new Map<string, CharacterRelationshipQualifierCue>();
  for (const cue of cues) deduped.set(`${cue.kind}:${cue.evidenceId}`, cue);
  return [...deduped.values()].sort((left, right) =>
    left.tokenId - right.tokenId
    || left.kind.localeCompare(right.kind)
    || left.evidenceId.localeCompare(right.evidenceId)
  );
}

function observationForPredicate(input: {
  predicate: SyntaxTokenEvidence;
  index: SyntaxIndex;
  identity: CharacterIdentityResult;
}): CharacterRelationshipObservation | null {
  const lemma = normalizeLemma(input.predicate.lemma);
  if (!PREDICATE_SET.has(lemma)) return null;

  const activeSubjects = directChildren(input.index, input.predicate.tokenId, "nsubj");
  const activeObjects = directChildren(input.index, input.predicate.tokenId, "dobj");
  const passivePatients = directChildren(input.index, input.predicate.tokenId, "nsubjpass");
  const passiveAgents = passiveAgentObjects(input.index, input.predicate.tokenId);

  const activeShape = activeSubjects.length > 0 || activeObjects.length > 0;
  const passiveShape = passivePatients.length > 0 || passiveAgents.length > 0;
  if (activeShape && passiveShape) return null;

  let voice: CharacterRelationshipVoice;
  let subject: GroundedCharacter | null;
  let object: GroundedCharacter | null;
  if (passiveShape) {
    voice = "passive";
    subject = singleGroundedRole(passiveAgents, input.identity);
    object = singleGroundedRole(passivePatients, input.identity);
  } else {
    voice = "active";
    subject = singleGroundedRole(activeSubjects, input.identity);
    object = singleGroundedRole(activeObjects, input.identity);
  }
  if (!subject || !object || subject.characterKey === object.characterKey) return null;

  const qualifierCuesForPredicate = qualifierCues(input.predicate, input.index);
  const hasNegation = qualifierCuesForPredicate.some((cue) => cue.kind === "negation");
  const hasModal = qualifierCuesForPredicate.some((cue) => cue.kind === "modal_auxiliary");
  const hasConditional = qualifierCuesForPredicate.some((cue) => cue.kind === "conditional_marker");
  const predicate = lemma as CharacterRelationshipPredicate;
  const observationId = `relationship-${sha256Hex(canonicalJson({
    subjectCharacterKey: subject.characterKey,
    objectCharacterKey: object.characterKey,
    predicate,
    predicateEvidenceId: input.predicate.evidenceId,
    predicateStartOffset: input.predicate.startOffset,
    predicateEndOffset: input.predicate.endOffset,
    structuralLocator: input.predicate.structuralLocator,
  })).slice(0, 24)}`;

  return {
    observationId,
    subjectCharacterKey: subject.characterKey,
    objectCharacterKey: object.characterKey,
    predicate,
    predicateEvidenceId: input.predicate.evidenceId,
    predicateSurfaceText: input.predicate.surfaceText,
    predicateStartOffset: input.predicate.startOffset,
    predicateEndOffset: input.predicate.endOffset,
    structuralLocator: input.predicate.structuralLocator,
    sentenceId: input.predicate.sentenceId,
    predicateTokenId: input.predicate.tokenId,
    voice,
    subjectMentionEvidenceId: subject.evidenceId,
    objectMentionEvidenceId: object.evidenceId,
    polarity: hasNegation ? "negated" : "unmarked",
    modality: hasModal ? "modalized" : "unmarked",
    conditionality: hasConditional ? "conditional_cued" : "unmarked",
    qualifierCues: qualifierCuesForPredicate,
  };
}

function buildSourceOrderLedger(observations: CharacterRelationshipObservation[]) {
  const groups = new Map<string, CharacterRelationshipObservation[]>();
  for (const observation of observations) {
    const key = canonicalJson({
      subjectCharacterKey: observation.subjectCharacterKey,
      objectCharacterKey: observation.objectCharacterKey,
      predicate: observation.predicate,
    });
    const group = groups.get(key) ?? [];
    group.push(observation);
    groups.set(key, group);
  }

  return [...groups.entries()].map(([groupKey, group]) => {
    const ordered = [...group].sort((left, right) =>
      left.predicateStartOffset - right.predicateStartOffset
      || left.predicateEndOffset - right.predicateEndOffset
      || left.observationId.localeCompare(right.observationId)
    );
    const first = ordered[0]!;
    const last = ordered.at(-1)!;
    return {
      ledgerKey: `relationship-ledger-${sha256Hex(groupKey).slice(0, 24)}`,
      subjectCharacterKey: first.subjectCharacterKey,
      objectCharacterKey: first.objectCharacterKey,
      predicate: first.predicate,
      observationIds: ordered.map((observation) => observation.observationId),
      observationCount: ordered.length,
      firstSourceOffset: first.predicateStartOffset,
      lastSourceOffset: last.predicateStartOffset,
    } satisfies CharacterRelationshipSourceOrderLedgerEntry;
  }).sort((left, right) =>
    left.firstSourceOffset - right.firstSourceOffset
    || left.lastSourceOffset - right.lastSourceOffset
    || left.ledgerKey.localeCompare(right.ledgerKey)
  );
}

export function characterRelationshipEvidenceFingerprint(input: {
  provider: CharacterRelationshipEvidenceResult["provider"];
  sourceProvider: CharacterRelationshipEvidenceResult["sourceProvider"];
  identityResolverVersion: string;
  identityOutputFingerprint: string;
  normalizedInputFingerprint: string;
  configurationFingerprint: string;
  observations: CharacterRelationshipObservation[];
  sourceOrderLedger: CharacterRelationshipSourceOrderLedgerEntry[];
}) {
  return sha256Hex(canonicalJson(input));
}

export function deriveCharacterRelationshipEvidence(input: {
  normalizedInputFingerprint: string;
  identity: CharacterIdentityResult;
  literaryEvidence: LocalLiteraryEvidenceBundle;
}): CharacterRelationshipEvidenceResult {
  validateFingerprint(input.normalizedInputFingerprint, "invalid_relationship_input_fingerprint");
  validateFingerprint(input.identity.outputFingerprint, "invalid_relationship_identity_output_fingerprint");
  if (input.identity.normalizedInputFingerprint !== input.normalizedInputFingerprint) {
    throw new Error("relationship_identity_input_fingerprint_mismatch");
  }
  if (input.literaryEvidence.normalizedInputFingerprint !== input.normalizedInputFingerprint) {
    throw new Error("relationship_provider_input_fingerprint_mismatch");
  }
  if (!input.literaryEvidence.syntaxTokens) throw new Error("relationship_syntax_evidence_missing");

  const index = syntaxIndex(input.literaryEvidence.syntaxTokens);
  const sourceProvider = {
    name: input.literaryEvidence.provider.name,
    model: input.literaryEvidence.provider.model,
    revision: input.literaryEvidence.provider.revision,
  };
  const configurationFingerprint = sha256Hex(canonicalJson({
    version: CHARACTER_RELATIONSHIP_EVIDENCE_VERSION,
    predicates: [...CHARACTER_RELATIONSHIP_PREDICATES],
    activeRoles: { subject: "nsubj", object: "dobj" },
    passiveRoles: { subject: "agent->pobj", object: "nsubjpass" },
    identityGrounding: "exact_structural_locator_unique_linked_covering_mention",
    multipleRoleCandidates: "reject",
    selfRelations: "reject",
    reciprocalInference: false,
    cooccurrenceRelationshipInference: false,
    eventCoparticipationRelationshipInference: false,
    qualifiers: {
      negation: "neg child of predicate or direct auxiliary",
      modal: [...RELATIONSHIP_MODAL_LEMMAS],
      conditional: [...RELATIONSHIP_CONDITIONAL_MARKERS],
    },
    ledgerSemantics: "source_order_observation_history_only_no_persistence_or_story_time",
  }));
  const provider = {
    name: "saga_explicit_character_relationship",
    model: null,
    revision: `${CHARACTER_RELATIONSHIP_EVIDENCE_VERSION}:${configurationFingerprint.slice(0, 16)}`,
  };

  const observations = input.literaryEvidence.syntaxTokens
    .map((predicate) => observationForPredicate({ predicate, index, identity: input.identity }))
    .filter((value): value is CharacterRelationshipObservation => value !== null)
    .sort((left, right) =>
      left.predicateStartOffset - right.predicateStartOffset
      || left.predicateEndOffset - right.predicateEndOffset
      || left.observationId.localeCompare(right.observationId)
    );
  const sourceOrderLedger = buildSourceOrderLedger(observations);
  const semantic = {
    provider,
    sourceProvider,
    identityResolverVersion: input.identity.resolverVersion,
    identityOutputFingerprint: input.identity.outputFingerprint,
    normalizedInputFingerprint: input.normalizedInputFingerprint,
    configurationFingerprint,
    observations,
    sourceOrderLedger,
  };
  return {
    schemaVersion: CHARACTER_RELATIONSHIP_EVIDENCE_VERSION,
    ...semantic,
    outputFingerprint: characterRelationshipEvidenceFingerprint(semantic),
  };
}

export function validateCharacterRelationshipEvidenceResult(result: CharacterRelationshipEvidenceResult) {
  if (result.schemaVersion !== CHARACTER_RELATIONSHIP_EVIDENCE_VERSION) {
    throw new Error("unsupported_relationship_evidence_result");
  }
  validateFingerprint(result.normalizedInputFingerprint, "invalid_relationship_result_input_fingerprint");
  validateFingerprint(result.identityOutputFingerprint, "invalid_relationship_result_identity_fingerprint");
  validateFingerprint(result.configurationFingerprint, "invalid_relationship_configuration_fingerprint");
  validateFingerprint(result.outputFingerprint, "invalid_relationship_output_fingerprint");

  const observationsById = new Map<string, CharacterRelationshipObservation>();
  for (const observation of result.observations) {
    if (!observation.observationId.trim()) throw new Error("invalid_relationship_observation_id");
    if (observationsById.has(observation.observationId)) {
      throw new Error(`duplicate_relationship_observation:${observation.observationId}`);
    }
    observationsById.set(observation.observationId, observation);
    if (!observation.subjectCharacterKey.trim() || !observation.objectCharacterKey.trim()) {
      throw new Error(`invalid_relationship_character_key:${observation.observationId}`);
    }
    if (observation.subjectCharacterKey === observation.objectCharacterKey) {
      throw new Error(`relationship_self_observation:${observation.observationId}`);
    }
    if (!PREDICATE_SET.has(observation.predicate)) {
      throw new Error(`unsupported_relationship_predicate:${observation.observationId}`);
    }
    if (!Number.isSafeInteger(observation.predicateStartOffset) || observation.predicateStartOffset < 0) {
      throw new Error(`invalid_relationship_start_offset:${observation.observationId}`);
    }
    if (!Number.isSafeInteger(observation.predicateEndOffset) || observation.predicateEndOffset <= observation.predicateStartOffset) {
      throw new Error(`invalid_relationship_end_offset:${observation.observationId}`);
    }
    const cueIds = new Set<string>();
    for (const cue of observation.qualifierCues) {
      const key = `${cue.kind}:${cue.evidenceId}`;
      if (cueIds.has(key)) throw new Error(`duplicate_relationship_qualifier_cue:${observation.observationId}:${key}`);
      cueIds.add(key);
      if (cue.sentenceId !== observation.sentenceId) {
        throw new Error(`relationship_qualifier_sentence_mismatch:${observation.observationId}:${cue.evidenceId}`);
      }
      if (cue.structuralLocator !== observation.structuralLocator) {
        throw new Error(`relationship_qualifier_locator_mismatch:${observation.observationId}:${cue.evidenceId}`);
      }
    }
    if (observation.polarity === "negated" && !observation.qualifierCues.some((cue) => cue.kind === "negation")) {
      throw new Error(`relationship_negation_without_cue:${observation.observationId}`);
    }
    if (observation.modality === "modalized" && !observation.qualifierCues.some((cue) => cue.kind === "modal_auxiliary")) {
      throw new Error(`relationship_modality_without_cue:${observation.observationId}`);
    }
    if (observation.conditionality === "conditional_cued" && !observation.qualifierCues.some((cue) => cue.kind === "conditional_marker")) {
      throw new Error(`relationship_conditional_without_cue:${observation.observationId}`);
    }
  }

  const ledgerObservationIds = new Set<string>();
  for (const entry of result.sourceOrderLedger) {
    if (!entry.ledgerKey.trim() || entry.observationCount !== entry.observationIds.length || entry.observationCount < 1) {
      throw new Error(`invalid_relationship_ledger_entry:${entry.ledgerKey}`);
    }
    const observations = entry.observationIds.map((id) => {
      if (ledgerObservationIds.has(id)) throw new Error(`duplicate_relationship_ledger_observation:${id}`);
      ledgerObservationIds.add(id);
      const observation = observationsById.get(id);
      if (!observation) throw new Error(`relationship_ledger_unknown_observation:${id}`);
      if (
        observation.subjectCharacterKey !== entry.subjectCharacterKey
        || observation.objectCharacterKey !== entry.objectCharacterKey
        || observation.predicate !== entry.predicate
      ) throw new Error(`relationship_ledger_group_mismatch:${id}`);
      return observation;
    });
    const sorted = [...observations].sort((left, right) =>
      left.predicateStartOffset - right.predicateStartOffset
      || left.predicateEndOffset - right.predicateEndOffset
      || left.observationId.localeCompare(right.observationId)
    );
    if (sorted.some((observation, index) => observation.observationId !== entry.observationIds[index])) {
      throw new Error(`relationship_ledger_order_mismatch:${entry.ledgerKey}`);
    }
    if (entry.firstSourceOffset !== sorted[0]!.predicateStartOffset || entry.lastSourceOffset !== sorted.at(-1)!.predicateStartOffset) {
      throw new Error(`relationship_ledger_offset_mismatch:${entry.ledgerKey}`);
    }
  }
  if (ledgerObservationIds.size !== observationsById.size) throw new Error("relationship_ledger_incomplete");

  const expected = characterRelationshipEvidenceFingerprint({
    provider: result.provider,
    sourceProvider: result.sourceProvider,
    identityResolverVersion: result.identityResolverVersion,
    identityOutputFingerprint: result.identityOutputFingerprint,
    normalizedInputFingerprint: result.normalizedInputFingerprint,
    configurationFingerprint: result.configurationFingerprint,
    observations: result.observations,
    sourceOrderLedger: result.sourceOrderLedger,
  });
  if (expected !== result.outputFingerprint) throw new Error("relationship_output_fingerprint_mismatch");
}
