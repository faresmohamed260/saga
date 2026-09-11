import { NextResponse, type NextRequest } from "next/server";

import { safeNextPath } from "@/lib/auth/redirect";
import { claimCurrentSagaInvitation } from "@/server/account/claim-invitation";
import { createSupabaseServerClient } from "@/server/supabase/server";

export async function GET(request: NextRequest) {
  const tokenHash = request.nextUrl.searchParams.get("token_hash");
  const type = request.nextUrl.searchParams.get("type");
  const next = safeNextPath(request.nextUrl.searchParams.get("next"));

  if (!tokenHash || type !== "invite") {
    return NextResponse.redirect(new URL("/sign-in?error=confirmation", request.url));
  }

  try {
    const supabase = await createSupabaseServerClient();
    const { error } = await supabase.auth.verifyOtp({
      type: "invite",
      token_hash: tokenHash,
    });

    if (error) {
      return NextResponse.redirect(new URL("/sign-in?error=confirmation", request.url));
    }

    const account = await claimCurrentSagaInvitation();
    if (!account) {
      return NextResponse.redirect(new URL("/access/not-admitted", request.url));
    }

    if (account.status !== "active") {
      return NextResponse.redirect(new URL("/access/suspended", request.url));
    }

    const destination = new URL("/set-password", request.url);
    destination.searchParams.set("next", next);
    return NextResponse.redirect(destination);
  } catch {
    return NextResponse.redirect(new URL("/access/unavailable", request.url));
  }
}
