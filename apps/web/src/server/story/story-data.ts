import { requireCurrentSagaAccount } from "@/server/account/account-access";
import { createSupabaseServerClient } from "@/server/supabase/server";

export type SagaProjectStatus = "active" | "archived";
export type SagaSourceFormat = "txt" | "epub";
export type SagaSourceIngestionStatus =
  | "pending_upload"
  | "uploaded"
  | "processing"
  | "ready"
  | "failed";
export type SagaAnalysisJobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";
export type SagaAnalysisJobKind = "source_ingestion" | "character_identity";

export type SagaProject = {
  id: string;
  title: string;
  description: string | null;
  status: SagaProjectStatus;
  createdAt: string;
  updatedAt: string;
};

export type SagaSource = {
  id: string;
  projectId: string;
  projectTitle: string | null;
  displayName: string;
  originalFilename: string;
  format: SagaSourceFormat;
  byteSize: number;
  contentSha256: string;
  ingestionStatus: SagaSourceIngestionStatus;
  failureCode: string | null;
  createdAt: string;
};

export type SagaAnalysisJob = {
  id: string;
  sourceId: string;
  kind: SagaAnalysisJobKind;
  status: SagaAnalysisJobStatus;
  attemptCount: number;
  maxAttempts: number;
  errorCode: string | null;
  errorSummary: string | null;
  createdAt: string;
  startedAt: string | null;
  completedAt: string | null;
};

export type SagaProjectWorkspace = {
  project: SagaProject;
  sources: SagaSource[];
  jobs: SagaAnalysisJob[];
  characterCount: number;
};

export type SagaStoryOperationErrorCode = "invalid_request" | "not_found" | "unavailable";

export class SagaStoryOperationError extends Error {
  readonly code: SagaStoryOperationErrorCode;
  readonly httpStatus: number;

  constructor(code: SagaStoryOperationErrorCode, httpStatus: number) {
    super(code);
    this.name = "SagaStoryOperationError";
    this.code = code;
    this.httpStatus = httpStatus;
  }
}

type ProjectRow = {
  id: unknown;
  title: unknown;
  description: unknown;
  status: unknown;
  created_at: unknown;
  updated_at: unknown;
};

type SourceRow = {
  id: unknown;
  project_id: unknown;
  original_filename: unknown;
  display_name: unknown;
  source_format: unknown;
  byte_size: unknown;
  content_sha256: unknown;
  ingestion_status: unknown;
  failure_code: unknown;
  created_at: unknown;
};

type JobRow = {
  id: unknown;
  source_id: unknown;
  kind: unknown;
  status: unknown;
  attempt_count: unknown;
  max_attempts: unknown;
  error_code: unknown;
  error_summary: unknown;
  created_at: unknown;
  started_at: unknown;
  completed_at: unknown;
};

function nullableString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function isProjectStatus(value: unknown): value is SagaProjectStatus {
  return value === "active" || value === "archived";
}

function isSourceFormat(value: unknown): value is SagaSourceFormat {
  return value === "txt" || value === "epub";
}

function isSourceIngestionStatus(value: unknown): value is SagaSourceIngestionStatus {
  return (
    value === "pending_upload" ||
    value === "uploaded" ||
    value === "processing" ||
    value === "ready" ||
    value === "failed"
  );
}

function isJobKind(value: unknown): value is SagaAnalysisJobKind {
  return value === "source_ingestion" || value === "character_identity";
}

function isJobStatus(value: unknown): value is SagaAnalysisJobStatus {
  return (
    value === "queued" ||
    value === "running" ||
    value === "succeeded" ||
    value === "failed" ||
    value === "cancelled"
  );
}

function mapProject(row: ProjectRow): SagaProject | null {
  if (
    typeof row.id !== "string" ||
    typeof row.title !== "string" ||
    !isProjectStatus(row.status) ||
    typeof row.created_at !== "string" ||
    typeof row.updated_at !== "string"
  ) {
    return null;
  }

  return {
    id: row.id,
    title: row.title,
    description: nullableString(row.description),
    status: row.status,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  };
}

