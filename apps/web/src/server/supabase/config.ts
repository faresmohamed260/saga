export type IntegrationStatus = {
  configured: boolean;
  provider: string;
};

export type SupabasePublicConfig = {
  url: string;
  publishableKey: string;
};

export type SupabaseAdminConfig = SupabasePublicConfig & {
  serviceRoleKey: string;
};

export function getSupabasePublicConfig(): SupabasePublicConfig | null {
  const url = (process.env.NEXT_PUBLIC_SUPABASE_URL ?? process.env.SUPABASE_URL)?.trim();
  const publishableKey = (
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
    ?? process.env.SUPABASE_PUBLISHABLE_KEY
  )?.trim();

  if (!url || !publishableKey) return null;
  return { url: url.replace(/\/$/, ""), publishableKey };
}

export function getSupabaseAdminConfig(): SupabaseAdminConfig | null {
  const publicConfig = getSupabasePublicConfig();
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY?.trim();
  if (!publicConfig || !serviceRoleKey) return null;
  return { ...publicConfig, serviceRoleKey };
}

export function supabaseConfigurationStatus(): IntegrationStatus {
  return {
    configured: Boolean(getSupabasePublicConfig()),
    provider: "supabase",
  };
}

export function requireSupabaseServerConfig(): SupabasePublicConfig {
  const config = getSupabasePublicConfig();
  if (!config) throw new Error("Supabase public server configuration is incomplete.");
  return config;
}

export function requireSupabaseAdminConfig(): SupabaseAdminConfig {
  const config = getSupabaseAdminConfig();
  if (!config) throw new Error("Supabase admin configuration is incomplete.");
  return config;
}
