import { createClient, type SupabaseClient } from "@supabase/supabase-js";

import type { NormalizationResult, SourceFormat } from "../ingestion/types.js";
import type { WorkerRuntimeConfig } from "./config.js";

export type ClaimedIngestionJob = {
  jobId: string;
  projectId: string;
  sourceId: string;
  ownerUserId: string;
  inputFingerprint: string;
  attemptCount: number;
  leaseToken: string;
};

export type IngestionSource = {
  id: string;
  projectId: string;
  ownerUserId: string;
  objectKey: string;
  format: SourceFormat;
  mediaType: string;
  byteSize: number;
  contentSha256: string;
};

type RpcRow = Record<string, unknown>;

function oneRow(data: unknown): RpcRow | null {
  const row = Array.isArray(data) ? data[0] : data;
  return row && typeof row === "object" ? (row as RpcRow) : null;
}

function requireString(row: RpcRow, key: string) {
  const value = row[key];
  if (typeof value !== "string") throw new Error(`invalid_database_row:${key}`);
  return value;
}

function requireNumber(row: RpcRow, key: string) {
  const value = row[key];
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new Error(`invalid_database_row:${key}`);
  }
  return value;
}

export class WorkerDatabase {
  readonly #client: SupabaseClient;

  constructor(config: WorkerRuntimeConfig) {
    this.#client = createClient(config.supabaseUrl, config.supabaseServiceRoleKey, {
      auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false },
    });
  }

  async claimSourceIngestionJob(workerId: string, leaseSeconds: number) {
    const { data, error } = await this.#client.rpc("saga_claim_analysis_job_kind", {
      p_worker_id: workerId,
      p_kind: "source_ingestion",
      p_lease_seconds: leaseSeconds,
    });
    if (error) throw new Error(`claim_failed:${error.message}`);
    const row = oneRow(data);
    if (!row) return null;
    if (requireString(row, "job_kind") !== "source_ingestion") {
      throw new Error("claim_returned_wrong_job_kind");
    }
    return {
      jobId: requireString(row, "job_id"),
      projectId: requireString(row, "project_id"),
      sourceId: requireString(row, "source_id"),
      ownerUserId: requireString(row, "owner_user_id"),
      inputFingerprint: requireString(row, "input_fingerprint"),
      attemptCount: requireNumber(row, "attempt_count"),
      leaseToken: requireString(row, "lease_token"),
    } satisfies ClaimedIngestionJob;
  }

  async getSource(job: ClaimedIngestionJob): Promise<IngestionSource> {
    const { data, error } = await this.#client
      .from("saga_sources")
      .select(
        "id,project_id,owner_user_id,object_key,source_format,media_type,byte_size,content_sha256",
      )
      .eq("id", job.sourceId)
      .eq("project_id", job.projectId)
      .eq("owner_user_id", job.ownerUserId)
      .single();
    if (error || !data) throw new Error(`source_lookup_failed:${error?.message ?? "missing"}`);

    const row = data as RpcRow;
    const format = requireString(row, "source_format");
    if (format !== "txt" && format !== "epub") throw new Error("unsupported_source_format");

    return {
      id: requireString(row, "id"),
      projectId: requireString(row, "project_id"),
      ownerUserId: requireString(row, "owner_user_id"),
      objectKey: requireString(row, "object_key"),
      format,
      mediaType: requireString(row, "media_type"),
      byteSize: requireNumber(row, "byte_size"),
      contentSha256: requireString(row, "content_sha256"),
    };
  }

  async renewLease(job: ClaimedIngestionJob, leaseSeconds: number) {
    const { data, error } = await this.#client.rpc("saga_renew_analysis_job_lease", {
      p_job_id: job.jobId,
      p_lease_token: job.leaseToken,
      p_lease_seconds: leaseSeconds,
    });
    if (error) throw new Error(`lease_renew_failed:${error.message}`);
    if (data !== true) throw new Error("stale_lease");
  }

  async markProcessing(job: ClaimedIngestionJob) {
    const { data, error } = await this.#client.rpc("saga_service_mark_source_processing", {
      p_job_id: job.jobId,
      p_lease_token: job.leaseToken,
    });
    if (error) throw new Error(`mark_processing_failed:${error.message}`);
    if (data !== true) throw new Error("stale_lease");
  }

  async commitSuccess(job: ClaimedIngestionJob, result: NormalizationResult) {
    const { data, error } = await this.#client.rpc("saga_service_commit_ingestion_success", {
      p_job_id: job.jobId,
      p_lease_token: job.leaseToken,
      p_normalization_version: result.normalizationVersion,
      p_config_fingerprint: result.configFingerprint,
      p_normalized_sha256: result.normalizedSha256,
      p_output_fingerprint: result.outputFingerprint,
      p_sections: result.sections,
    });
    if (error) throw new Error(`commit_success_failed:${error.message}`);
    if (typeof data !== "string") throw new Error("commit_success_missing_run_id");
    return data;
  }

  async commitTerminalFailure(
    job: ClaimedIngestionJob,
    engineVersion: string,
    configFingerprint: string,
    failureCode: string,
    summary: string,
  ) {
    const { data, error } = await this.#client.rpc("saga_service_commit_ingestion_failure", {
      p_job_id: job.jobId,
      p_lease_token: job.leaseToken,
      p_engine_version: engineVersion,
      p_config_fingerprint: configFingerprint,
      p_failure_code: failureCode,
      p_error_summary: summary.slice(0, 1000),
    });
    if (error) throw new Error(`commit_failure_failed:${error.message}`);
    if (typeof data !== "string") throw new Error("commit_failure_missing_run_id");
    return data;
  }

  async requeueTransientFailure(job: ClaimedIngestionJob, summary: string) {
    const { data, error } = await this.#client.rpc("saga_finish_analysis_job", {
      p_job_id: job.jobId,
      p_lease_token: job.leaseToken,
      p_succeeded: false,
      p_retry: true,
      p_error_code: "transient_ingestion_error",
      p_error_summary: summary.slice(0, 1000),
      p_retry_delay_seconds: 30,
    });
    if (error) throw new Error(`requeue_failed:${error.message}`);
    return data;
  }
}
