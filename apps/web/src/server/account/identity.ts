import { createSupabaseServerClient } from "@/server/supabase/server";

import { normalizeSagaEmail } from "./email";
import type { SagaIdentity } from "./types";

/**
 * Re-confirms the current Supabase session against the Auth server.
 *
 * Cookie/JWT parsing may be used elsewhere for SSR plumbing, but this fresh
 * Auth lookup is the identity boundary used before private S.A.G.A. access
 * decisions.
 */
export async function getFreshSagaIdentity(): Promise<SagaIdentity | null> {
  const supabase = await createSupabaseServerClient();
  const {
    data: { user },
    error,
  } = await supabase.auth.getUser();

  if (error || !user || user.is_anonymous || !user.email) {
    return null;
  }

  const email = user.email.trim();
  if (!email) {
    return null;
  }

  return {
    userId: user.id,
    email,
    emailNormalized: normalizeSagaEmail(email),
  };
}
