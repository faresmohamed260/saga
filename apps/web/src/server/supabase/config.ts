export type IntegrationStatus = {
  configured: boolean;
  provider: string;
};

function readRequired(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) {
    throw new Error(`${name} is not configured.`);
  }
  return value;
}

function readFirstRequired(names: string[]): string {
  for (const name of names) {
    const value = process.env[name]?.trim();
    if (value) {
      return value;
    }
  }

  throw new Error(`${names.join(" or ")} is not configured.`);
}

export function supabaseConfigurationStatus(): IntegrationStatus {
  const url = process.env.SUPABASE_URL?.trim();
  const publishableKey = process.env.SUPABASE_PUBLISHABLE_KEY?.trim();

  return {
    configured: Boolean(url && publishableKey),
    provider: "supabase",
  };
}

export function requireSupabaseServerConfig() {
  return {
    url: readRequired("SUPABASE_URL"),
    publishableKey: readRequired("SUPABASE_PUBLISHABLE_KEY"),
  };
}

export function requireSupabasePrivilegedConfig() {
  return {
    url: readRequired("SUPABASE_URL"),
    privilegedKey: readFirstRequired([
      "SUPABASE_SECRET_KEY",
      "SUPABASE_SERVICE_ROLE_KEY",
    ]),
  };
}
