import type { CharacterIdentityResult, IdentityMentionKind, NormalizedIdentityEvidence } from "../identity/types.js";

export type GoldIdentityMention = {
  mentionId: string;
  surfaceText: string;
  startOffset: number;
  endOffset: number;
  mentionKind: IdentityMentionKind;
  entityType: "person" | "non_person";
  goldCharacterId: string | null;
};

export type GoldIdentityDocument = {
  documentId: string;
  text: string;
  mentions: GoldIdentityMention[];
};

export type IdentityBenchmarkCase = {
  gold: GoldIdentityDocument;
  evidence: NormalizedIdentityEvidence;
  result: CharacterIdentityResult;
};

export type IdentityBenchmarkCounts = {
  documentCount: number;
  goldSeedEligibleCharacterCount: number;
  predictedCanonicalCount: number;
  pureCanonicalCount: number;
  falseCanonicalCount: number;
  incorrectMergeCount: number;
  contaminatedCanonicalCount: number;
  representedGoldCharacterCount: number;
  fragmentationExcessCount: number;
  relevantGoldMentionCount: number;
  predictedMentionCount: number;
  correctLinkedMentionCount: number;
  linkedMentionCount: number;
  unresolvedRelevantMentionCount: number;
  quarantinedRelevantMentionCount: number;
  nonPersonPredictedMentionCount: number;
  nonPersonLinkedMentionCount: number;
  nonPersonQuarantinedMentionCount: number;
  linkedPersonMentionCount: number;
  dominantClusterLinkedPersonMentionCount: number;
};

export type IdentityBenchmarkMetrics = {
  canonicalPrecision: number;
  canonicalRecall: number;
  falseCanonicalRate: number;
  incorrectMergeRate: number;
  contaminatedCanonicalRate: number;
  fragmentationRate: number;
  linkedMentionPrecision: number;
  linkedMentionRecall: number;
  unresolvedRelevantMentionRate: number;
  quarantinedRelevantMentionRate: number;
  nonPersonQuarantineRate: number;
  clusterPurity: number;
};

export type IdentityBenchmarkReport = {
  counts: IdentityBenchmarkCounts;
  metrics: IdentityBenchmarkMetrics;
};
