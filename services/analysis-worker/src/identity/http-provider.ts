import type { NormalizedSection } from "../ingestion/types.js";
import type {
  CharacterEvidenceProvider,
  IdentityBoundaryQuality,
  IdentityEntityType,
  IdentityEvidenceMention,
  IdentityMentionKind,
  IdentityPersonEvidence,
  IdentityProviderDescriptor,
  NormalizedIdentityEvidence,
} from "./types.js";

const mentionKinds = new Set<IdentityMentionKind>(["proper_name", "nominal", "pronoun"]);
const entityTypes = new Set<IdentityEntityType>(["person", "non_person", "unknown"]);
const personEvidenceValues = new Set<IdentityPersonEvidence>(["strong", "supporting", "weak", "none"]);
const boundaryQualities = new Set<IdentityBoundaryQuality>(["clean", "malformed"]);

export class IdentityEvidenceProviderError extends Error {
  readonly retryable: boolean;

  constructor(message: string, retryable: boolean) {
    super(message);
    this.name = "IdentityEvidenceProviderError";
    this.retryable = retryable;
  }
}

function parseMention(value: unknown): IdentityEvidenceMention {
  if (!value || typeof value !== "object") {
    throw new IdentityEvidenceProviderError("invalid_provider_mention", false);
  }
  const row = value as Record<string, unknown>;
  if (
    typeof row.evidenceId !== "string" ||
    typeof row.surfaceText !== "string" ||
    typeof row.startOffset !== "number" ||
    !Number.isSafeInteger(row.startOffset) ||
    typeof row.endOffset !== "number" ||
    !Number.isSafeInteger(row.endOffset) ||
    (row.structuralLocator !== null && typeof row.structuralLocator !== "string") ||
    !mentionKinds.has(row.mentionKind as IdentityMentionKind) ||
    !entityTypes.has(row.entityType as IdentityEntityType) ||
    !personEvidenceValues.has(row.personEvidence as IdentityPersonEvidence) ||
    !boundaryQualities.has(row.boundaryQuality as IdentityBoundaryQuality) ||
    (row.providerClusterId !== null && typeof row.providerClusterId !== "string")
  ) {
    throw new IdentityEvidenceProviderError("invalid_provider_mention", false);
  }

  return {
    evidenceId: row.evidenceId,
    surfaceText: row.surfaceText,
    startOffset: row.startOffset,
    endOffset: row.endOffset,
    structuralLocator: row.structuralLocator as string | null,
    mentionKind: row.mentionKind as IdentityMentionKind,
    entityType: row.entityType as IdentityEntityType,
    personEvidence: row.personEvidence as IdentityPersonEvidence,
    boundaryQuality: row.boundaryQuality as IdentityBoundaryQuality,
    providerClusterId: row.providerClusterId as string | null,
  };
}

export class HttpCharacterEvidenceProvider implements CharacterEvidenceProvider {
  readonly descriptor: IdentityProviderDescriptor;
  readonly #url: URL;
  readonly #bearerToken: string | null;

  constructor(input: {
    url: string;
    descriptor: IdentityProviderDescriptor;
    bearerToken?: string | null;
  }) {
    this.#url = new URL(input.url);
    if (this.#url.protocol !== "https:" && this.#url.hostname !== "localhost" && this.#url.hostname !== "127.0.0.1") {
      throw new Error("Identity evidence provider URL must use HTTPS outside localhost.");
    }
    this.descriptor = input.descriptor;
    this.#bearerToken = input.bearerToken?.trim() || null;
  }

  async collect(input: {
    normalizedInputFingerprint: string;
    normalizedText: string;
    sections: NormalizedSection[];
  }): Promise<NormalizedIdentityEvidence> {
    let response: Response;
    try {
      response = await fetch(this.#url, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          ...(this.#bearerToken ? { authorization: `Bearer ${this.#bearerToken}` } : {}),
        },
        body: JSON.stringify(input),
        signal: AbortSignal.timeout(120_000),
      });
    } catch (error) {
      throw new IdentityEvidenceProviderError(
        `identity_provider_request_failed:${error instanceof Error ? error.message : String(error)}`,
        true,
      );
    }

    if (!response.ok) {
      throw new IdentityEvidenceProviderError(
        `identity_provider_http_${response.status}`,
        response.status === 408 || response.status === 429 || response.status >= 500,
      );
    }

    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      throw new IdentityEvidenceProviderError("identity_provider_invalid_json", false);
    }
    if (!payload || typeof payload !== "object") {
      throw new IdentityEvidenceProviderError("identity_provider_invalid_payload", false);
    }
    const row = payload as Record<string, unknown>;
    if (!Array.isArray(row.mentions)) {
      throw new IdentityEvidenceProviderError("identity_provider_missing_mentions", false);
    }

    return {
      provider: this.descriptor,
      normalizedInputFingerprint: input.normalizedInputFingerprint,
      mentions: row.mentions.map(parseMention),
    };
  }
}
