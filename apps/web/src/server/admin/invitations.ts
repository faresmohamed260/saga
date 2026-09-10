import type {
  SagaAccessRole,
  SagaInvitationCreateResponse,
  SagaInvitationSummary,
} from "@/lib/api/admin";
import { createSupabaseAdminClient } from "@/server/supabase/admin";

type InvitationRow = {
  id: string;
  normalized_email: string;
  role: SagaAccessRole;
  expires_at: string;
  created_at: string;
};

const INVITATION_LIFETIME_MS = 24 * 60 * 60 * 1000;
const PENDING_INVITATION_LIMIT = 100;

export class SagaAdminInvitationError extends Error {
  constructor(
    public readonly code:
      | "invalid_request"
      | "invitation_exists"
      | "invitation_not_found"
      | "admin_backend_unavailable",
    message: string,
  ) {
    super(message);
    this.name = "SagaAdminInvitationError";
  }
}

function publicInvitation(row: InvitationRow): SagaInvitationSummary {
  return {
    id: row.id,
    email: row.normalized_email,
    role: row.role,
    expiresAt: row.expires_at,
    createdAt: row.created_at,
  };
}

export function normalizeSagaInvitationEmail(value: string) {
  const email = value.trim().toLowerCase();
  if (email.length < 3 || email.length > 320 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    throw new SagaAdminInvitationError("invalid_request", "Enter a valid invitation email.");
  }
  return email;
}

export async function listPendingSagaInvitations(): Promise<SagaInvitationSummary[]> {
  const admin = createSupabaseAdminClient();
  if (!admin) throw new SagaAdminInvitationError("admin_backend_unavailable", "Invitations are temporarily unavailable.");

  const { data, error } = await admin
    .from("saga_invitations")
    .select("id,normalized_email,role,expires_at,created_at")
    .is("claimed_at", null)
    .is("revoked_at", null)
    .gt("expires_at", new Date().toISOString())
    .order("created_at", { ascending: false })
    .limit(PENDING_INVITATION_LIMIT);

  if (error) throw new SagaAdminInvitationError("admin_backend_unavailable", "Invitations are temporarily unavailable.");
  return (data ?? []).map((row) => publicInvitation(row as InvitationRow));
}

export async function createSagaInvitation({
  email,
  role,
  inviterUserId,
  redirectTo,
}: {
  email: string;
  role: SagaAccessRole;
  inviterUserId: string;
  redirectTo: string;
}): Promise<SagaInvitationCreateResponse> {
  const normalizedEmail = normalizeSagaInvitationEmail(email);
  if (role !== "member" && role !== "admin") {
    throw new SagaAdminInvitationError("invalid_request", "Choose a valid S.A.G.A. role.");
  }

  const admin = createSupabaseAdminClient();
  if (!admin) throw new SagaAdminInvitationError("admin_backend_unavailable", "Invitations are temporarily unavailable.");

  const { data: existingRows, error: existingError } = await admin
    .from("saga_invitations")
    .select("id,expires_at")
    .eq("normalized_email", normalizedEmail)
    .is("claimed_at", null)
    .is("revoked_at", null)
    .order("created_at", { ascending: false })
    .limit(1);

  if (existingError) throw new SagaAdminInvitationError("admin_backend_unavailable", "Invitations are temporarily unavailable.");
  const existing = existingRows?.[0] as { id: string; expires_at: string } | undefined;
  if (existing && Date.parse(existing.expires_at) > Date.now()) {
    throw new SagaAdminInvitationError("invitation_exists", "A pending invitation already exists for that email.");
  }
  if (existing) {
    const { error } = await admin
      .from("saga_invitations")
      .update({ revoked_at: new Date().toISOString() })
      .eq("id", existing.id)
      .is("claimed_at", null)
      .is("revoked_at", null);
    if (error) throw new SagaAdminInvitationError("admin_backend_unavailable", "Invitations are temporarily unavailable.");
  }

  const expiresAt = new Date(Date.now() + INVITATION_LIFETIME_MS).toISOString();
  const { data: inserted, error: insertError } = await admin
    .from("saga_invitations")
    .insert({
      normalized_email: normalizedEmail,
      role,
      invited_by: inviterUserId,
      expires_at: expiresAt,
    })
    .select("id,normalized_email,role,expires_at,created_at")
    .single();

  if (insertError || !inserted) {
    if (insertError?.code === "23505") {
      throw new SagaAdminInvitationError("invitation_exists", "A pending invitation already exists for that email.");
    }
    throw new SagaAdminInvitationError("admin_backend_unavailable", "The invitation could not be recorded right now.");
  }

  const { error: deliveryError } = await admin.auth.admin.inviteUserByEmail(normalizedEmail, { redirectTo });
  return {
    invitation: publicInvitation(inserted as InvitationRow),
    deliveryStatus: deliveryError ? "not_confirmed" : "requested",
    message: deliveryError
      ? "Invitation recorded. Email delivery could not be confirmed."
      : "Invitation recorded. Email delivery was requested.",
  };
}

export async function revokeSagaInvitation(invitationId: string) {
  const admin = createSupabaseAdminClient();
  if (!admin) throw new SagaAdminInvitationError("admin_backend_unavailable", "Invitations are temporarily unavailable.");

  const { data, error } = await admin
    .from("saga_invitations")
    .update({ revoked_at: new Date().toISOString() })
    .eq("id", invitationId)
    .is("claimed_at", null)
    .is("revoked_at", null)
    .select("id")
    .maybeSingle();

  if (error) throw new SagaAdminInvitationError("admin_backend_unavailable", "The invitation could not be revoked right now.");
  if (!data) throw new SagaAdminInvitationError("invitation_not_found", "That pending invitation is no longer available.");
}
