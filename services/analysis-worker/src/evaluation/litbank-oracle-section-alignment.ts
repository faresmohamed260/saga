import { canonicalJson, sha256Hex } from "../ingestion/hash.js";
import type { NormalizedSection } from "../ingestion/types.js";
import type { CharacterIdentityResult } from "../identity/types.js";

/**
 * LitBank oracle identity is benchmark-only evidence. Its historical fixture
 * locator used only the section key, while provider evidence uses the normal
 * S.A.G.A. structural-locator form `${stable_key}:${source_locator}`.
 *
 * Align only the benchmark oracle to that canonical single-section locator;
 * production identity/syntax matching remains strict and unchanged.
 */
export function alignSingleSectionOracleIdentity(input: {
  identity: CharacterIdentityResult;
  section: NormalizedSection;
}): CharacterIdentityResult {
  const { identity, section } = input;
  for (const mention of identity.mentions) {
    if (mention.startOffset < section.start_offset || mention.endOffset > section.end_offset) {
      throw new Error(`oracle_identity_mention_outside_section:${mention.evidenceId}`);
    }
  }

  const structuralLocator = `${section.stable_key}:${section.source_locator}`;
  const mentions = identity.mentions.map((mention) => ({ ...mention, structuralLocator }));
  const semantic = { characters: identity.characters, mentions };
  return {
    ...identity,
    mentions,
    outputFingerprint: sha256Hex(canonicalJson(semantic)),
  };
}
