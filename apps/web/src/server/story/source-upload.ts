import "server-only";

import { requireCurrentSagaAccount } from "@/server/account/account-access";
import { createObjectStorage, storageConfigurationStatus } from "@/server/storage";
import { createSupabasePrivilegedClient } from "@/server/supabase/privileged";
import { createSupabaseServerClient } from "@/server/supabase/server";

import type { SagaSourceFormat } from "./story-data";

const DEFAULT_MAX_SOURCE_BYTES = 25 * 1024 * 1024;
const UPLOAD_URL_TTL_SECONDS = 300;
const READ_URL_TTL_SECONDS = 300;
const SHA256_PATTERN = /^[0-9a-f]{64}$/;

export type SagaSourceUploadErrorCode =
  | "invalid_request"
  | "not_found"
  | "storage_unavailable"
  | "upload_incomplete"
  | "upload_mismatch"
  | "unavailable";

export class SagaSourceUploadError extends Error {
  readonly code: SagaSourceUploadErrorCode;
  readonly httpStatus: number;

  constructor(code: SagaSourceUploadErrorCode, httpStatus: number) {
    super(code);
    this.name = "SagaSourceUploadError";
    this.code = code;
    this.httpStatus = httpStatus;
  }
}

export type SagaSourceUploadIntent = {
  sourceId: string;
  uploadUrl: string;
  expiresInSeconds: number;
  contentType: string;
  requiredHeaders: Record<string, string>;
};

export type SagaSourceUploadCompletion = {
  sourceId: string;
  sourceStatus: string;
  jobId: string | null;
  failureCode: string | null;
};

type UploadIntentRow = {
  source_id: unknown;
  object_key: unknown;
  media_type: unknown;
};

type SourceUploadRow = {
  id: unknown;
  object_key: unknown;
  original_filename: unknown;
  media_type: unknown;
  byte_size: unknown;
  content_sha256: unknown;
  ingestion_status: unknown;
};

type FinalizeRow = {
  source_id: unknown;
  source_status: unknown;
  job_id: unknown;
  result_failure_code: unknown;
};

function sourceMaxBytes() {
  const raw = process.env.SAGA_SOURCE_MAX_BYTES?.trim();
  if (!raw) return DEFAULT_MAX_SOURCE_BYTES;

  const parsed = Number(raw);
  if (!Number.isSafeInteger(parsed) || parsed <= 0) {
    throw new SagaSourceUploadError("unavailable", 503);
  }
  return parsed;
}

function expectedExtension(format: SagaSourceFormat) {
  return format === "txt" ? ".txt" : ".epub";
}

function validateUploadInput(input: {
  projectId: unknown;
  originalFilename: unknown;
  displayName: unknown;
  format: unknown;
  byteSize: unknown;
  contentSha256: unknown;
}) {
  if (
    typeof input.projectId !== "string" ||
    typeof input.originalFilename !== "string" ||
    typeof input.displayName !== "string" ||
    (input.format !== "txt" && input.format !== "epub") ||
    typeof input.byteSize !== "number" ||
    typeof input.contentSha256 !== "string"
  ) {
    throw new SagaSourceUploadError("invalid_request", 400);
  }

  const originalFilename = input.originalFilename.trim();
  const displayName = input.displayName.trim();
  const contentSha256 = input.contentSha256.toLowerCase();
  const format = input.format;

  if (
    input.projectId.length < 1 ||
    originalFilename.length < 1 ||
    originalFilename.length > 512 ||
    displayName.length < 1 ||
    displayName.length > 512 ||
    input.byteSize <= 0 ||
    input.byteSize > sourceMaxBytes() ||
    !SHA256_PATTERN.test(contentSha256) ||
    !originalFilename.toLowerCase().endsWith(expectedExtension(format))
  ) {
    throw new SagaSourceUploadError("invalid_request", 400);
  }

  return {
    projectId: input.projectId,
    originalFilename,
    displayName,
    format,
    byteSize: input.byteSize,
    contentSha256,
  };
}

function mapDatabaseMessage(message: string) {
  if (message.includes("saga_project_not_found")) {
    return new SagaSourceUploadError("not_found", 404);
  }
  if (
    message.includes("saga_invalid_source_format") ||
    message.includes("saga_invalid_source_metadata")
  ) {
    return new SagaSourceUploadError("invalid_request", 400);
  }
  return new SagaSourceUploadError("unavailable", 503);
}

function parseIntentRow(value: unknown): UploadIntentRow {
  const row = Array.isArray(value) ? value[0] : value;
  if (!row || typeof row !== "object") {
    throw new SagaSourceUploadError("unavailable", 503);
  }
  return row as UploadIntentRow;
}

function parseFinalizeRow(value: unknown): SagaSourceUploadCompletion {
  const row = (Array.isArray(value) ? value[0] : value) as FinalizeRow | undefined;
  if (
    !row ||
    typeof row.source_id !== "string" ||
    typeof row.source_status !== "string" ||
    (row.job_id !== null && typeof row.job_id !== "string") ||
    (row.result_failure_code !== null && typeof row.result_failure_code !== "string")
  ) {
    throw new SagaSourceUploadError("unavailable", 503);
  }

  return {
    sourceId: row.source_id,
    sourceStatus: row.source_status,
    jobId: row.job_id,
    failureCode: row.result_failure_code,
  };
}

