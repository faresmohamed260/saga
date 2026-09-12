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
};

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
