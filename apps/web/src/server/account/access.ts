import type { SagaAccessRole } from "@/lib/api/admin";
import { createSupabaseAdminClient } from "@/server/supabase/admin";

export type SagaAccessStatus = "active" | "suspended";

export type SagaAccountAccess = {
  userId: string;
  role: SagaAccessRole;
  status: SagaAccessStatus;
  createdAt: string;
  updatedAt: string;
};

export type SagaIdentity = {
  id: string;
  email: string | null;
};

type SagaAccountAccessRow = {
  user_id: string;
  role: SagaAccessRole;
  status: SagaAccessStatus;
  created_at: string;
  updated_at: string;
};

export class SagaAccessUnavailableError extends Error {
  constructor() {
    super("S.A.G.A. account access is unavailable.");
    this.name = "SagaAccessUnavailableError";
  }
}

function publicAccess(row: SagaAccountAccessRow): SagaAccountAccess {
  return {
    userId: row.user_id,
    role: row.role,
    status: row.status,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  };
}

export async function getSagaAccountAccess(userId: string): Promise<SagaAccountAccess | null> {
  const admin = createSupabaseAdminClient();
  if (!admin) throw new SagaAccessUnavailableError();

  const { data, error } = await admin
    .from("saga_account_access")
    .select("user_id,role,status,created_at,updated_at")
    .eq("user_id", userId)
    .maybeSingle();

  if (error) throw new SagaAccessUnavailableError();
  return data ? publicAccess(data as SagaAccountAccessRow) : null;
}

export async function claimSagaInvitation(identity: SagaIdentity): Promise<SagaAccountAccess | null> {
  const email = identity.email?.trim().toLowerCase();
  if (!email) return null;

  const admin = createSupabaseAdminClient();
  if (!admin) throw new SagaAccessUnavailableError();

  const { data, error } = await admin.rpc("saga_claim_invitation", {
    p_user_id: identity.id,
    p_email: email,
  });

  if (error) throw new SagaAccessUnavailableError();
  const row = Array.isArray(data) ? data[0] : data;
  return row ? publicAccess(row as SagaAccountAccessRow) : null;
}

export async function resolveSagaAccountAccess(identity: SagaIdentity) {
  const existing = await getSagaAccountAccess(identity.id);
  return existing ?? claimSagaInvitation(identity);
}
