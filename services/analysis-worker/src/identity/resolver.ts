import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import type {
  CharacterIdentityResult,
  IdentityEvidenceMention,
  NormalizedIdentityEvidence,
  ResolvedCharacter,
  ResolvedIdentityMention,
} from "./types.js";

export const IDENTITY_RESOLVER_VERSION = "saga-identity-resolver-v1";

const BLOCKED_SURFACES = [
  "he",
  "her",
  "hers",
  "him",
  "his",
  "i",
  "it",
  "its",
  "me",
  "mine",
  "my",
  "our",
  "ours",
  "she",
  "that",
  "their",
  "theirs",
  "them",
  "they",
  "this",
  "those",
  "us",
  "we",
  "what",
  "which",
  "who",
  "whom",
  "whose",
  "you",
  "your",
  "yours",
];

const GENERIC_ROLE_SURFACES = [
  "captain",
  "doctor",
  "fiddler",
  "guard",
  "healer",
  "king",
  "narrator",
  "prince",
  "princess",
  "queen",
  "reveler",
  "revelers",
  "servant",
  "soldier",
  "stranger",
];

const LEADING_TITLES = [
  "doctor",
  "dr",
  "king",
  "lady",
  "lord",
  "miss",
  "mister",
  "mr",
  "mrs",
  "ms",
  "prince",
  "princess",
  "professor",
  "queen",
  "sir",
];

const TRAILING_FRAGMENT_TOKENS = [
  "and",
  "at",
  "by",
  "for",
  "from",
  "in",
  "of",
  "on",
  "or",
  "the",
  "to",
  "with",
];

const POLICY_CONFIG = {
  version: IDENTITY_RESOLVER_VERSION,
  canonicalSeed: {
    mentionKind: "proper_name",
    entityType: "person",
    personEvidence: "strong",
    boundaryQuality: "clean",
  },
  blockedSurfaces: BLOCKED_SURFACES,
  genericRoleSurfaces: GENERIC_ROLE_SURFACES,
  leadingTitles: LEADING_TITLES,
  trailingFragmentTokens: TRAILING_FRAGMENT_TOKENS,
  attachment: "unique-provider-cluster-or-unique-proper-name",
  stabilization: "full-evidence-pass-before-attachment",
} as const;

export const IDENTITY_RESOLVER_CONFIG_FINGERPRINT = sha256Hex(canonicalJson(POLICY_CONFIG));

const blockedSurfaceSet = new Set(BLOCKED_SURFACES);
const genericRoleSet = new Set(GENERIC_ROLE_SURFACES);
const leadingTitleSet = new Set(LEADING_TITLES);
const trailingFragmentSet = new Set(TRAILING_FRAGMENT_TOKENS);

type SeedCandidate = {
  mention: IdentityEvidenceMention;
  compareKey: string;
  compareTokens: string[];
};

type SeedGroup = {
  seeds: SeedCandidate[];
};

type MentionDecision = ResolvedIdentityMention & { compareKey: string | null };

