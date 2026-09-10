import { createClient } from "@supabase/supabase-js";

import { getSupabaseAdminConfig } from "./config";

export function createSupabaseAdminClient() {
  const config = getSupabaseAdminConfig();
  if (!config) return null;

  return createClient(config.url, config.serviceRoleKey, {
    auth: {
      autoRefreshToken: false,
      persistSession: false,
      detectSessionInUrl: false,
    },
  });
}
