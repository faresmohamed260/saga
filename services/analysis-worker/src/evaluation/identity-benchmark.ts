import type { CharacterIdentityResult, ResolvedIdentityMention } from "../identity/types.js";
import type {
  GoldIdentityDocument,
  GoldIdentityMention,
  IdentityBenchmarkCase,
  IdentityBenchmarkCounts,
  IdentityBenchmarkMetrics,
  IdentityBenchmarkReport,
} from "./types.js";

function ratio(numerator: number, denominator: number) {
  return denominator === 0 ? 0 : numerator / denominator;
}

function spanKey(startOffset: number, endOffset: number) {
  return `${startOffset}:${endOffset}`;
}

function buildGoldSpanIndex(gold: GoldIdentityDocument) {
  const index = new Map<string, GoldIdentityMention[]>();
  for (const mention of gold.mentions) {
    const key = spanKey(mention.startOffset, mention.endOffset);
    const rows = index.get(key) ?? [];
    rows.push(mention);
    index.set(key, rows);
  }
  return index;
}

function alignGoldMention(
  mention: ResolvedIdentityMention,
  index: Map<string, GoldIdentityMention[]>,
) {
  const candidates = index.get(spanKey(mention.startOffset, mention.endOffset)) ?? [];
  const exactSurface = candidates.filter((candidate) => candidate.surfaceText === mention.surfaceText);
  if (exactSurface.length === 1) return exactSurface[0]!;
  if (candidates.length === 1) return candidates[0]!;
  return null;
}

function seedEligibleCharacters(gold: GoldIdentityDocument) {
  const result = new Set<string>();
  for (const mention of gold.mentions) {
    if (
      mention.entityType === "person" &&
      mention.goldCharacterId &&
      mention.mentionKind === "proper_name"
    ) {
      result.add(mention.goldCharacterId);
    }
  }
  return result;
}

type PredictedCharacterAssessment = {
  characterKey: string;
  goldCharacterIds: Set<string>;
  contaminatingMentionCount: number;
  linkedPersonMentionCount: number;
  dominantGoldMentionCount: number;
  pureGoldCharacterId: string | null;
};

function assessPredictedCharacters(
  result: CharacterIdentityResult,
  aligned: Map<string, GoldIdentityMention | null>,
): PredictedCharacterAssessment[] {
  return result.characters.map((character) => {
    const linked = result.mentions.filter((mention) => mention.characterKey === character.characterKey);
    const goldCharacterIds = new Set<string>();
    const perGold = new Map<string, number>();
    let contaminatingMentionCount = 0;
    let linkedPersonMentionCount = 0;

    for (const mention of linked) {
      const gold = aligned.get(mention.evidenceId) ?? null;
      if (gold?.entityType === "person" && gold.goldCharacterId) {
        goldCharacterIds.add(gold.goldCharacterId);
        linkedPersonMentionCount += 1;
        perGold.set(gold.goldCharacterId, (perGold.get(gold.goldCharacterId) ?? 0) + 1);
      } else {
        contaminatingMentionCount += 1;
      }
    }

    const dominantGoldMentionCount = Math.max(0, ...perGold.values());
    const pureGoldCharacterId =
      goldCharacterIds.size === 1 && contaminatingMentionCount === 0
        ? [...goldCharacterIds][0]!
        : null;

    return {
      characterKey: character.characterKey,
      goldCharacterIds,
      contaminatingMentionCount,
      linkedPersonMentionCount,
      dominantGoldMentionCount,
      pureGoldCharacterId,
    };
  });
}

