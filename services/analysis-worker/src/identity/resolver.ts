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
  "he", "her", "hers", "him", "his", "i", "it", "its", "me", "mine", "my",
  "our", "ours", "she", "that", "their", "theirs", "them", "they", "this",
  "those", "us", "we", "what", "which", "who", "whom", "whose", "you", "your", "yours",
];
const GENERIC_ROLE_SURFACES = [
  "captain", "doctor", "fiddler", "guard", "healer", "king", "narrator", "prince",
  "princess", "queen", "reveler", "revelers", "servant", "soldier", "stranger",
];
const LEADING_TITLES = [
  "doctor", "dr", "king", "lady", "lord", "miss", "mister", "mr", "mrs", "ms",
  "prince", "princess", "professor", "queen", "sir",
];
const TRAILING_FRAGMENT_TOKENS = [
  "and", "at", "by", "for", "from", "in", "of", "on", "or", "the", "to", "with",
];

const blockedSurfaceSet = new Set(BLOCKED_SURFACES);
const genericRoleSet = new Set(GENERIC_ROLE_SURFACES);
const leadingTitleSet = new Set(LEADING_TITLES);
const trailingFragmentSet = new Set(TRAILING_FRAGMENT_TOKENS);

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

type SeedCandidate = {
  mention: IdentityEvidenceMention;
  compareKey: string;
  compareTokens: string[];
};
type SeedGroup = { seeds: SeedCandidate[] };
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

function singleNormalizedWord(surface: string) {
  const words = normalizedWords(surface);
  return words.length === 1 ? words[0]! : null;
}

function isBlockedDiscourseSurface(surface: string) {
  const word = singleNormalizedWord(surface);
  return word !== null && blockedSurfaceSet.has(word);
}

function isGenericRoleSurface(surface: string) {
  const word = singleNormalizedWord(surface);
  return word !== null && genericRoleSet.has(word);
}

function hasMalformedLexicalBoundary(surface: string) {
  const words = normalizedWords(surface);
  return words.length === 0 || words.length > 12 || trailingFragmentSet.has(words.at(-1) ?? "");
}

function isCanonicalSeedCandidate(mention: IdentityEvidenceMention) {
  return (
    mention.mentionKind === "proper_name" &&
    mention.entityType === "person" &&
    mention.personEvidence === "strong" &&
    mention.boundaryQuality === "clean" &&
    !isBlockedDiscourseSurface(mention.surfaceText) &&
    !isGenericRoleSurface(mention.surfaceText) &&
    !hasMalformedLexicalBoundary(mention.surfaceText) &&
    comparisonTokens(mention.surfaceText).length > 0
  );
}

function sameProviderCluster(a: SeedCandidate, b: SeedCandidate) {
  return a.mention.providerClusterId !== null && a.mention.providerClusterId === b.mention.providerClusterId;
}

function namesCompatible(a: SeedCandidate, b: SeedCandidate) {
  if (a.compareKey === b.compareKey) {
    if (a.compareTokens.length > 1 || b.compareTokens.length > 1) return true;
    return sameProviderCluster(a, b) || (a.mention.providerClusterId === null && b.mention.providerClusterId === null);
  }
  if (!sameProviderCluster(a, b)) return false;
  if (a.compareTokens.length === 1) return b.compareTokens.includes(a.compareTokens[0]!);
  if (b.compareTokens.length === 1) return a.compareTokens.includes(b.compareTokens[0]!);
  const shorter = a.compareTokens.length <= b.compareTokens.length ? a.compareTokens : b.compareTokens;
  const longer = shorter === a.compareTokens ? b.compareTokens : a.compareTokens;
  return (
    shorter.every((token, index) => longer[index] === token) ||
    shorter.every((token, index) => longer[longer.length - shorter.length + index] === token)
  );
}

function groupCompatible(group: SeedGroup, candidate: SeedCandidate) {
  const anchors = group.seeds.filter((seed) => seed.compareTokens.length > 1);
  if (anchors.length > 0) {
    return anchors.every((anchor) => namesCompatible(anchor, candidate));
  }
  return group.seeds.every((seed) => namesCompatible(seed, candidate));
}

function chooseCanonicalName(group: SeedGroup) {
  return [...group.seeds]
    .sort((a, b) =>
      b.compareTokens.length - a.compareTokens.length ||
      [...b.mention.surfaceText].length - [...a.mention.surfaceText].length ||
      a.mention.startOffset - b.mention.startOffset ||
      a.mention.surfaceText.localeCompare(b.mention.surfaceText, "en"),
    )[0]!.mention.surfaceText;
}

