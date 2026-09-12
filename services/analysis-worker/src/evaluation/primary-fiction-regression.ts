import { normalizeIdentityName } from "../identity/resolver.js";
import type { CharacterIdentityResult, ResolvedCharacter } from "../identity/types.js";

export type PrimaryFictionRegressionScope =
  | { kind: "full_book" }
  | {
      kind: "bounded_epub";
      maxChapters: number;
      maxWindows: number;
      paragraphsPerWindow: number;
      overlapParagraphs: number;
    };

export type PrimaryFictionRegressionCase = {
  caseId: string;
  bookId: string;
  title: string;
  scope: PrimaryFictionRegressionScope;
  mustCanonicalSurfaces: string[];
  mustMergeSurfaceGroups: string[][];
  forbiddenCanonicalSurfaces: string[];
  forbiddenLinkedSurfaces: string[];
  notes: string[];
};

export type PrimaryFictionRegressionManifest = {
  schemaVersion: "saga-primary-fiction-regressions-v1";
  sourcePolicy: string;
  cases: PrimaryFictionRegressionCase[];
};

export type PrimaryFictionRegressionAssertion = {
  kind: "must_canonical" | "must_merge" | "forbidden_canonical" | "forbidden_link";
  label: string;
  passed: boolean;
  details: string;
};

export type PrimaryFictionRegressionReport = {
  schemaVersion: "saga-primary-fiction-regression-report-v1";
  caseId: string;
  bookId: string;
  provider: CharacterIdentityResult["provider"];
  normalizedInputFingerprint: string;
  identityOutputFingerprint: string;
  assertionCount: number;
  passedAssertionCount: number;
  failedAssertionCount: number;
  passRate: number;
  passed: boolean;
  assertions: PrimaryFictionRegressionAssertion[];
};

