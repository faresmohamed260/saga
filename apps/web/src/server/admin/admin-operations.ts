import {
  isSagaAccountRole,
  isSagaAccountStatus,
  type SagaAccountRole,
  type SagaAccountStatus,
} from "@/server/account/types";
import { createSupabasePrivilegedClient } from "@/server/supabase/privileged";

import { requireCurrentSagaAdmin } from "./admin-auth";

export type SagaAdminInvitationStatus = "pending" | "accepted" | "revoked" | "expired";

export type SagaAdminInvitation = {
  id: string;
  emailNormalized: string;
  emailDisplay: string;
  intendedRole: SagaAccountRole;
  status: SagaAdminInvitationStatus;
  invitedBy: string | null;
  invitedAt: string;
  expiresAt: string;
  acceptedBy: string | null;
  acceptedAt: string | null;
  revokedAt: string | null;
};

export type SagaAdminAccount = {
  userId: string;
  email: string;
  role: SagaAccountRole;
  status: SagaAccountStatus;
  invitedBy: string | null;
  acceptedAt: string;
  updatedBy: string | null;
  updatedAt: string;
};

export type SagaAdminOperationErrorCode =
  | "invalid_request"
  | "not_found"
  | "conflict"
  | "forbidden"
  | "unavailable";

export class SagaAdminOperationError extends Error {
  readonly code: SagaAdminOperationErrorCode;
  readonly httpStatus: number;

  constructor(code: SagaAdminOperationErrorCode, httpStatus: number) {
    super(code);
    this.name = "SagaAdminOperationError";
    this.code = code;
    this.httpStatus = httpStatus;
  }
}

type InvitationRow = {
  id: unknown;
  email_normalized: unknown;
  email_display: unknown;
  intended_role: unknown;
  status: unknown;
  invited_by: unknown;
  invited_at: unknown;
  expires_at: unknown;
  accepted_by: unknown;
  accepted_at: unknown;
  revoked_at: unknown;
};

type AccountRow = {
  user_id: unknown;
  role: unknown;
  status: unknown;
  invited_by: unknown;
  accepted_at: unknown;
  updated_by: unknown;
  updated_at: unknown;
};

function isInvitationStatus(value: unknown): value is SagaAdminInvitationStatus {
  return value === "pending" || value === "accepted" || value === "revoked" || value === "expired";
}

function nullableString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function mapInvitation(row: InvitationRow): SagaAdminInvitation | null {
  if (
    typeof row.id !== "string" ||
    typeof row.email_normalized !== "string" ||
    typeof row.email_display !== "string" ||
    !isSagaAccountRole(row.intended_role) ||
    !isInvitationStatus(row.status) ||
    typeof row.invited_at !== "string" ||
    typeof row.expires_at !== "string"
  ) {
    return null;
  }

  return {
    id: row.id,
    emailNormalized: row.email_normalized,
    emailDisplay: row.email_display,
    intendedRole: row.intended_role,
    status: row.status,
    invitedBy: nullableString(row.invited_by),
    invitedAt: row.invited_at,
    expiresAt: row.expires_at,
    acceptedBy: nullableString(row.accepted_by),
    acceptedAt: nullableString(row.accepted_at),
    revokedAt: nullableString(row.revoked_at),
  };
}

function mapAccountRow(row: AccountRow, email: string): SagaAdminAccount | null {
  if (
    typeof row.user_id !== "string" ||
    !isSagaAccountRole(row.role) ||
    !isSagaAccountStatus(row.status) ||
    typeof row.accepted_at !== "string" ||
    typeof row.updated_at !== "string"
  ) {
    return null;
  }

  return {
    userId: row.user_id,
    email,
    role: row.role,
    status: row.status,
    invitedBy: nullableString(row.invited_by),
    acceptedAt: row.accepted_at,
    updatedBy: nullableString(row.updated_by),
    updatedAt: row.updated_at,
  };
}

function mapDatabaseError(message: string): SagaAdminOperationError {
  if (message.includes("saga_admin_required") || message.includes("saga_admin_self_lockout") || message.includes("saga_last_active_admin")) {
    return new SagaAdminOperationError("forbidden", 403);
  }

  if (
    message.includes("saga_account_already_admitted") ||
    message.includes("saga_pending_invitation_role_conflict")
  ) {
    return new SagaAdminOperationError("conflict", 409);
  }

  if (
    message.includes("saga_invalid_email") ||
    message.includes("saga_invalid_role") ||
    message.includes("saga_invalid_status") ||
    message.includes("saga_invalid_expiry")
  ) {
    return new SagaAdminOperationError("invalid_request", 400);
  }

  return new SagaAdminOperationError("unavailable", 503);
}

function requireEmail(value: unknown): string {
  if (typeof value !== "string") {
    throw new SagaAdminOperationError("invalid_request", 400);
  }

  const email = value.trim();
  if (email.length < 3 || email.length > 320 || !/^\S+@\S+\.\S+$/.test(email)) {
    throw new SagaAdminOperationError("invalid_request", 400);
  }
  return email;
}

