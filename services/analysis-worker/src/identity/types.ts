import type { NormalizedSection } from "../ingestion/types.js";

export type IdentityMentionKind = "proper_name" | "nominal" | "pronoun";
export type IdentityEntityType = "person" | "non_person" | "unknown";
export type IdentityPersonEvidence = "strong" | "supporting" | "weak" | "none";
export type IdentityBoundaryQuality = "clean" | "malformed";

/**
 * Provider-normalized evidence. Provider SDK/model shapes must be translated
 * into this contract before S.A.G.A. identity policy sees them.
 */
export type IdentityEvidenceMention = {
  evidenceId: string;
  surfaceText: string;
  startOffset: number;
  endOffset: number;
  structuralLocator: string | null;
  mentionKind: IdentityMentionKind;
  entityType: IdentityEntityType;
  personEvidence: IdentityPersonEvidence;
  boundaryQuality: IdentityBoundaryQuality;
  providerClusterId: string | null;
};

export type IdentityProviderDescriptor = {
  name: string;
  model: string | null;
  revision: string;
};

export type NormalizedIdentityEvidence = {
  provider: IdentityProviderDescriptor;
  normalizedInputFingerprint: string;
  mentions: IdentityEvidenceMention[];
};

export interface CharacterEvidenceProvider {
  readonly descriptor: IdentityProviderDescriptor;
  collect(input: {
    normalizedInputFingerprint: string;
    normalizedText: string;
    sections: NormalizedSection[];
  }): Promise<NormalizedIdentityEvidence>;
}

export type ResolvedCharacterAlias = {
  surfaceForm: string;
  normalizedForm: string;
  evidenceCount: number;
};

export type ResolvedCharacter = {
  characterKey: string;
  canonicalName: string;
  admissionTier: "canonical_seed" | "stabilized";
  evidenceCount: number;
  aliases: ResolvedCharacterAlias[];
};

export type ResolvedIdentityMention = {
  evidenceId: string;
  characterKey: string | null;
  surfaceText: string;
  startOffset: number;
  endOffset: number;
  structuralLocator: string | null;
  mentionKind: IdentityMentionKind;
  resolutionState: "linked" | "unresolved" | "quarantined";
  evidenceTier: "canonical_seed" | "attachment" | "quarantined";
  decisionReason: string;
};

export type CharacterIdentityResult = {
  resolverVersion: string;
  resolverConfigFingerprint: string;
  provider: IdentityProviderDescriptor;
  normalizedInputFingerprint: string;
  outputFingerprint: string;
  characters: ResolvedCharacter[];
  mentions: ResolvedIdentityMention[];
};