function semanticCharacterKey(normalizedInputFingerprint: string, group: SeedGroup) {
  const semanticSeeds = group.seeds
    .map((seed) => ({ compareKey: seed.compareKey, startOffset: seed.mention.startOffset, endOffset: seed.mention.endOffset }))
    .sort((a, b) => a.startOffset - b.startOffset || a.compareKey.localeCompare(b.compareKey));
  return `character:${sha256Hex(canonicalJson({ normalizedInputFingerprint, semanticSeeds })).slice(0, 24)}`;
}

function validateEvidence(evidence: NormalizedIdentityEvidence) {
  if (!/^[0-9a-f]{64}$/.test(evidence.normalizedInputFingerprint)) throw new Error("invalid_identity_input_fingerprint");
  if (!evidence.provider.name.trim() || !evidence.provider.revision.trim()) throw new Error("invalid_identity_provider_descriptor");
  const ids = new Set<string>();
  for (const mention of evidence.mentions) {
    if (!mention.evidenceId || ids.has(mention.evidenceId)) throw new Error("duplicate_or_missing_identity_evidence_id");
    ids.add(mention.evidenceId);
  }
}

function spanMatchesNormalizedText(mention: IdentityEvidenceMention, codePoints: string[]) {
  return (
    Number.isSafeInteger(mention.startOffset) &&
    Number.isSafeInteger(mention.endOffset) &&
    mention.startOffset >= 0 &&
    mention.endOffset > mention.startOffset &&
    mention.endOffset <= codePoints.length &&
    codePoints.slice(mention.startOffset, mention.endOffset).join("") === mention.surfaceText
  );
}

function seedRejectionReason(mention: IdentityEvidenceMention, spanValid: boolean) {
  if (!spanValid) return "span_text_mismatch";
  if (mention.boundaryQuality === "malformed" || hasMalformedLexicalBoundary(mention.surfaceText)) return "malformed_span";
  if (mention.entityType === "non_person") return "non_person_evidence";
  if (mention.mentionKind === "pronoun") return "pronoun_cannot_seed";
  if (mention.mentionKind === "nominal") return "non_name_cannot_seed";
  if (isBlockedDiscourseSurface(mention.surfaceText)) return "blocked_surface";
  if (isGenericRoleSurface(mention.surfaceText)) return "generic_role_cannot_seed";
  return "insufficient_seed_evidence";
}

function aliasRows(mentions: MentionDecision[], characterKey: string) {
  const rows = new Map<string, { surfaceForm: string; normalizedForm: string; evidenceCount: number }>();
  for (const mention of mentions) {
    if (mention.characterKey !== characterKey || mention.mentionKind !== "proper_name") continue;
    const normalizedForm = normalizeIdentityName(mention.surfaceText);
    if (!normalizedForm) continue;
    const current = rows.get(normalizedForm);
    if (current) {
      current.evidenceCount += 1;
      if (mention.surfaceText.length > current.surfaceForm.length) current.surfaceForm = mention.surfaceText;
    } else {
      rows.set(normalizedForm, { surfaceForm: mention.surfaceText, normalizedForm, evidenceCount: 1 });
    }
  }
  return [...rows.values()].sort((a, b) => b.evidenceCount - a.evidenceCount || a.normalizedForm.localeCompare(b.normalizedForm, "en"));
}

