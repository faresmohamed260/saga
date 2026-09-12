import {
  IDENTITY_RESOLVER_CONFIG_FINGERPRINT,
  IDENTITY_RESOLVER_VERSION,
  resolveCharacterIdentity,
} from "./identity/resolver.js";
import { IdentityEvidenceProviderError } from "./identity/http-provider.js";
import type { CharacterEvidenceProvider } from "./identity/types.js";
import type { ClaimedIdentityJob, WorkerDatabase } from "./runtime/database.js";

export type IdentityDatabase = Pick<
  WorkerDatabase,
  | "claimCharacterIdentityJob"
  | "getIdentityInput"
  | "renewLease"
  | "commitIdentitySuccess"
  | "commitIdentityTerminalFailure"
  | "requeueTransientFailure"
>;

export type IdentityProcessResult =
  | { status: "no_work" }
  | { status: "succeeded"; jobId: string; runId: string }
  | { status: "failed"; jobId: string; failureCode: string }
  | { status: "requeued"; jobId: string };

class TerminalIdentityError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = "TerminalIdentityError";
    this.code = code;
  }
}

function terminalResolverError(error: unknown) {
  if (!(error instanceof Error)) return null;
  if (
    error.message.startsWith("invalid_identity_") ||
    error.message.startsWith("duplicate_or_missing_identity_")
  ) {
    return new TerminalIdentityError("invalid_provider_evidence", error.message);
  }
  return null;
}

async function commitTerminal(
  database: IdentityDatabase,
  provider: CharacterEvidenceProvider,
  job: ClaimedIdentityJob,
  error: TerminalIdentityError,
): Promise<IdentityProcessResult> {
  await database.commitIdentityTerminalFailure(job, {
    resolverVersion: IDENTITY_RESOLVER_VERSION,
    configFingerprint: IDENTITY_RESOLVER_CONFIG_FINGERPRINT,
    provider: provider.descriptor,
    failureCode: error.code,
    summary: error.message,
  });
  return { status: "failed", jobId: job.jobId, failureCode: error.code };
}

export async function processOneCharacterIdentityJob(input: {
  database: IdentityDatabase;
  provider: CharacterEvidenceProvider;
  workerId: string;
  leaseSeconds: number;
}): Promise<IdentityProcessResult> {
  const job = await input.database.claimCharacterIdentityJob(input.workerId, input.leaseSeconds);
  if (!job) return { status: "no_work" };

  try {
    const source = await input.database.getIdentityInput(job);
    await input.database.renewLease(job, input.leaseSeconds);

    const evidence = await input.provider.collect({
      normalizedInputFingerprint: source.normalizedInputFingerprint,
      normalizedText: source.normalizedText,
      sections: source.sections,
    });

    if (evidence.normalizedInputFingerprint !== source.normalizedInputFingerprint) {
      throw new TerminalIdentityError(
        "provider_input_fingerprint_mismatch",
        "Identity evidence provider returned evidence for a different normalized input fingerprint.",
      );
    }

    let result;
    try {
      result = resolveCharacterIdentity({
        normalizedText: source.normalizedText,
        evidence,
      });
    } catch (error) {
      const terminal = terminalResolverError(error);
      if (terminal) throw terminal;
      throw error;
    }

    await input.database.renewLease(job, input.leaseSeconds);
    const runId = await input.database.commitIdentitySuccess(job, result);
    return { status: "succeeded", jobId: job.jobId, runId };
  } catch (error) {
    if (error instanceof TerminalIdentityError) {
      return commitTerminal(input.database, input.provider, job, error);
    }
    if (error instanceof IdentityEvidenceProviderError && !error.retryable) {
      return commitTerminal(
        input.database,
        input.provider,
        job,
        new TerminalIdentityError("invalid_provider_evidence", error.message),
      );
    }
    if (
      error instanceof Error &&
      (error.message.startsWith("identity_input_run_missing:") ||
        error.message.startsWith("identity_input_sections_missing:") ||
        error.message === "identity_input_reconstruction_fingerprint_mismatch")
    ) {
      return commitTerminal(
        input.database,
        input.provider,
        job,
        new TerminalIdentityError("identity_input_invalid", error.message),
      );
    }

    const summary = error instanceof Error ? error.message : "Unknown character identity runtime error";
    const state = await input.database.requeueTransientFailure(
      job,
      summary,
      "transient_identity_error",
    );
    if (state === "queued") return { status: "requeued", jobId: job.jobId };
    return { status: "failed", jobId: job.jobId, failureCode: "transient_identity_error" };
  }
}
