import { createSupabasePrivilegedClient } from "@/server/supabase/privileged";

import { getFreshSagaIdentity } from "./identity";
import {
  isSagaAccountRole,
  isSagaAccountStatus,
  type SagaAccount,
  type SagaIdentity,
} from "./types";

type SagaAccountAccessRow = {
  user_id: string;
  role: unknown;
  status: unknown;
  invited_by: string | null;
  accepted_at: string;
};

export type SagaAccountResolution =
  | { state: "unauthenticated" }
  | { state: "not_admitted"; identity: SagaIdentity }
  | { state: "suspended"; account: SagaAccount }
  | { state: "active"; account: SagaAccount }
  | { state: "unavailable" };

export type SagaAccessErrorCode =
  | "unauthenticated"
  | "not_admitted"
  | "suspended"
  | "access_unavailable"
  | "admin_required";

export class SagaAccessError extends Error {
  readonly code: SagaAccessErrorCode;
  readonly httpStatus: number;

  constructor(code: SagaAccessErrorCode, httpStatus: number) {
    super(code);
    this.name = "SagaAccessError";
    this.code = code;
    this.httpStatus = httpStatus;
  }
}

function mapAccountRow(
  identity: SagaIdentity,
  row: SagaAccountAccessRow,
): SagaAccount | null {
  if (
    row.user_id !== identity.userId ||
    !isSagaAccountRole(row.role) ||
    !isSagaAccountStatus(row.status) ||
    typeof row.accepted_at !== "string"
  ) {
    return null;
  }

  return {
    ...identity,
    role: row.role,
    status: row.status,
    invitedBy: typeof row.invited_by === "string" ? row.invited_by : null,
    acceptedAt: row.accepted_at,
  };
}

export async function resolveCurrentSagaAccount(): Promise<SagaAccountResolution> {
  let identity: SagaIdentity | null;

  try {
    identity = await getFreshSagaIdentity();
  } catch {
    return { state: "unavailable" };
  }

  if (!identity) {
    return { state: "unauthenticated" };
  }

  try {
    const privileged = createSupabasePrivilegedClient();
    const { data, error } = await privileged
      .from("saga_account_access")
      .select("user_id,role,status,invited_by,accepted_at")
      .eq("user_id", identity.userId)
      .maybeSingle();

    if (error) {
      return { state: "unavailable" };
    }

    if (!data) {
      return { state: "not_admitted", identity };
    }

    const account = mapAccountRow(identity, data as SagaAccountAccessRow);
    if (!account) {
      return { state: "unavailable" };
    }

    if (account.status === "suspended") {
      return { state: "suspended", account };
    }

    return { state: "active", account };
  } catch {
    return { state: "unavailable" };
  }
}

export async function requireCurrentSagaAccount(): Promise<SagaAccount> {
  const resolution = await resolveCurrentSagaAccount();

  switch (resolution.state) {
    case "active":
      return resolution.account;
    case "unauthenticated":
      throw new SagaAccessError("unauthenticated", 401);
    case "not_admitted":
      throw new SagaAccessError("not_admitted", 403);
    case "suspended":
      throw new SagaAccessError("suspended", 403);
    case "unavailable":
      throw new SagaAccessError("access_unavailable", 503);
  }
}