function baseDecision(mention: IdentityEvidenceMention) {
  return {
    evidenceId: mention.evidenceId,
    surfaceText: mention.surfaceText,
    startOffset: mention.startOffset,
    endOffset: mention.endOffset,
    structuralLocator: mention.structuralLocator,
    mentionKind: mention.mentionKind,
  };
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

  const spanValidity = new Map<string, boolean>();
  const seeds: SeedCandidate[] = [];
  for (const mention of mentions) {
    const spanValid = spanMatchesNormalizedText(mention, codePoints);
    spanValidity.set(mention.evidenceId, spanValid);
    if (!spanValid || !isCanonicalSeedCandidate(mention)) continue;
    const compareTokens = comparisonTokens(mention.surfaceText);
    seeds.push({ mention, compareTokens, compareKey: compareTokens.join(" ") });
  }

  const groups: SeedGroup[] = [];
  const seedGroupByEvidence = new Map<string, SeedGroup>();
  const ambiguousSeedIds = new Set<string>();

  for (const seed of seeds.filter((value) => value.compareTokens.length > 1)) {
    const matches = groups.filter((group) => groupCompatible(group, seed));
    if (matches.length === 1) {
      matches[0]!.seeds.push(seed);
      seedGroupByEvidence.set(seed.mention.evidenceId, matches[0]!);
    } else if (matches.length === 0) {
      const group: SeedGroup = { seeds: [seed] };
      groups.push(group);
      seedGroupByEvidence.set(seed.mention.evidenceId, group);
    } else {
      ambiguousSeedIds.add(seed.mention.evidenceId);
    }
  }

  for (const seed of seeds.filter((value) => value.compareTokens.length === 1)) {
    const clustered = groups.filter((group) => groupCompatible(group, seed) && group.seeds.some((member) => sameProviderCluster(member, seed)));
    const matches = clustered.length > 0 ? clustered : groups.filter((group) => groupCompatible(group, seed));
    if (matches.length === 1) {
      matches[0]!.seeds.push(seed);
      seedGroupByEvidence.set(seed.mention.evidenceId, matches[0]!);
    } else if (matches.length > 1) {
      ambiguousSeedIds.add(seed.mention.evidenceId);
    } else {
      const exact = groups.find((group) =>
        group.seeds.every((member) => member.compareKey === seed.compareKey) &&
        group.seeds.every((member) => sameProviderCluster(member, seed) || (member.mention.providerClusterId === null && seed.mention.providerClusterId === null)),
      );
      if (exact) {
        exact.seeds.push(seed);
        seedGroupByEvidence.set(seed.mention.evidenceId, exact);
      } else {
        const group: SeedGroup = { seeds: [seed] };
        groups.push(group);
        seedGroupByEvidence.set(seed.mention.evidenceId, group);
      }
    }
  }

  const groupKey = new Map(groups.map((group) => [group, semanticCharacterKey(input.evidence.normalizedInputFingerprint, group)]));
  const byCluster = new Map<string, Set<SeedGroup>>();
  const byName = new Map<string, Set<SeedGroup>>();
  for (const group of groups) {
    for (const seed of group.seeds) {
      if (seed.mention.providerClusterId) {
        const set = byCluster.get(seed.mention.providerClusterId) ?? new Set<SeedGroup>();
        set.add(group);
        byCluster.set(seed.mention.providerClusterId, set);
      }
      const names = byName.get(seed.compareKey) ?? new Set<SeedGroup>();
      names.add(group);
      byName.set(seed.compareKey, names);
    }
  }

  const decisions: MentionDecision[] = [];
  for (const mention of mentions) {
    const compareKey = mention.mentionKind === "proper_name" ? normalizeIdentityName(mention.surfaceText) : null;
    const seedGroup = seedGroupByEvidence.get(mention.evidenceId);
    if (seedGroup) {
      decisions.push({ ...baseDecision(mention), characterKey: groupKey.get(seedGroup)!, resolutionState: "linked", evidenceTier: "canonical_seed", decisionReason: "accepted_canonical_seed", compareKey });
      continue;
    }
    if (ambiguousSeedIds.has(mention.evidenceId)) {
      decisions.push({ ...baseDecision(mention), characterKey: null, resolutionState: "unresolved", evidenceTier: "attachment", decisionReason: "ambiguous_seed_name", compareKey });
      continue;
    }

    const rejection = seedRejectionReason(mention, spanValidity.get(mention.evidenceId) === true);
    if (["span_text_mismatch", "malformed_span", "non_person_evidence", "blocked_surface", "generic_role_cannot_seed"].includes(rejection)) {
      decisions.push({ ...baseDecision(mention), characterKey: null, resolutionState: "quarantined", evidenceTier: "quarantined", decisionReason: rejection, compareKey });
      continue;
    }

    let attachmentGroups = mention.providerClusterId ? new Set(byCluster.get(mention.providerClusterId) ?? []) : new Set<SeedGroup>();
    if (attachmentGroups.size === 0 && compareKey) attachmentGroups = new Set(byName.get(compareKey) ?? []);
    if (attachmentGroups.size === 1) {
      const group = [...attachmentGroups][0]!;
      decisions.push({ ...baseDecision(mention), characterKey: groupKey.get(group)!, resolutionState: "linked", evidenceTier: "attachment", decisionReason: mention.providerClusterId ? "unique_provider_cluster_attachment" : "unique_name_attachment", compareKey });
    } else {
      decisions.push({ ...baseDecision(mention), characterKey: null, resolutionState: "unresolved", evidenceTier: "attachment", decisionReason: attachmentGroups.size > 1 ? "ambiguous_provider_cluster" : rejection, compareKey });
    }
  }

  const characters = groups.map<ResolvedCharacter>((group) => {
    const characterKey = groupKey.get(group)!;
    const linked = decisions.filter((mention) => mention.characterKey === characterKey);
    const firstSeed = Math.min(...group.seeds.map((seed) => seed.mention.startOffset));
    const stabilized = linked.some((mention) => mention.evidenceTier === "attachment" && mention.startOffset < firstSeed);
    return {
      characterKey,
      canonicalName: chooseCanonicalName(group),
      admissionTier: stabilized ? "stabilized" : "canonical_seed",
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
  return { ...fingerprintPayload, outputFingerprint: sha256Hex(canonicalJson(fingerprintPayload)) };
}