function normalizedWords(surface: string) {
  return surface
    .normalize("NFKC")
    .toLocaleLowerCase("en-US")
    .replace(/[’‘`]/g, "'")
    .replace(/[‐‑‒–—]/g, "-")
    .replace(/[^\p{L}\p{M}'-]+/gu, " ")
    .trim()
    .split(/\s+/u)
    .filter(Boolean);
}

function comparisonTokens(surface: string) {
  const words = normalizedWords(surface);
  let index = 0;
  while (words.length - index > 1 && leadingTitleSet.has(words[index] ?? "")) index += 1;
  return words.slice(index);
}

export function normalizeIdentityName(surface: string) {
  return comparisonTokens(surface).join(" ");
}

function isBlockedSurface(surface: string) {
  const words = normalizedWords(surface);
  if (words.length !== 1) return false;
  return blockedSurfaceSet.has(words[0] ?? "") || genericRoleSet.has(words[0] ?? "");
}

function hasMalformedLexicalBoundary(surface: string) {
  const words = normalizedWords(surface);
  if (words.length === 0 || words.length > 12) return true;
  return trailingFragmentSet.has(words.at(-1) ?? "");
}

function isCanonicalSeedCandidate(mention: IdentityEvidenceMention) {
  return (
    mention.mentionKind === "proper_name" &&
    mention.entityType === "person" &&
    mention.personEvidence === "strong" &&
    mention.boundaryQuality === "clean" &&
    !isBlockedSurface(mention.surfaceText) &&
    !hasMalformedLexicalBoundary(mention.surfaceText) &&
    comparisonTokens(mention.surfaceText).length > 0
  );
}

function sameProviderCluster(a: SeedCandidate, b: SeedCandidate) {
  return (
    a.mention.providerClusterId !== null &&
    a.mention.providerClusterId === b.mention.providerClusterId
  );
}

function namesCompatible(a: SeedCandidate, b: SeedCandidate) {
  if (a.compareKey === b.compareKey) {
    if (a.compareTokens.length > 1 || b.compareTokens.length > 1) return true;
    return (
      sameProviderCluster(a, b) ||
      (a.mention.providerClusterId === null && b.mention.providerClusterId === null)
    );
  }

  if (!sameProviderCluster(a, b)) return false;

  if (a.compareTokens.length === 1) return b.compareTokens.includes(a.compareTokens[0] ?? "");
  if (b.compareTokens.length === 1) return a.compareTokens.includes(b.compareTokens[0] ?? "");

  const shorter = a.compareTokens.length <= b.compareTokens.length ? a.compareTokens : b.compareTokens;
  const longer = shorter === a.compareTokens ? b.compareTokens : a.compareTokens;
  const prefix = shorter.every((token, index) => longer[index] === token);
  const suffix = shorter.every(
    (token, index) => longer[longer.length - shorter.length + index] === token,
  );
  return prefix || suffix;
}

function groupCompatible(group: SeedGroup, candidate: SeedCandidate) {
  return group.seeds.every((seed) => namesCompatible(seed, candidate));
}

function chooseCanonicalName(group: SeedGroup) {
  return [...group.seeds]
    .sort((a, b) => {
      const tokenDelta = b.compareTokens.length - a.compareTokens.length;
      if (tokenDelta !== 0) return tokenDelta;
      const lengthDelta = [...b.mention.surfaceText].length - [...a.mention.surfaceText].length;
      if (lengthDelta !== 0) return lengthDelta;
      const offsetDelta = a.mention.startOffset - b.mention.startOffset;
      if (offsetDelta !== 0) return offsetDelta;
      return a.mention.surfaceText.localeCompare(b.mention.surfaceText, "en");
    })[0]?.mention.surfaceText ?? "Unknown character";
}

function semanticCharacterKey(
  normalizedInputFingerprint: string,
  group: SeedGroup,
) {
  const semanticSeeds = group.seeds
    .map((seed) => ({
      compareKey: seed.compareKey,
      startOffset: seed.mention.startOffset,
      endOffset: seed.mention.endOffset,
    }))
    .sort((a, b) => a.startOffset - b.startOffset || a.compareKey.localeCompare(b.compareKey));
  return `character:${sha256Hex(canonicalJson({ normalizedInputFingerprint, semanticSeeds })).slice(0, 24)}`;
}

function validateEvidence(evidence: NormalizedIdentityEvidence) {
  if (!/^[0-9a-f]{64}$/.test(evidence.normalizedInputFingerprint)) {
    throw new Error("invalid_identity_input_fingerprint");
  }
  if (!evidence.provider.name.trim() || !evidence.provider.revision.trim()) {
    throw new Error("invalid_identity_provider_descriptor");
  }

  const ids = new Set<string>();
  for (const mention of evidence.mentions) {
    if (!mention.evidenceId || ids.has(mention.evidenceId)) {
      throw new Error("duplicate_or_missing_identity_evidence_id");
    }
    ids.add(mention.evidenceId);
  }
}

function spanMatchesNormalizedText(mention: IdentityEvidenceMention, codePoints: string[]) {
  if (
    !Number.isSafeInteger(mention.startOffset) ||
    !Number.isSafeInteger(mention.endOffset) ||
    mention.startOffset < 0 ||
    mention.endOffset <= mention.startOffset ||
    mention.endOffset > codePoints.length
  ) {
    return false;
  }
  return codePoints.slice(mention.startOffset, mention.endOffset).join("") === mention.surfaceText;
}

function seedRejectionReason(mention: IdentityEvidenceMention, spanValid: boolean) {
  if (!spanValid) return "span_text_mismatch";
  if (mention.boundaryQuality === "malformed" || hasMalformedLexicalBoundary(mention.surfaceText)) {
    return "malformed_span";
  }
  if (mention.entityType === "non_person") return "non_person_evidence";
  if (isBlockedSurface(mention.surfaceText)) return "blocked_surface";
  if (mention.mentionKind === "pronoun") return "pronoun_cannot_seed";
  if (mention.mentionKind !== "proper_name") return "non_name_cannot_seed";
  return "insufficient_seed_evidence";
}

function aliasRows(mentions: MentionDecision[], characterKey: string) {
  const counts = new Map<string, { surfaceForm: string; normalizedForm: string; evidenceCount: number }>();
  for (const mention of mentions) {
    if (mention.characterKey !== characterKey || mention.mentionKind !== "proper_name") continue;
    const normalizedForm = normalizeIdentityName(mention.surfaceText);
    if (!normalizedForm) continue;
    const existing = counts.get(normalizedForm);
    if (existing) {
      existing.evidenceCount += 1;
      if (mention.surfaceText.length > existing.surfaceForm.length) existing.surfaceForm = mention.surfaceText;
    } else {
      counts.set(normalizedForm, { surfaceForm: mention.surfaceText, normalizedForm, evidenceCount: 1 });
    }
  }
  return [...counts.values()].sort(
    (a, b) => b.evidenceCount - a.evidenceCount || a.normalizedForm.localeCompare(b.normalizedForm, "en"),
  );
}

export function resolveCharacterIdentity(input: {
  normalizedText: string;
  evidence: NormalizedIdentityEvidence;
}): CharacterIdentityResult {
  validateEvidence(input.evidence);
  const codePoints = [...input.normalizedText];
  const mentions = [...input.evidence.mentions].sort(
    (a, b) => a.startOffset - b.startOffset || a.endOffset - b.endOffset || a.evidenceId.localeCompare(b.evidenceId),
  );

  const seedCandidates: SeedCandidate[] = [];
  const spanValidity = new Map<string, boolean>();
  for (const mention of mentions) {
    const spanValid = spanMatchesNormalizedText(mention, codePoints);
    spanValidity.set(mention.evidenceId, spanValid);
    if (!spanValid || !isCanonicalSeedCandidate(mention)) continue;
    const compareTokens = comparisonTokens(mention.surfaceText);
    seedCandidates.push({ mention, compareKey: compareTokens.join(" "), compareTokens });
  }

  const multiTokenSeeds = seedCandidates.filter((seed) => seed.compareTokens.length > 1);
  const singleTokenSeeds = seedCandidates.filter((seed) => seed.compareTokens.length === 1);
  const groups: SeedGroup[] = [];
  const seedGroupByEvidence = new Map<string, SeedGroup>();
  const ambiguousSeedIds = new Set<string>();

  for (const seed of multiTokenSeeds) {
    const matches = groups.filter((group) => groupCompatible(group, seed));
    if (matches.length === 1) {
      matches[0]?.seeds.push(seed);
      seedGroupByEvidence.set(seed.mention.evidenceId, matches[0]!);
    } else if (matches.length === 0) {
      const group = { seeds: [seed] };
      groups.push(group);
      seedGroupByEvidence.set(seed.mention.evidenceId, group);
    } else {
      ambiguousSeedIds.add(seed.mention.evidenceId);
    }
  }

  for (const seed of singleTokenSeeds) {
    const sameClusterMatches = groups.filter(
      (group) =>
        groupCompatible(group, seed) &&
        group.seeds.some((member) => sameProviderCluster(member, seed)),
    );
    const matches = sameClusterMatches.length > 0
      ? sameClusterMatches
      : groups.filter((group) => groupCompatible(group, seed));

    if (matches.length === 1) {
      matches[0]?.seeds.push(seed);
      seedGroupByEvidence.set(seed.mention.evidenceId, matches[0]!);
      continue;
    }
    if (matches.length > 1) {
      ambiguousSeedIds.add(seed.mention.evidenceId);
      continue;
    }

    const exactExisting = groups.find((group) =>
      group.seeds.every((member) => member.compareKey === seed.compareKey) &&
      group.seeds.every(
        (member) =>
          sameProviderCluster(member, seed) ||
          (member.mention.providerClusterId === null && seed.mention.providerClusterId === null),
      ),
    );
    if (exactExisting) {
      exactExisting.seeds.push(seed);
      seedGroupByEvidence.set(seed.mention.evidenceId, exactExisting);
    } else {
      const group = { seeds: [seed] };
      groups.push(group);
      seedGroupByEvidence.set(seed.mention.evidenceId, group);
    }
  }

  const groupCharacterKey = new Map<SeedGroup, string>();
  for (const group of groups) {
    groupCharacterKey.set(
      group,
      semanticCharacterKey(input.evidence.normalizedInputFingerprint, group),
    );
  }

  const groupsByProviderCluster = new Map<string, Set<SeedGroup>>();
  const groupsByCompareKey = new Map<string, Set<SeedGroup>>();
  for (const group of groups) {
    for (const seed of group.seeds) {
      if (seed.mention.providerClusterId) {
        const set = groupsByProviderCluster.get(seed.mention.providerClusterId) ?? new Set<SeedGroup>();
        set.add(group);
        groupsByProviderCluster.set(seed.mention.providerClusterId, set);
      }
      const names = groupsByCompareKey.get(seed.compareKey) ?? new Set<SeedGroup>();
      names.add(group);
      groupsByCompareKey.set(seed.compareKey, names);
    }
  }

  const decisions: MentionDecision[] = [];
  for (const mention of mentions) {
    const spanValid = spanValidity.get(mention.evidenceId) === true;
    const seedGroup = seedGroupByEvidence.get(mention.evidenceId);
    const compareKey = mention.mentionKind === "proper_name" ? normalizeIdentityName(mention.surfaceText) : null;

    if (seedGroup) {
      decisions.push({
        evidenceId: mention.evidenceId,
        characterKey: groupCharacterKey.get(seedGroup)!,
        surfaceText: mention.surfaceText,
        startOffset: mention.startOffset,
        endOffset: mention.endOffset,
        structuralLocator: mention.structuralLocator,
        mentionKind: mention.mentionKind,
        resolutionState: "linked",
        evidenceTier: "canonical_seed",
        decisionReason: "accepted_canonical_seed",
        compareKey,
      });
      continue;
    }

    if (ambiguousSeedIds.has(mention.evidenceId)) {
      decisions.push({
        evidenceId: mention.evidenceId,
        characterKey: null,
        surfaceText: mention.surfaceText,
        startOffset: mention.startOffset,
        endOffset: mention.endOffset,
        structuralLocator: mention.structuralLocator,
        mentionKind: mention.mentionKind,
        resolutionState: "unresolved",
        evidenceTier: "attachment",
        decisionReason: "ambiguous_seed_name",
        compareKey,
      });
      continue;
    }

    const rejectionReason = seedRejectionReason(mention, spanValid);
    if (
      rejectionReason === "span_text_mismatch" ||
      rejectionReason === "malformed_span" ||
      rejectionReason === "non_person_evidence" ||
      rejectionReason === "blocked_surface"
    ) {
      decisions.push({
        evidenceId: mention.evidenceId,
        characterKey: null,
        surfaceText: mention.surfaceText,
        startOffset: mention.startOffset,
        endOffset: mention.endOffset,
        structuralLocator: mention.structuralLocator,
        mentionKind: mention.mentionKind,
        resolutionState: "quarantined",
        evidenceTier: "quarantined",
        decisionReason: rejectionReason,
        compareKey,
      });
      continue;
    }

    let attachmentGroups = new Set<SeedGroup>();
    if (mention.providerClusterId) {
      attachmentGroups = new Set(groupsByProviderCluster.get(mention.providerClusterId) ?? []);
    }

    if (attachmentGroups.size === 0 && compareKey) {
      attachmentGroups = new Set(groupsByCompareKey.get(compareKey) ?? []);
    }

    if (attachmentGroups.size === 1) {
      const group = [...attachmentGroups][0]!;
      decisions.push({
        evidenceId: mention.evidenceId,
        characterKey: groupCharacterKey.get(group)!,
        surfaceText: mention.surfaceText,
        startOffset: mention.startOffset,
        endOffset: mention.endOffset,
        structuralLocator: mention.structuralLocator,
        mentionKind: mention.mentionKind,
        resolutionState: "linked",
        evidenceTier: "attachment",
        decisionReason: mention.providerClusterId
          ? "unique_provider_cluster_attachment"
          : "unique_name_attachment",
        compareKey,
      });
      continue;
    }

    decisions.push({
      evidenceId: mention.evidenceId,
      characterKey: null,
      surfaceText: mention.surfaceText,
      startOffset: mention.startOffset,
      endOffset: mention.endOffset,
      structuralLocator: mention.structuralLocator,
      mentionKind: mention.mentionKind,
      resolutionState: "unresolved",
      evidenceTier: "attachment",
      decisionReason:
        attachmentGroups.size > 1
          ? "ambiguous_provider_cluster"
          : rejectionReason,
      compareKey,
    });
  }

  const characters: ResolvedCharacter[] = groups.map((group) => {
    const characterKey = groupCharacterKey.get(group)!;
    const linked = decisions.filter((mention) => mention.characterKey === characterKey);
    const firstSeedOffset = Math.min(...group.seeds.map((seed) => seed.mention.startOffset));
    const hasBackfilledAttachment = linked.some(
      (mention) => mention.evidenceTier === "attachment" && mention.startOffset < firstSeedOffset,
    );
    return {
      characterKey,
      canonicalName: chooseCanonicalName(group),
      admissionTier: hasBackfilledAttachment ? "stabilized" : "canonical_seed",
      evidenceCount: linked.length,
      aliases: aliasRows(decisions, characterKey),
    };
  }).sort((a, b) => a.canonicalName.localeCompare(b.canonicalName, "en") || a.characterKey.localeCompare(b.characterKey));

  const publicMentions: ResolvedIdentityMention[] = decisions.map(({ compareKey: _compareKey, ...mention }) => mention);
  const fingerprintPayload = {
    resolverVersion: IDENTITY_RESOLVER_VERSION,
    resolverConfigFingerprint: IDENTITY_RESOLVER_CONFIG_FINGERPRINT,
    provider: input.evidence.provider,
    normalizedInputFingerprint: input.evidence.normalizedInputFingerprint,
    characters,
    mentions: publicMentions,
  };

  return {
    ...fingerprintPayload,
    outputFingerprint: sha256Hex(canonicalJson(fingerprintPayload)),
  };
}
