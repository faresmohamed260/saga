"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import {
  createOrRetrySagaInvitation,
  revokeSagaInvitation,
  SagaAdminOperationError,
  updateSagaAdminAccount,
} from "@/server/admin/admin-operations";
import { SagaAccessError } from "@/server/account/account-access";

function boundedNotice(error: unknown): string {
  if (error instanceof SagaAdminOperationError || error instanceof SagaAccessError) {
    return error.code;
  }
  return "unavailable";
}

export async function createInvitationAction(formData: FormData) {
  let notice = "invitation_saved";
  try {
    const result = await createOrRetrySagaInvitation({
      email: formData.get("email"),
      role: formData.get("role"),
    });
    notice = result.delivery === "sent" ? "invitation_sent" : "delivery_failed";
    revalidatePath("/admin");
  } catch (error) {
    notice = boundedNotice(error);
  }
  redirect(`/admin?notice=${encodeURIComponent(notice)}`);
}

export async function revokeInvitationAction(formData: FormData) {
  let notice = "invitation_revoked";
  try {
    const invitationId = formData.get("invitationId");
    if (typeof invitationId !== "string") throw new SagaAdminOperationError("invalid_request", 400);
    const status = await revokeSagaInvitation(invitationId);
    notice = status === "revoked" ? "invitation_revoked" : `invitation_${status}`;
    revalidatePath("/admin");
  } catch (error) {
    notice = boundedNotice(error);
  }
  redirect(`/admin?notice=${encodeURIComponent(notice)}`);
}

export async function updateAccountAction(formData: FormData) {
  let notice = "account_updated";
  try {
    const userId = formData.get("userId");
    if (typeof userId !== "string") throw new SagaAdminOperationError("invalid_request", 400);
    await updateSagaAdminAccount(userId, {
      role: formData.get("role"),
      status: formData.get("status"),
    });
    revalidatePath("/admin");
  } catch (error) {
    notice = boundedNotice(error);
  }
  redirect(`/admin?notice=${encodeURIComponent(notice)}`);
}
