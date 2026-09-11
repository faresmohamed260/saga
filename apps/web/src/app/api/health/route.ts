import { NextResponse } from "next/server";

import { storageConfigurationStatus } from "@/server/storage";
import { supabaseConfigurationStatus } from "@/server/supabase/config";

export const dynamic = "force-dynamic";

function releaseIdentity() {
  return {
    commitSha: process.env.VERCEL_GIT_COMMIT_SHA?.trim() || null,
    environment: process.env.VERCEL_ENV?.trim() || null,
  };
}

export async function GET() {
  return NextResponse.json(
    {
      status: "ok",
      service: "saga-web",
      architecture: "v2",
      release: releaseIdentity(),
      integrations: {
        supabase: supabaseConfigurationStatus(),
        storage: storageConfigurationStatus(),
      },
    },
    {
      headers: {
        "cache-control": "no-store",
      },
    },
  );
}
