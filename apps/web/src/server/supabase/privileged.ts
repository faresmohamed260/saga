import { createClient } from "@supabase/supabase-js";

import { requireSupabasePrivilegedConfig } from "./config";

/**
 * Server-only privileged Supabase client.
 *
 * Never import this module from a Client Component or browser utility. The
 * privileged API credential bypasses RLS and exists only for narrowly scoped
 * S.A.G.A. server services such as product-access resolution and invitations.
 */
export function createSupabasePrivilegedClient() {
  const { url, privilegedKey } = requireSupabasePrivilegedConfig();

  return createClient(url, privilegedKey, {
    auth: {
      autoRefreshToken: false,
      detectSessionInUrl: false,
      persistSession: false,
    },
  });
}
