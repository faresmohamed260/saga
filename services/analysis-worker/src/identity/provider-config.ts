import { HttpCharacterEvidenceProvider } from "./http-provider.js";
import type { CharacterEvidenceProvider } from "./types.js";

function optional(name: string) {
  return process.env[name]?.trim() || null;
}

export function createConfiguredIdentityEvidenceProvider(): CharacterEvidenceProvider | null {
  const url = optional("SAGA_IDENTITY_PROVIDER_URL");
  if (!url) return null;

  const name = optional("SAGA_IDENTITY_PROVIDER_NAME");
  const revision = optional("SAGA_IDENTITY_PROVIDER_REVISION");
  if (!name || !revision) {
    throw new Error(
      "SAGA_IDENTITY_PROVIDER_NAME and SAGA_IDENTITY_PROVIDER_REVISION are required when SAGA_IDENTITY_PROVIDER_URL is configured.",
    );
  }

  return new HttpCharacterEvidenceProvider({
    url,
    descriptor: {
      name,
      model: optional("SAGA_IDENTITY_PROVIDER_MODEL"),
      revision,
    },
    bearerToken: optional("SAGA_IDENTITY_PROVIDER_BEARER_TOKEN"),
  });
}
