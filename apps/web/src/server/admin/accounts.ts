import type {
  SagaAccessRole,
  SagaAccessStatus,
  SagaAdminAccountSummary,
  SagaAdminAccountUpdate,
} from "@/lib/api/admin";
import { createSupabaseAdminClient } from "@/server/supabase/admin";

const ACCOUNT_LIST_LIMIT = 100;

type AccountRow = {
  user_id: string;
  role: SagaAccessRole;
  status: SagaAccessStatus;
  created_at: string;
  updated_at: string;
};

export class SagaAdminAccountError extends Error {
  constructor(
    public readonly code:
      | "invalid_request"
      | "account_not_found"
      | "admin_required"
      | "self_lockout"
      | "last_active_admin"
      | "admin_backend_unavailable",
    message: string,
  ) {
    super(message);
    this.name = "SagaAdminAccountError";
  }
}

function publicAccount(row: AccountRow, email: string | null): SagaAdminAccountSummary {
  return {
    userId: row.user_id,
    email,
    role: row.role,
    status: row.status,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  };
}

export async function listSagaAdminAccounts(): Promise<SagaAdminAccountSummary[]> {
  const admin = createSupabaseAdminClient();
  if (!admin) throw new SagaAdminAccountError("admin_backend_unavailable", "Accounts are temporarily unavailable.");

  const { data, error } = await admin
    .from("saga_account_access")
    .select("user_id,role,status,created_at,updated_at")
    .order("created_at", { ascending: true })
    .limit(ACCOUNT_LIST_LIMIT);

  if (error) throw new SagaAdminAccountError("admin_backend_unavailable", "Accounts are temporarily unavailable.");

  return Promise.all((data ?? []).map(async (record) => {
    const row = record as AccountRow;
    const { data: userData, error: userError } = await admin.auth.admin.getUserById(row.user_id);
    const email = !userError && typeof userData.user?.email === "string" ? userData.user.email : null;
    return publicAccount(row, email);
  }));
}

function classifyAccountMutationError(error: { message?: string } | null) {
  const message = error?.message ?? "";
  if (message.includes("saga_admin_self_lockout")) {
    return new SagaAdminAccountError("self_lockout", "You cannot remove your own active admin access.");
  }
  if (message.includes("saga_admin_last_active_admin")) {
    return new SagaAdminAccountError("last_active_admin", "The last active S.A.G.A. admin cannot be demoted or suspended.");
  }
  if (message.includes("saga_admin_account_not_found")) {
    return new SagaAdminAccountError("account_not_found", "That S.A.G.A. account is no longer available.");
  }
  if (message.includes("saga_admin_required")) {
    return new SagaAdminAccountError("admin_required", "Active S.A.G.A. admin access is required.");
  }
  if (message.includes("saga_admin_invalid_request")) {
    return new SagaAdminAccountError("invalid_request", "The requested account values are invalid.");
  }
  return new SagaAdminAccountError("admin_backend_unavailable", "The account could not be updated right now.");
}

export async function updateSagaAdminAccount(
  actorUserId: string,
  targetUserId: string,
  update: SagaAdminAccountUpdate,
): Promise<SagaAdminAccountSummary> {
  if (
    (update.role !== undefined && update.role !== "member" && update.role !== "admin")
    || (update.status !== undefined && update.status !== "active" && update.status !== "suspended")
    || (update.role === undefined && update.status === undefined)
  ) {
    throw new SagaAdminAccountError("invalid_request", "The requested account values are invalid.");
  }

  const admin = createSupabaseAdminClient();
  if (!admin) throw new SagaAdminAccountError("admin_backend_unavailable", "Accounts are temporarily unavailable.");

  const { data, error } = await admin.rpc("saga_admin_set_account_access", {
    p_actor_user_id: actorUserId,
    p_target_user_id: targetUserId,
    p_role: update.role ?? null,
    p_status: update.status ?? null,
  });

  if (error) throw classifyAccountMutationError(error);
  const row = (Array.isArray(data) ? data[0] : data) as AccountRow | undefined;
  if (!row) throw new SagaAdminAccountError("admin_backend_unavailable", "The account could not be updated right now.");

  const { data: userData, error: userError } = await admin.auth.admin.getUserById(row.user_id);
  const email = !userError && typeof userData.user?.email === "string" ? userData.user.email : null;
  return publicAccount(row, email);
}
