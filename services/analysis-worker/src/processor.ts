import {
  NORMALIZATION_CONFIG_FINGERPRINT,
  NORMALIZATION_VERSION,
  normalizeSource,
} from "./ingestion/normalize.js";
import { NormalizationError } from "./ingestion/types.js";
import type {
  ClaimedIngestionJob,
  IngestionSource,
  WorkerDatabase,
} from "./runtime/database.js";
import type { SourceObjectReader } from "./runtime/storage.js";

export type IngestionDatabase = Pick<
  WorkerDatabase,
  | "claimSourceIngestionJob"
  | "getSource"
  | "renewLease"
  | "markProcessing"
  | "commitSuccess"
  | "commitTerminalFailure"
  | "requeueTransientFailure"
>;

export type ProcessResult =
  | { status: "no_work" }
  | { status: "succeeded"; jobId: string; runId: string }
  | { status: "failed"; jobId: string; failureCode: string }
  | { status: "requeued"; jobId: string };

class TerminalIngestionError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = "TerminalIngestionError";
    this.code = code;
  }
}

function validateClaimAgainstSource(job: ClaimedIngestionJob, source: IngestionSource) {
  if (job.inputFingerprint !== source.contentSha256) {
    throw new TerminalIngestionError(
      "input_fingerprint_mismatch",
      "The queued ingestion fingerprint no longer matches the immutable source fingerprint.",
    );
  }
}

async function commitTerminal(
  database: IngestionDatabase,
  job: ClaimedIngestionJob,
  error: NormalizationError | TerminalIngestionError,
): Promise<ProcessResult> {
  await database.commitTerminalFailure(
    job,
    NORMALIZATION_VERSION,
    NORMALIZATION_CONFIG_FINGERPRINT,
    error.code,
    error.message,
  );
  return { status: "failed", jobId: job.jobId, failureCode: error.code };
}

export async function processOneSourceIngestionJob(input: {
  database: IngestionDatabase;
  storage: SourceObjectReader;
  workerId: string;
  leaseSeconds: number;
}): Promise<ProcessResult> {
  const job = await input.database.claimSourceIngestionJob(
    input.workerId,
    input.leaseSeconds,
  );
  if (!job) return { status: "no_work" };

  try {
    const source = await input.database.getSource(job);
    validateClaimAgainstSource(job, source);

    await input.database.markProcessing(job);
    await input.database.renewLease(job, input.leaseSeconds);

    const object = await input.storage.read(source.objectKey, source.byteSize);
    if (object.contentType && object.contentType !== source.mediaType) {
      throw new TerminalIngestionError(
        "object_metadata_changed",
        `Stored source content type changed from ${source.mediaType} to ${object.contentType}.`,
      );
    }

    const result = normalizeSource({
      bytes: object.bytes,
      format: source.format,
      expectedSha256: source.contentSha256,
    });

    await input.database.renewLease(job, input.leaseSeconds);
    const runId = await input.database.commitSuccess(job, result);
    return { status: "succeeded", jobId: job.jobId, runId };
  } catch (error) {
    if (error instanceof NormalizationError || error instanceof TerminalIngestionError) {
      return commitTerminal(input.database, job, error);
    }

    const summary = error instanceof Error ? error.message : "Unknown ingestion runtime error";
    const state = await input.database.requeueTransientFailure(job, summary);
    if (state === "queued") return { status: "requeued", jobId: job.jobId };
    return { status: "failed", jobId: job.jobId, failureCode: "transient_ingestion_error" };
  }
}
