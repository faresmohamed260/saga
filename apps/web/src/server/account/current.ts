import type { User } from "@supabase/supabase-js";

import type { SagaAccountAccess, SagaIdentity } from "./access";
import { resolveSagaAccountAccess } from "./access";
import { createSupabaseServerClient } from "@/server/supabase/server";

export type SagaAccountState =
  | { status: "unconfigured" }
  | { status: "signed_out" }
  | { status: "unavailable"; identity: SagaIdentity }
  | { status: "invitation_required"; identity: SagaIdentity }
  | { status: "suspended"; identity: SagaIdentity; access: SagaAccountAccess }
  | { status: "active"; identity: SagaIdentity; access: SagaAccountAccess };

function verifiedIdentity(user: User | null): SagaIdentity | null {
  if (!user || user.is_anonymous === true || typeof user.id !== "string") return null;
  return {
    id: user.id,
    email: typeof user.email === "string" ? user.email : null,
  };
}

export async function getCurrentSagaIdentity(): Promise<SagaIdentity | null> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return null;

  const { data, error } = await supabase.auth.getUser();
  if (error) return null;
  return verifiedIdentity(data.user);
}

export async function getCurrentSagaAccountState(): Promise<SagaAccountState> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return { status: "unconfigured" };

  const { data, error } = await supabase.auth.getUser();
  const identity = error ? null : verifiedIdentity(data.user);
  if (!identity) return { status: "signed_out" };

  try {
    const access = await resolveSagaAccountAccess(identity);
    if (!access) return { status: "invitation_required", identity };
    if (access.status !== "active") return { status: "suspended", identity, access };
    return { status: "active", identity, access };
  } catch {
    return { status: "unavailable", identity };
  }
}

export function isActiveSagaAdmin(state: SagaAccountState) {
  return state.status === "active" && state.access.role === "admin";
}
