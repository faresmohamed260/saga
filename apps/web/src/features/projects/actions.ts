"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { SagaAccessError } from "@/server/account/account-access";
import {
  createSagaProject,
  SagaStoryOperationError,
} from "@/server/story/story-data";

function boundedNotice(error: unknown): string {
  if (error instanceof SagaStoryOperationError || error instanceof SagaAccessError) {
    return error.code;
  }
  return "unavailable";
}

export async function createProjectAction(formData: FormData) {
  let destination = "/projects?notice=unavailable";

  try {
    const project = await createSagaProject({
      title: formData.get("title"),
      description: formData.get("description"),
    });

    revalidatePath("/projects");
    revalidatePath("/home");
    destination = `/projects/${encodeURIComponent(project.id)}?notice=project_created`;
  } catch (error) {
    destination = `/projects?notice=${encodeURIComponent(boundedNotice(error))}`;
  }

  redirect(destination);
}
