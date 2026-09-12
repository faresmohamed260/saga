import { createClient, type SupabaseClient } from "@supabase/supabase-js";

import { sha256Hex } from "../ingestion/hash.js";
import type { NormalizationResult, NormalizedSection, SourceFormat } from "../ingestion/types.js";
import type { CharacterIdentityResult, IdentityProviderDescriptor } from "../identity/types.js";
import type { WorkerRuntimeConfig } from "./config.js";

export type ClaimedAnalysisJob = {
  jobId: string;
  projectId: string;
  sourceId: string;
  ownerUserId: string;
  inputFingerprint: string;
  attemptCount: number;
  leaseToken: string;
};

export type ClaimedIngestionJob = ClaimedAnalysisJob;
export type ClaimedIdentityJob = ClaimedAnalysisJob;

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

export type IdentityInput = {
  normalizedInputFingerprint: string;
  normalizedText: string;
  sections: NormalizedSection[];
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

function nullableString(row: RpcRow, key: string) {
  const value = row[key];
  if (value === null || value === undefined) return null;
  if (typeof value !== "string") throw new Error(`invalid_database_row:${key}`);
  return value;
}

function requireNumber(row: RpcRow, key: string) {
  const value = row[key];
  if (typeof value !== "number" || !Number.isFinite(value)) throw new Error(`invalid_database_row:${key}`);
  return value;
}

function mapClaim(row: RpcRow): ClaimedAnalysisJob {
  return {
    jobId: requireString(row, "job_id"),
    projectId: requireString(row, "project_id"),
    sourceId: requireString(row, "source_id"),
    ownerUserId: requireString(row, "owner_user_id"),
    inputFingerprint: requireString(row, "input_fingerprint"),
    attemptCount: requireNumber(row, "attempt_count"),
    leaseToken: requireString(row, "lease_token"),
  };
}

function mapSection(row: RpcRow): NormalizedSection {
  const kind = requireString(row, "section_kind");
  if (kind !== "document" && kind !== "chapter" && kind !== "section") {
    throw new Error("invalid_database_row:section_kind");
  }
  return {
    stable_key: requireString(row, "stable_key"),
    ordinal: requireNumber(row, "ordinal"),
    section_kind: kind,
    title: nullableString(row, "title"),
    source_locator: requireString(row, "source_locator"),
    start_offset: requireNumber(row, "start_offset"),
    end_offset: requireNumber(row, "end_offset"),
    normalized_text: requireString(row, "normalized_text"),
  };
}

export class WorkerDatabase {
  readonly #client: SupabaseClient;

  constructor(config: WorkerRuntimeConfig) {
    this.#client = createClient(config.supabaseUrl, config.supabaseServiceRoleKey, {
      auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false },
    });
  }

  async #claimKind(kind: "source_ingestion" | "character_identity", workerId: string, leaseSeconds: number) {
    const { data, error } = await this.#client.rpc("saga_claim_analysis_job_kind", {
      p_worker_id: workerId,
      p_kind: kind,
      p_lease_seconds: leaseSeconds,
    });
    if (error) throw new Error(`claim_failed:${error.message}`);
    const row = oneRow(data);
    if (!row) return null;
    if (requireString(row, "job_kind") !== kind) throw new Error("claim_returned_wrong_job_kind");
    return mapClaim(row);
  }

  claimSourceIngestionJob(workerId: string, leaseSeconds: number) {
    return this.#claimKind("source_ingestion", workerId, leaseSeconds);
  }

  claimCharacterIdentityJob(workerId: string, leaseSeconds: number) {
    return this.#claimKind("character_identity", workerId, leaseSeconds);
  }

  async getSource(job: ClaimedIngestionJob): Promise<IngestionSource> {
    const { data, error } = await this.#client
      .from("saga_sources")
      .select("id,project_id,owner_user_id,object_key,source_format,media_type,byte_size,content_sha256")
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

  async getIdentityInput(job: ClaimedIdentityJob): Promise<IdentityInput> {
    const { data: runData, error: runError } = await this.#client
      .from("saga_analysis_runs")
      .select("id,normalized_input_fingerprint")
      .eq("project_id", job.projectId)
      .eq("source_id", job.sourceId)
      .eq("owner_user_id", job.ownerUserId)
      .eq("status", "succeeded")
      .eq("output_fingerprint", job.inputFingerprint)
      .order("completed_at", { ascending: false })
      .limit(1)
      .maybeSingle();
    if (runError || !runData) throw new Error(`identity_input_run_missing:${runError?.message ?? "missing"}`);

    const run = runData as RpcRow;
    const runId = requireString(run, "id");
    const normalizedInputFingerprint = requireString(run, "normalized_input_fingerprint");

    const { data: sectionData, error: sectionError } = await this.#client
      .from("saga_normalized_sections")
      .select("stable_key,ordinal,section_kind,title,source_locator,start_offset,end_offset,normalized_text")
      .eq("run_id", runId)
      .eq("project_id", job.projectId)
      .eq("source_id", job.sourceId)
      .eq("owner_user_id", job.ownerUserId)
      .order("ordinal", { ascending: true });
    if (sectionError || !sectionData || sectionData.length === 0) {
      throw new Error(`identity_input_sections_missing:${sectionError?.message ?? "missing"}`);
    }

    const sections = sectionData.map((row) => mapSection(row as RpcRow));
    const normalizedText = sections.map((section) => section.normalized_text).join("\n\n");
    if (sha256Hex(normalizedText) !== normalizedInputFingerprint) {
      throw new Error("identity_input_reconstruction_fingerprint_mismatch");
    }
    return { normalizedInputFingerprint, normalizedText, sections };
  }

  async renewLease(job: ClaimedAnalysisJob, leaseSeconds: number) {
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

  async commitIdentitySuccess(job: ClaimedIdentityJob, result: CharacterIdentityResult) {
    const { data, error } = await this.#client.rpc("saga_service_commit_identity_success", {
      p_job_id: job.jobId,
      p_lease_token: job.leaseToken,
      p_resolver_version: result.resolverVersion,
      p_provider_name: result.provider.name,
      p_provider_model: result.provider.model,
      p_provider_revision: result.provider.revision,
      p_config_fingerprint: result.resolverConfigFingerprint,
      p_output_fingerprint: result.outputFingerprint,
      p_characters: result.characters.map((character) => ({
        character_key: character.characterKey,
        canonical_name: character.canonicalName,
        admission_tier: character.admissionTier,
        evidence_count: character.evidenceCount,
        aliases: character.aliases.map((alias) => ({
          surface_form: alias.surfaceForm,
          normalized_form: alias.normalizedForm,
          evidence_count: alias.evidenceCount,
        })),
      })),
      p_mentions: result.mentions.map((mention) => ({
        evidence_id: mention.evidenceId,
        character_key: mention.characterKey,
        surface_text: mention.surfaceText,
        start_offset: mention.startOffset,
        end_offset: mention.endOffset,
        structural_locator: mention.structuralLocator,
        mention_kind: mention.mentionKind,
        resolution_state: mention.resolutionState,
        evidence_tier: mention.evidenceTier,
        decision_reason: mention.decisionReason,
      })),
    });
    if (error) throw new Error(`identity_commit_success_failed:${error.message}`);
    if (typeof data !== "string") throw new Error("identity_commit_success_missing_run_id");
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

  async commitIdentityTerminalFailure(
    job: ClaimedIdentityJob,
    input: {
      resolverVersion: string;
      configFingerprint: string;
      provider: IdentityProviderDescriptor;
      failureCode: string;
      summary: string;
    },
  ) {
    const { data, error } = await this.#client.rpc("saga_service_commit_identity_failure", {
      p_job_id: job.jobId,
      p_lease_token: job.leaseToken,
      p_resolver_version: input.resolverVersion,
      p_provider_name: input.provider.name,
      p_provider_model: input.provider.model,
      p_provider_revision: input.provider.revision,
      p_config_fingerprint: input.configFingerprint,
      p_failure_code: input.failureCode,
      p_error_summary: input.summary.slice(0, 1000),
    });
    if (error) throw new Error(`identity_commit_failure_failed:${error.message}`);
    if (typeof data !== "string") throw new Error("identity_commit_failure_missing_run_id");
    return data;
  }

  async requeueTransientFailure(job: ClaimedAnalysisJob, summary: string, errorCode = "transient_ingestion_error") {
    const { data, error } = await this.#client.rpc("saga_finish_analysis_job", {
      p_job_id: job.jobId,
      p_lease_token: job.leaseToken,
      p_succeeded: false,
      p_retry: true,
      p_error_code: errorCode,
      p_error_summary: summary.slice(0, 1000),
      p_retry_delay_seconds: 30,
    });
    if (error) throw new Error(`requeue_failed:${error.message}`);
    return data;
  }
}
