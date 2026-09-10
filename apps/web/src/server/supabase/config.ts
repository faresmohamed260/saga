export type IntegrationStatus = {
  configured: boolean;
  provider: string;
};

export function supabaseConfigurationStatus(): IntegrationStatus {
  const url = process.env.SUPABASE_URL?.trim();
  const publishableKey = process.env.SUPABASE_PUBLISHABLE_KEY?.trim();

  return {
    configured: Boolean(url && publishableKey),
    provider: "supabase",
  };
}

export function requireSupabaseServerConfig() {
  const url = process.env.SUPABASE_URL?.trim();
  const publishableKey = process.env.SUPABASE_PUBLISHABLE_KEY?.trim();

  if (!url || !publishableKey) {
    throw new Error("Supabase server configuration is incomplete.");
  }

  return { url, publishableKey };
}