export function evaluateIdentityBenchmarkCase(input: IdentityBenchmarkCase): IdentityBenchmarkReport {
  const { gold, result } = input;
  const goldSpanIndex = buildGoldSpanIndex(gold);
  const seedEligible = seedEligibleCharacters(gold);
  const aligned = new Map<string, GoldIdentityMention | null>();

  for (const mention of result.mentions) {
    aligned.set(mention.evidenceId, alignGoldMention(mention, goldSpanIndex));
  }

  const assessments = assessPredictedCharacters(result, aligned);
  const pure = assessments.filter((assessment) => assessment.pureGoldCharacterId !== null);
  const represented = new Set(
    pure
      .map((assessment) => assessment.pureGoldCharacterId)
      .filter((value): value is string => value !== null && seedEligible.has(value)),
  );

  let fragmentationExcessCount = 0;
  for (const goldCharacterId of seedEligible) {
    const predictedKeys = new Set(
      assessments
        .filter((assessment) => assessment.goldCharacterIds.has(goldCharacterId))
        .map((assessment) => assessment.characterKey),
    );
    fragmentationExcessCount += Math.max(0, predictedKeys.size - 1);
  }

  const relevantGoldMentions = gold.mentions.filter(
    (mention) =>
      mention.entityType === "person" &&
      mention.goldCharacterId !== null &&
      seedEligible.has(mention.goldCharacterId),
  );
  const relevantGoldMentionIds = new Set(relevantGoldMentions.map((mention) => mention.mentionId));

  const assessmentByCharacter = new Map(
    assessments.map((assessment) => [assessment.characterKey, assessment]),
  );

  let linkedMentionCount = 0;
  let correctLinkedMentionCount = 0;
  let unresolvedRelevantMentionCount = 0;
  let quarantinedRelevantMentionCount = 0;
  let nonPersonPredictedMentionCount = 0;
  let nonPersonLinkedMentionCount = 0;
  let nonPersonQuarantinedMentionCount = 0;

  for (const mention of result.mentions) {
    const goldMention = aligned.get(mention.evidenceId) ?? null;
    if (mention.resolutionState === "linked") linkedMentionCount += 1;

    if (goldMention?.entityType === "non_person") {
      nonPersonPredictedMentionCount += 1;
      if (mention.resolutionState === "linked") nonPersonLinkedMentionCount += 1;
      if (mention.resolutionState === "quarantined") nonPersonQuarantinedMentionCount += 1;
    }

    if (
      goldMention?.goldCharacterId &&
      relevantGoldMentionIds.has(goldMention.mentionId)
    ) {
      if (mention.resolutionState === "unresolved") unresolvedRelevantMentionCount += 1;
      if (mention.resolutionState === "quarantined") quarantinedRelevantMentionCount += 1;

      if (mention.resolutionState === "linked" && mention.characterKey) {
        const assessment = assessmentByCharacter.get(mention.characterKey);
        if (assessment?.pureGoldCharacterId === goldMention.goldCharacterId) {
          correctLinkedMentionCount += 1;
        }
      }
    }
  }

  const counts: IdentityBenchmarkCounts = {
    documentCount: 1,
    goldSeedEligibleCharacterCount: seedEligible.size,
    predictedCanonicalCount: result.characters.length,
    pureCanonicalCount: pure.length,
    falseCanonicalCount: assessments.filter((assessment) => assessment.goldCharacterIds.size === 0).length,
    incorrectMergeCount: assessments.filter((assessment) => assessment.goldCharacterIds.size > 1).length,
    contaminatedCanonicalCount: assessments.filter(
      (assessment) => assessment.contaminatingMentionCount > 0,
    ).length,
    representedGoldCharacterCount: represented.size,
    fragmentationExcessCount,
    relevantGoldMentionCount: relevantGoldMentions.length,
    predictedMentionCount: result.mentions.length,
    correctLinkedMentionCount,
    linkedMentionCount,
    unresolvedRelevantMentionCount,
    quarantinedRelevantMentionCount,
    nonPersonPredictedMentionCount,
    nonPersonLinkedMentionCount,
    nonPersonQuarantinedMentionCount,
    linkedPersonMentionCount: assessments.reduce(
      (sum, assessment) => sum + assessment.linkedPersonMentionCount,
      0,
    ),
    dominantClusterLinkedPersonMentionCount: assessments.reduce(
      (sum, assessment) => sum + assessment.dominantGoldMentionCount,
      0,
    ),
  };

  return { counts, metrics: metricsFromCounts(counts) };
}

export function metricsFromCounts(counts: IdentityBenchmarkCounts): IdentityBenchmarkMetrics {
  return {
    canonicalPrecision: ratio(counts.pureCanonicalCount, counts.predictedCanonicalCount),
    canonicalRecall: ratio(
      counts.representedGoldCharacterCount,
      counts.goldSeedEligibleCharacterCount,
    ),
    falseCanonicalRate: ratio(counts.falseCanonicalCount, counts.predictedCanonicalCount),
    incorrectMergeRate: ratio(counts.incorrectMergeCount, counts.predictedCanonicalCount),
    contaminatedCanonicalRate: ratio(
      counts.contaminatedCanonicalCount,
      counts.predictedCanonicalCount,
    ),
    fragmentationRate: ratio(
      counts.fragmentationExcessCount,
      counts.goldSeedEligibleCharacterCount,
    ),
    linkedMentionPrecision: ratio(counts.correctLinkedMentionCount, counts.linkedMentionCount),
    linkedMentionRecall: ratio(
      counts.correctLinkedMentionCount,
      counts.relevantGoldMentionCount,
    ),
    unresolvedRelevantMentionRate: ratio(
      counts.unresolvedRelevantMentionCount,
      counts.relevantGoldMentionCount,
    ),
    quarantinedRelevantMentionRate: ratio(
      counts.quarantinedRelevantMentionCount,
      counts.relevantGoldMentionCount,
    ),
    nonPersonQuarantineRate: ratio(
      counts.nonPersonQuarantinedMentionCount,
      counts.nonPersonPredictedMentionCount,
    ),
    clusterPurity: ratio(
      counts.dominantClusterLinkedPersonMentionCount,
      counts.linkedPersonMentionCount,
    ),
  };
}

export function aggregateIdentityBenchmarkReports(
  reports: IdentityBenchmarkReport[],
): IdentityBenchmarkReport {
  const counts: IdentityBenchmarkCounts = {
    documentCount: 0,
    goldSeedEligibleCharacterCount: 0,
    predictedCanonicalCount: 0,
    pureCanonicalCount: 0,
    falseCanonicalCount: 0,
    incorrectMergeCount: 0,
    contaminatedCanonicalCount: 0,
    representedGoldCharacterCount: 0,
    fragmentationExcessCount: 0,
    relevantGoldMentionCount: 0,
    predictedMentionCount: 0,
    correctLinkedMentionCount: 0,
    linkedMentionCount: 0,
    unresolvedRelevantMentionCount: 0,
    quarantinedRelevantMentionCount: 0,
    nonPersonPredictedMentionCount: 0,
    nonPersonLinkedMentionCount: 0,
    nonPersonQuarantinedMentionCount: 0,
    linkedPersonMentionCount: 0,
    dominantClusterLinkedPersonMentionCount: 0,
  };

  for (const report of reports) {
    for (const key of Object.keys(counts) as Array<keyof IdentityBenchmarkCounts>) {
      counts[key] += report.counts[key];
    }
  }

  return { counts, metrics: metricsFromCounts(counts) };
}
