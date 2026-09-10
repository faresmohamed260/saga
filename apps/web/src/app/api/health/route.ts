import { NextResponse } from "next/server";

import { storageConfigurationStatus } from "@/server/storage";
import { supabaseConfigurationStatus } from "@/server/supabase/config";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json(
    {
      status: "ok",
      service: "saga-web",
      architecture: "v2",
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
