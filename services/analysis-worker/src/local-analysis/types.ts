import type { NormalizedSection } from "../ingestion/types.js";
import type { IdentityProviderDescriptor, NormalizedIdentityEvidence } from "../identity/types.js";

export type LiteraryEntityCategory =
  | "person"
  | "location"
  | "facility"
  | "geopolitical"
  | "organization"
  | "vehicle"
  | "unknown";

export type LiteraryEntityEvidence = {
  evidenceId: string;
  surfaceText: string;
  startOffset: number;
  endOffset: number;
  structuralLocator: string | null;
  mentionKind: "proper_name" | "nominal" | "pronoun";
  category: LiteraryEntityCategory;
  providerClusterId: string | null;
  boundaryQuality: "clean" | "malformed";
};

export type QuoteSpeakerEvidence = {
  evidenceId: string;
  quoteText: string;
  startOffset: number;
  endOffset: number;
  structuralLocator: string | null;
  speakerSurfaceText: string | null;
  speakerStartOffset: number | null;
  speakerEndOffset: number | null;
  speakerProviderClusterId: string | null;
};

export type SyntaxTokenEvidence = {
  evidenceId: string;
  surfaceText: string;
  lemma: string;
  startOffset: number;
  endOffset: number;
  structuralLocator: string | null;
  paragraphId: number;
  sentenceId: number;
  tokenIdWithinSentence: number;
  tokenId: number;
  posTag: string;
  finePosTag: string;
  dependencyRelation: string;
  syntacticHeadTokenId: number;
};

export type EventTriggerEvidence = {
  evidenceId: string;
  surfaceText: string;
  lemma: string;
  startOffset: number;
  endOffset: number;
  structuralLocator: string | null;
  sentenceId: number;
  tokenId: number;
  dependencyRelation: string;
  syntacticHeadTokenId: number;
};

export type LocalLiteraryEvidenceBundle = {
  provider: IdentityProviderDescriptor;
  normalizedInputFingerprint: string;
  identityEvidence: NormalizedIdentityEvidence;
  entities: LiteraryEntityEvidence[];
  quotes: QuoteSpeakerEvidence[];
  eventTriggers: EventTriggerEvidence[];
  /**
   * Optional provider-neutral sentence syntax evidence. Existing providers may omit it;
   * providers that expose a dependency graph must satisfy strict source/head validation.
   */
  syntaxTokens?: SyntaxTokenEvidence[];
};

export type LocalLiteraryAnalysisInput = {
  normalizedInputFingerprint: string;
  normalizedText: string;
  sections: NormalizedSection[];
};

export type LocalLiteraryProviderHealth = {
  status: "ok";
  provider: IdentityProviderDescriptor;
  protocolVersion: string;
  configurationFingerprint: string;
};

export interface LocalLiteraryEvidenceProvider {
  readonly descriptor: IdentityProviderDescriptor;
  readonly configurationFingerprint: string;
  analyze(input: LocalLiteraryAnalysisInput): Promise<LocalLiteraryEvidenceBundle>;
  health(): Promise<LocalLiteraryProviderHealth>;
}

export type AnalysisBenchmarkResourceSample = {
  wallClockMs: number;
  peakResidentMemoryMb: number | null;
  peakVramMb: number | null;
  modelArtifactBytes: number | null;
};

export type AnalysisBenchmarkManifest = {
  schemaVersion: "saga-analysis-benchmark-v1";
  benchmarkId: string;
  source: {
    id: string;
    sha256: string;
    codePointCount: number;
    utf8ByteCount: number;
  };
  provider: IdentityProviderDescriptor;
  hardware: {
    hostLabel: string;
    cpu: string | null;
    logicalCpuCount: number | null;
    ramMb: number | null;
    gpu: string | null;
    vramMb: number | null;
  };
  configurationFingerprint: string;
  resources: AnalysisBenchmarkResourceSample;
  outputCounts: {
    identityMentions: number;
    entities: number;
    quotes: number;
    eventTriggers: number;
  };
};