export async function createSagaSourceUploadIntent(input: {
  projectId: unknown;
  originalFilename: unknown;
  displayName: unknown;
  format: unknown;
  byteSize: unknown;
  contentSha256: unknown;
}): Promise<SagaSourceUploadIntent> {
  const account = await requireCurrentSagaAccount();
  const values = validateUploadInput(input);

  if (!storageConfigurationStatus().configured) {
    throw new SagaSourceUploadError("storage_unavailable", 503);
  }

  const supabase = await createSupabaseServerClient();
  const { data, error } = await supabase.rpc("saga_create_source_upload_intent", {
    p_project_id: values.projectId,
    p_original_filename: values.originalFilename,
    p_display_name: values.displayName,
    p_source_format: values.format,
    p_byte_size: values.byteSize,
    p_content_sha256: values.contentSha256,
  });

  if (error) throw mapDatabaseMessage(error.message);

  const row = parseIntentRow(data);
  if (
    typeof row.source_id !== "string" ||
    typeof row.object_key !== "string" ||
    typeof row.media_type !== "string" ||
    !row.object_key.startsWith(`sources/${account.userId}/${values.projectId}/${row.source_id}/`)
  ) {
    throw new SagaSourceUploadError("unavailable", 503);
  }

  const metadata = {
    "saga-sha256": values.contentSha256,
    "saga-source-id": row.source_id,
  };
  const storage = createObjectStorage();
  const signed = await storage.createUploadUrl({
    key: row.object_key,
    contentType: row.media_type,
    metadata,
    expiresInSeconds: UPLOAD_URL_TTL_SECONDS,
  });

  return {
    sourceId: row.source_id,
    uploadUrl: signed.url,
    expiresInSeconds: signed.expiresInSeconds,
    contentType: row.media_type,
    requiredHeaders: {
      "content-type": row.media_type,
      "x-amz-meta-saga-sha256": values.contentSha256,
      "x-amz-meta-saga-source-id": row.source_id,
    },
  };
}

async function getOwnedSourceUploadRow(sourceId: string, ownerUserId: string) {
  const supabase = await createSupabaseServerClient();
  const { data, error } = await supabase
    .from("saga_sources")
    .select(
      "id,object_key,original_filename,media_type,byte_size,content_sha256,ingestion_status",
    )
    .eq("id", sourceId)
    .eq("owner_user_id", ownerUserId)
    .maybeSingle();

  if (error) throw new SagaSourceUploadError("unavailable", 503);
  if (!data) throw new SagaSourceUploadError("not_found", 404);

  const row = data as SourceUploadRow;
  if (
    typeof row.id !== "string" ||
    typeof row.object_key !== "string" ||
    typeof row.original_filename !== "string" ||
    typeof row.media_type !== "string" ||
    typeof row.byte_size !== "number" ||
    typeof row.content_sha256 !== "string" ||
    typeof row.ingestion_status !== "string"
  ) {
    throw new SagaSourceUploadError("unavailable", 503);
  }

  return row as {
    id: string;
    object_key: string;
    original_filename: string;
    media_type: string;
    byte_size: number;
    content_sha256: string;
    ingestion_status: string;
  };
}

export async function completeSagaSourceUpload(
  sourceId: string,
): Promise<SagaSourceUploadCompletion> {
  const account = await requireCurrentSagaAccount();
  if (!sourceId) throw new SagaSourceUploadError("invalid_request", 400);

  if (!storageConfigurationStatus().configured) {
    throw new SagaSourceUploadError("storage_unavailable", 503);
  }

  const source = await getOwnedSourceUploadRow(sourceId, account.userId);
  const storage = createObjectStorage();
  const observed = await storage.head(source.object_key);
  if (!observed) throw new SagaSourceUploadError("upload_incomplete", 409);

  const privileged = createSupabasePrivilegedClient();
  const { data, error } = await privileged.rpc("saga_service_finalize_source_upload", {
    p_source_id: source.id,
    p_owner_user_id: account.userId,
    p_observed_byte_size: observed.sizeBytes,
    p_observed_content_type: observed.contentType,
    p_observed_sha256_metadata: observed.metadata["saga-sha256"] ?? null,
    p_observed_source_id_metadata: observed.metadata["saga-source-id"] ?? null,
  });

  if (error) throw mapDatabaseMessage(error.message);
  const completion = parseFinalizeRow(data);

  if (completion.failureCode === "upload_metadata_mismatch") {
    try {
      await storage.delete(source.object_key);
    } catch {
      // The database failure state is authoritative. Object cleanup is best effort.
    }
    throw new SagaSourceUploadError("upload_mismatch", 409);
  }

  return completion;
}

export async function createSagaSourceReadUrl(sourceId: string) {
  const account = await requireCurrentSagaAccount();
  if (!sourceId) throw new SagaSourceUploadError("invalid_request", 400);

  if (!storageConfigurationStatus().configured) {
    throw new SagaSourceUploadError("storage_unavailable", 503);
  }

  const source = await getOwnedSourceUploadRow(sourceId, account.userId);
  if (source.ingestion_status === "pending_upload") {
    throw new SagaSourceUploadError("upload_incomplete", 409);
  }

  return createObjectStorage().createReadUrl({
    key: source.object_key,
    expiresInSeconds: READ_URL_TTL_SECONDS,
    downloadFilename: source.original_filename,
  });
}
