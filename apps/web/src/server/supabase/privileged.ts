import { createClient } from "@supabase/supabase-js";

import { requireSupabasePrivilegedConfig } from "./config";

/**
 * Server-only privileged Supabase client.
 *
 * Never import this module from a Client Component or browser utility. The
 * service-role credential bypasses RLS and exists only for narrowly scoped
 * S.A.G.A. server services such as product-access resolution and invitations.
 */
export function createSupabasePrivilegedClient() {
  const { url, serviceRoleKey } = requireSupabasePrivilegedConfig();

  return createClient(url, serviceRoleKey, {
    auth: {
      autoRefreshToken: false,
      detectSessionInUrl: false,
      persistSession: false,
    },
  });
}
