"use server";

import { revalidatePath } from "next/cache";

import {
  completeSagaSourceUpload,
  createSagaSourceUploadIntent,
  SagaSourceUploadError,
} from "@/server/story/source-upload";

export type SourceUploadActionError =
  | "invalid_request"
  | "not_found"
  | "storage_unavailable"
  | "upload_incomplete"
  | "upload_mismatch"
  | "unavailable";

type ActionFailure = {
  ok: false;
  error: SourceUploadActionError;
};

export type StartSourceUploadActionResult =
  | {
      ok: true;
      sourceId: string;
      uploadUrl: string;
      expiresInSeconds: number;
      contentType: string;
      requiredHeaders: Record<string, string>;
    }
  | ActionFailure;

export type CompleteSourceUploadActionResult =
  | {
      ok: true;
      sourceId: string;
      jobId: string | null;
      sourceStatus: string;
    }
  | ActionFailure;

function actionError(error: unknown): ActionFailure {
  if (error instanceof SagaSourceUploadError) {
    return { ok: false, error: error.code };
  }
  return { ok: false, error: "unavailable" };
}

export async function startSourceUploadAction(input: {
  projectId: string;
  originalFilename: string;
  displayName: string;
  format: "txt" | "epub";
  byteSize: number;
  contentSha256: string;
}): Promise<StartSourceUploadActionResult> {
  try {
    const intent = await createSagaSourceUploadIntent(input);
    return { ok: true, ...intent };
  } catch (error) {
    return actionError(error);
  }
}

export async function completeSourceUploadAction(
  projectId: string,
  sourceId: string,
): Promise<CompleteSourceUploadActionResult> {
  try {
    const completion = await completeSagaSourceUpload(sourceId);
    revalidatePath("/library");
    revalidatePath("/projects");
    revalidatePath(`/projects/${projectId}`);
    return {
      ok: true,
      sourceId: completion.sourceId,
      jobId: completion.jobId,
      sourceStatus: completion.sourceStatus,
    };
  } catch (error) {
    return actionError(error);
  }
}