function normalizeExactSurface(surface: string) {
  return surface
    .normalize("NFKC")
    .toLocaleLowerCase("en-US")
    .replace(/[’‘`]/g, "'")
    .replace(/[‐‑‒–—]/g, "-")
    .replace(/[^\p{L}\p{M}'-]+/gu, " ")
    .trim()
    .replace(/\s+/gu, " ");
}

function characterExactSurfaces(character: ResolvedCharacter) {
  return new Set([
    normalizeExactSurface(character.canonicalName),
    ...character.aliases.map((alias) => normalizeExactSurface(alias.surfaceForm)),
  ].filter(Boolean));
}

function characterIdentitySurfaces(character: ResolvedCharacter) {
  return new Set([
    normalizeIdentityName(character.canonicalName),
    ...character.aliases.map((alias) => alias.normalizedForm || normalizeIdentityName(alias.surfaceForm)),
  ].filter(Boolean));
}

function matchingCharacterKeys(result: CharacterIdentityResult, surface: string) {
  const exact = normalizeExactSurface(surface);
  const identity = normalizeIdentityName(surface);
  const keys = new Set<string>();
  for (const character of result.characters) {
    const exactSurfaces = characterExactSurfaces(character);
    const identitySurfaces = characterIdentitySurfaces(character);
    if (exactSurfaces.has(exact) || (identity && identitySurfaces.has(identity))) {
      keys.add(character.characterKey);
    }
  }
  return keys;
}

function exactSurfaceObservedOnCharacter(character: ResolvedCharacter, surface: string) {
  return characterExactSurfaces(character).has(normalizeExactSurface(surface));
}

function characterByKey(result: CharacterIdentityResult, key: string) {
  return result.characters.find((character) => character.characterKey === key) ?? null;
}

function linkedMentionCount(result: CharacterIdentityResult, surface: string) {
  const expected = normalizeExactSurface(surface);
  return result.mentions.filter((mention) =>
    mention.resolutionState === "linked" && normalizeExactSurface(mention.surfaceText) === expected,
  ).length;
}

export function validatePrimaryFictionRegressionManifest(manifest: PrimaryFictionRegressionManifest) {
  if (manifest.schemaVersion !== "saga-primary-fiction-regressions-v1") {
    throw new Error("unsupported_primary_fiction_regression_manifest");
  }
  if (!manifest.sourcePolicy.trim()) throw new Error("missing_primary_fiction_source_policy");
  if (manifest.cases.length === 0) throw new Error("empty_primary_fiction_regression_manifest");

  const caseIds = new Set<string>();
  for (const regressionCase of manifest.cases) {
    if (!/^[a-z0-9][a-z0-9-]*$/u.test(regressionCase.caseId)) {
      throw new Error(`invalid_primary_fiction_case_id:${regressionCase.caseId}`);
    }
    if (caseIds.has(regressionCase.caseId)) {
      throw new Error(`duplicate_primary_fiction_case_id:${regressionCase.caseId}`);
    }
    caseIds.add(regressionCase.caseId);
    if (!regressionCase.bookId.trim() || !regressionCase.title.trim()) {
      throw new Error(`invalid_primary_fiction_case_metadata:${regressionCase.caseId}`);
    }
    if (regressionCase.scope.kind === "bounded_epub") {
      for (const [name, value] of Object.entries(regressionCase.scope).filter(([name]) => name !== "kind")) {
        if (!Number.isSafeInteger(value) || Number(value) < 0) {
          throw new Error(`invalid_primary_fiction_scope:${regressionCase.caseId}:${name}`);
        }
      }
      if (regressionCase.scope.maxChapters < 1 || regressionCase.scope.maxWindows < 1 || regressionCase.scope.paragraphsPerWindow < 1) {
        throw new Error(`invalid_primary_fiction_scope:${regressionCase.caseId}:non_positive_limit`);
      }
    }
    for (const group of regressionCase.mustMergeSurfaceGroups) {
      if (group.length < 2 || group.some((surface) => !surface.trim())) {
        throw new Error(`invalid_primary_fiction_merge_group:${regressionCase.caseId}`);
      }
    }
  }
}

export function evaluatePrimaryFictionRegression(input: {
  regressionCase: PrimaryFictionRegressionCase;
  result: CharacterIdentityResult;
}): PrimaryFictionRegressionReport {
  const assertions: PrimaryFictionRegressionAssertion[] = [];

  for (const surface of input.regressionCase.mustCanonicalSurfaces) {
    const keys = matchingCharacterKeys(input.result, surface);
    assertions.push({
      kind: "must_canonical",
      label: surface,
      passed: keys.size === 1,
      details: keys.size === 1
        ? `surface maps to one canonical character (${[...keys][0]})`
        : `expected exactly one canonical character, observed ${keys.size}`,
    });
  }

  for (const group of input.regressionCase.mustMergeSurfaceGroups) {
    const observedBySurface = group.map((surface) => {
      const keys = matchingCharacterKeys(input.result, surface);
      const exactKeys = [...keys].filter((key) => {
        const character = characterByKey(input.result, key);
        return character !== null && exactSurfaceObservedOnCharacter(character, surface);
      });
      return { surface, keys: new Set(exactKeys) };
    });
    const allObserved = observedBySurface.every((entry) => entry.keys.size > 0);
    const union = new Set(observedBySurface.flatMap((entry) => [...entry.keys]));
    const oneSharedCharacter = union.size === 1 && observedBySurface.every((entry) => entry.keys.has([...union][0]!));
    assertions.push({
      kind: "must_merge",
      label: group.join(" ↔ "),
      passed: allObserved && oneSharedCharacter,
      details: allObserved
        ? oneSharedCharacter
          ? `all variants observed on one canonical character (${[...union][0]})`
          : `variants span ${union.size} canonical characters`
        : `missing exact variant(s): ${observedBySurface.filter((entry) => entry.keys.size === 0).map((entry) => entry.surface).join(", ")}`,
    });
  }

  for (const surface of input.regressionCase.forbiddenCanonicalSurfaces) {
    const keys = matchingCharacterKeys(input.result, surface);
    assertions.push({
      kind: "forbidden_canonical",
      label: surface,
      passed: keys.size === 0,
      details: keys.size === 0
        ? "surface is absent from canonical character identities"
        : `surface maps to ${keys.size} canonical character(s): ${[...keys].join(", ")}`,
    });
  }

  for (const surface of input.regressionCase.forbiddenLinkedSurfaces) {
    const linked = linkedMentionCount(input.result, surface);
    assertions.push({
      kind: "forbidden_link",
      label: surface,
      passed: linked === 0,
      details: linked === 0 ? "no exact-surface mention linked to a character" : `${linked} exact-surface linked mention(s) observed`,
    });
  }

  const passedAssertionCount = assertions.filter((assertion) => assertion.passed).length;
  const failedAssertionCount = assertions.length - passedAssertionCount;
  return {
    schemaVersion: "saga-primary-fiction-regression-report-v1",
    caseId: input.regressionCase.caseId,
    bookId: input.regressionCase.bookId,
    provider: input.result.provider,
    normalizedInputFingerprint: input.result.normalizedInputFingerprint,
    identityOutputFingerprint: input.result.outputFingerprint,
    assertionCount: assertions.length,
    passedAssertionCount,
    failedAssertionCount,
    passRate: assertions.length === 0 ? 1 : passedAssertionCount / assertions.length,
    passed: failedAssertionCount === 0,
    assertions,
  };
}