function mapSource(row: SourceRow, projectTitle: string | null = null): SagaSource | null {
  if (
    typeof row.id !== "string" ||
    typeof row.project_id !== "string" ||
    typeof row.original_filename !== "string" ||
    typeof row.display_name !== "string" ||
    !isSourceFormat(row.source_format) ||
    typeof row.byte_size !== "number" ||
    typeof row.content_sha256 !== "string" ||
    !isSourceIngestionStatus(row.ingestion_status) ||
    typeof row.created_at !== "string"
  ) {
    return null;
  }

  return {
    id: row.id,
    projectId: row.project_id,
    projectTitle,
    displayName: row.display_name,
    originalFilename: row.original_filename,
    format: row.source_format,
    byteSize: row.byte_size,
    contentSha256: row.content_sha256,
    ingestionStatus: row.ingestion_status,
    failureCode: nullableString(row.failure_code),
    createdAt: row.created_at,
  };
}

function mapJob(row: JobRow): SagaAnalysisJob | null {
  if (
    typeof row.id !== "string" ||
    typeof row.source_id !== "string" ||
    !isJobKind(row.kind) ||
    !isJobStatus(row.status) ||
    typeof row.attempt_count !== "number" ||
    typeof row.max_attempts !== "number" ||
    typeof row.created_at !== "string"
  ) {
    return null;
  }

  return {
    id: row.id,
    sourceId: row.source_id,
    kind: row.kind,
    status: row.status,
    attemptCount: row.attempt_count,
    maxAttempts: row.max_attempts,
    errorCode: nullableString(row.error_code),
    errorSummary: nullableString(row.error_summary),
    createdAt: row.created_at,
    startedAt: nullableString(row.started_at),
    completedAt: nullableString(row.completed_at),
  };
}

function validateProjectInput(input: { title: unknown; description?: unknown }) {
  if (typeof input.title !== "string") {
    throw new SagaStoryOperationError("invalid_request", 400);
  }

  const title = input.title.trim();
  if (title.length < 1 || title.length > 160) {
    throw new SagaStoryOperationError("invalid_request", 400);
  }

  let description: string | null = null;
  if (typeof input.description === "string" && input.description.trim().length > 0) {
    description = input.description.trim();
    if (description.length > 4000) {
      throw new SagaStoryOperationError("invalid_request", 400);
    }
  } else if (input.description !== undefined && input.description !== null && typeof input.description !== "string") {
    throw new SagaStoryOperationError("invalid_request", 400);
  }

  return { title, description };
}

export async function listSagaProjects(): Promise<SagaProject[]> {
  const account = await requireCurrentSagaAccount();
  const supabase = await createSupabaseServerClient();
  const { data, error } = await supabase
    .from("saga_projects")
    .select("id,title,description,status,created_at,updated_at")
    .eq("owner_user_id", account.userId)
    .order("updated_at", { ascending: false });

  if (error || !data) {
    throw new SagaStoryOperationError("unavailable", 503);
  }

  const projects = data.map((row) => mapProject(row as ProjectRow));
  if (projects.some((project) => project === null)) {
    throw new SagaStoryOperationError("unavailable", 503);
  }

  return projects as SagaProject[];
}

export async function createSagaProject(input: {
  title: unknown;
  description?: unknown;
}): Promise<SagaProject> {
  const account = await requireCurrentSagaAccount();
  const values = validateProjectInput(input);
  const supabase = await createSupabaseServerClient();
  const { data, error } = await supabase
    .from("saga_projects")
    .insert({
      owner_user_id: account.userId,
      title: values.title,
      description: values.description,
    })
    .select("id,title,description,status,created_at,updated_at")
    .single();

  if (error || !data) {
    throw new SagaStoryOperationError("unavailable", 503);
  }

  const project = mapProject(data as ProjectRow);
  if (!project) {
    throw new SagaStoryOperationError("unavailable", 503);
  }

  return project;
}