export async function listSagaAdminInvitations(): Promise<SagaAdminInvitation[]> {
  await requireCurrentSagaAdmin();
  const privileged = createSupabasePrivilegedClient();
  const { data, error } = await privileged
    .from("saga_invitations")
    .select("id,email_normalized,email_display,intended_role,status,invited_by,invited_at,expires_at,accepted_by,accepted_at,revoked_at")
    .order("invited_at", { ascending: false });

  if (error) {
    throw new SagaAdminOperationError("unavailable", 503);
  }

  return (data ?? []).map((row) => mapInvitation(row as InvitationRow)).filter((row): row is SagaAdminInvitation => row !== null);
}

export async function listSagaAdminAccounts(): Promise<SagaAdminAccount[]> {
  await requireCurrentSagaAdmin();
  const privileged = createSupabasePrivilegedClient();
  const { data, error } = await privileged
    .from("saga_account_access")
    .select("user_id,role,status,invited_by,accepted_at,updated_by,updated_at")
    .order("created_at", { ascending: true });

  if (error) {
    throw new SagaAdminOperationError("unavailable", 503);
  }

  const rows = (data ?? []) as AccountRow[];
  const accounts = await Promise.all(
    rows.map(async (row) => {
      if (typeof row.user_id !== "string") return null;
      const { data: authData, error: authError } = await privileged.auth.admin.getUserById(row.user_id);
      const email = authData.user?.email;
      if (authError || typeof email !== "string") {
        throw new SagaAdminOperationError("unavailable", 503);
      }
      return mapAccountRow(row, email);
    }),
  );

  return accounts.filter((row): row is SagaAdminAccount => row !== null);
}

export async function createOrRetrySagaInvitation(input: {
  email: unknown;
  role: unknown;
}): Promise<{ invitation: SagaAdminInvitation; delivery: "sent" | "failed"; created: boolean }> {
  const admin = await requireCurrentSagaAdmin();
  const email = requireEmail(input.email);
  if (!isSagaAccountRole(input.role)) {
    throw new SagaAdminOperationError("invalid_request", 400);
  }

  const privileged = createSupabasePrivilegedClient();
  const expiresAt = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString();
  const { data, error } = await privileged.rpc("saga_admin_upsert_invitation_intent", {
    p_actor_user_id: admin.userId,
    p_email: email,
    p_intended_role: input.role,
    p_expires_at: expiresAt,
  });

  if (error) {
    throw mapDatabaseError(error.message);
  }

  const row = Array.isArray(data) ? data[0] : null;
  const invitation = row ? mapInvitation(row as InvitationRow) : null;
  if (!invitation) {
    throw new SagaAdminOperationError("unavailable", 503);
  }

  const created = Boolean((row as { created?: unknown }).created);
  const { error: deliveryError } = await privileged.auth.admin.inviteUserByEmail(invitation.emailDisplay);

  return {
    invitation,
    delivery: deliveryError ? "failed" : "sent",
    created,
  };
}

export async function revokeSagaInvitation(invitationId: string): Promise<SagaAdminInvitationStatus> {
  const admin = await requireCurrentSagaAdmin();
  if (!/^[0-9a-f-]{36}$/i.test(invitationId)) {
    throw new SagaAdminOperationError("invalid_request", 400);
  }

  const privileged = createSupabasePrivilegedClient();
  const { data, error } = await privileged.rpc("saga_admin_revoke_invitation", {
    p_actor_user_id: admin.userId,
    p_invitation_id: invitationId,
  });

  if (error) {
    throw mapDatabaseError(error.message);
  }

  const row = Array.isArray(data) ? data[0] : null;
  if (!row || !isInvitationStatus((row as { status?: unknown }).status)) {
    throw new SagaAdminOperationError("not_found", 404);
  }

  return (row as { status: SagaAdminInvitationStatus }).status;
}

export async function updateSagaAdminAccount(
  userId: string,
  input: { role: unknown; status: unknown },
): Promise<SagaAdminAccount> {
  const admin = await requireCurrentSagaAdmin();
  if (!/^[0-9a-f-]{36}$/i.test(userId) || !isSagaAccountRole(input.role) || !isSagaAccountStatus(input.status)) {
    throw new SagaAdminOperationError("invalid_request", 400);
  }

  const privileged = createSupabasePrivilegedClient();
  const { data, error } = await privileged.rpc("saga_admin_update_account", {
    p_actor_user_id: admin.userId,
    p_target_user_id: userId,
    p_role: input.role,
    p_status: input.status,
  });

  if (error) {
    throw mapDatabaseError(error.message);
  }

  const row = Array.isArray(data) ? data[0] : null;
  if (!row) {
    throw new SagaAdminOperationError("not_found", 404);
  }

  const { data: authData, error: authError } = await privileged.auth.admin.getUserById(userId);
  const email = authData.user?.email;
  if (authError || typeof email !== "string") {
    throw new SagaAdminOperationError("unavailable", 503);
  }

  const account = mapAccountRow(row as AccountRow, email);
  if (!account) {
    throw new SagaAdminOperationError("unavailable", 503);
  }
  return account;
}
