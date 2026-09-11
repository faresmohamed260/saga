import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import { refreshSupabaseSession } from "@/server/supabase/proxy";

export async function proxy(request: NextRequest): Promise<NextResponse> {
  try {
    return await refreshSupabaseSession(request);
  } catch {
    // Public pages must still render when provider configuration is missing or
    // temporarily unavailable. Private layouts fail closed via account resolution.
    return NextResponse.next({ request });
  }
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