export async function listSagaSources(): Promise<SagaSource[]> {
  const account = await requireCurrentSagaAccount();
  const supabase = await createSupabaseServerClient();
  const [{ data: sourceData, error: sourceError }, { data: projectData, error: projectError }] =
    await Promise.all([
      supabase
        .from("saga_sources")
        .select(
          "id,project_id,original_filename,display_name,source_format,byte_size,content_sha256,ingestion_status,failure_code,created_at",
        )
        .eq("owner_user_id", account.userId)
        .order("created_at", { ascending: false }),
      supabase
        .from("saga_projects")
        .select("id,title,description,status,created_at,updated_at")
        .eq("owner_user_id", account.userId),
    ]);

  if (sourceError || projectError || !sourceData || !projectData) {
    throw new SagaStoryOperationError("unavailable", 503);
  }

  const projectTitles = new Map<string, string>();
  for (const rawProject of projectData) {
    const project = mapProject(rawProject as ProjectRow);
    if (!project) throw new SagaStoryOperationError("unavailable", 503);
    projectTitles.set(project.id, project.title);
  }

  const sources = sourceData.map((row) => {
    const sourceRow = row as SourceRow;
    const projectTitle =
      typeof sourceRow.project_id === "string"
        ? (projectTitles.get(sourceRow.project_id) ?? null)
        : null;
    return mapSource(sourceRow, projectTitle);
  });

  if (sources.some((source) => source === null)) {
    throw new SagaStoryOperationError("unavailable", 503);
  }

  return sources as SagaSource[];
}

export async function getSagaProjectWorkspace(projectId: string): Promise<SagaProjectWorkspace | null> {
  const account = await requireCurrentSagaAccount();
  if (!projectId) return null;

  const supabase = await createSupabaseServerClient();
  const { data: projectData, error: projectError } = await supabase
    .from("saga_projects")
    .select("id,title,description,status,created_at,updated_at")
    .eq("id", projectId)
    .eq("owner_user_id", account.userId)
    .maybeSingle();

  if (projectError) throw new SagaStoryOperationError("unavailable", 503);
  if (!projectData) return null;

  const project = mapProject(projectData as ProjectRow);
  if (!project) throw new SagaStoryOperationError("unavailable", 503);

  const [sourcesResult, jobsResult, charactersResult] = await Promise.all([
    supabase
      .from("saga_sources")
      .select(
        "id,project_id,original_filename,display_name,source_format,byte_size,content_sha256,ingestion_status,failure_code,created_at",
      )
      .eq("project_id", projectId)
      .eq("owner_user_id", account.userId)
      .order("created_at", { ascending: false }),
    supabase
      .from("saga_analysis_jobs")
      .select(
        "id,source_id,kind,status,attempt_count,max_attempts,error_code,error_summary,created_at,started_at,completed_at",
      )
      .eq("project_id", projectId)
      .eq("owner_user_id", account.userId)
      .order("created_at", { ascending: false }),
    supabase
      .from("saga_characters")
      .select("id", { count: "exact", head: true })
      .eq("project_id", projectId)
      .eq("owner_user_id", account.userId),
  ]);

  if (sourcesResult.error || jobsResult.error || charactersResult.error) {
    throw new SagaStoryOperationError("unavailable", 503);
  }

  const sources = (sourcesResult.data ?? []).map((row) =>
    mapSource(row as SourceRow, project.title),
  );
  const jobs = (jobsResult.data ?? []).map((row) => mapJob(row as JobRow));

  if (sources.some((source) => source === null) || jobs.some((job) => job === null)) {
    throw new SagaStoryOperationError("unavailable", 503);
  }

  return {
    project,
    sources: sources as SagaSource[],
    jobs: jobs as SagaAnalysisJob[],
    characterCount: charactersResult.count ?? 0,
  };
}
