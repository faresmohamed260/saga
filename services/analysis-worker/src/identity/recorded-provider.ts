import type { NormalizedSection } from "../ingestion/types.js";
import type {
  CharacterEvidenceProvider,
  IdentityEvidenceMention,
  IdentityProviderDescriptor,
  NormalizedIdentityEvidence,
} from "./types.js";

/**
 * CI/evaluation provider for recorded normalized evidence.
 *
 * This is deliberately not a production NLP heuristic. It lets the S.A.G.A.
 * resolver policy be tested independently from heavyweight or provider-specific
 * model runtimes.
 */
export class RecordedIdentityEvidenceProvider implements CharacterEvidenceProvider {
  readonly descriptor: IdentityProviderDescriptor;
  readonly #mentions: IdentityEvidenceMention[];

  constructor(input: {
    descriptor?: IdentityProviderDescriptor;
    mentions: IdentityEvidenceMention[];
  }) {
    this.descriptor = input.descriptor ?? {
      name: "recorded-evidence",
      model: null,
      revision: "fixture-v1",
    };
    this.#mentions = structuredClone(input.mentions);
  }

  async collect(input: {
    normalizedInputFingerprint: string;
    normalizedText: string;
    sections: NormalizedSection[];
  }): Promise<NormalizedIdentityEvidence> {
    void input.normalizedText;
    void input.sections;
    return {
      provider: this.descriptor,
      normalizedInputFingerprint: input.normalizedInputFingerprint,
      mentions: structuredClone(this.#mentions),
    };
  }
}
