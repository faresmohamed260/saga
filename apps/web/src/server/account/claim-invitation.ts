import { createSupabasePrivilegedClient } from "@/server/supabase/privileged";

import { SagaAccessError } from "./account-access";
import { getFreshSagaIdentity } from "./identity";
import {
  isSagaAccountRole,
  isSagaAccountStatus,
  type SagaAccount,
} from "./types";

type ClaimRow = {
  user_id: string;
  role: unknown;
  status: unknown;
  invited_by: string | null;
  accepted_at: string;
};

/**
 * Claims an eligible S.A.G.A. invitation for the currently verified Auth user.
 * The database routine independently reloads auth.users.email and performs the
 * invitation-email match while holding the invitation row lock.
 */
export async function claimCurrentSagaInvitation(): Promise<SagaAccount | null> {
  const identity = await getFreshSagaIdentity();
  if (!identity) {
    throw new SagaAccessError("unauthenticated", 401);
  }

  const privileged = createSupabasePrivilegedClient();
  const { data, error } = await privileged.rpc("saga_claim_invitation", {
    p_user_id: identity.userId,
  });

  if (error) {
    throw new SagaAccessError("access_unavailable", 503);
  }

  const row = Array.isArray(data) ? (data[0] as ClaimRow | undefined) : undefined;
  if (!row) {
    return null;
  }

  if (
    row.user_id !== identity.userId ||
    !isSagaAccountRole(row.role) ||
    !isSagaAccountStatus(row.status) ||
    typeof row.accepted_at !== "string"
  ) {
    throw new SagaAccessError("access_unavailable", 503);
  }

  return {
    ...identity,
    role: row.role,
    status: row.status,
    invitedBy: typeof row.invited_by === "string" ? row.invited_by : null,
    acceptedAt: row.accepted_at,
  };
}
