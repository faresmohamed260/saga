import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

import { requireSupabaseServerConfig } from "./config";

export async function createSupabaseServerClient() {
  const cookieStore = await cookies();
  const { url, publishableKey } = requireSupabaseServerConfig();

  return createServerClient(url, publishableKey, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        try {
          for (const { name, value, options } of cookiesToSet) {
            cookieStore.set(name, value, options);
          }
        } catch {
          // Server Components cannot always write cookies. Middleware/server actions
          // will own refresh writes once authentication is enabled in Phase 1.
        }
      },
    },
  });
}
