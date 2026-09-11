import { NextResponse } from "next/server";

import { safeNextPath } from "@/lib/auth/redirects";
import { claimCurrentSagaInvitation } from "@/server/account/claim-invitation";
import { createSupabaseServerClient } from "@/server/supabase/server";

function redirectTo(requestUrl: URL, path: string): NextResponse {
  return NextResponse.redirect(new URL(path, requestUrl.origin));
}

export async function GET(request: Request): Promise<NextResponse> {
  const requestUrl = new URL(request.url);
  const tokenHash = requestUrl.searchParams.get("token_hash")?.trim();
  const type = requestUrl.searchParams.get("type");
  const next = safeNextPath(requestUrl.searchParams.get("next"));

  if (!tokenHash || type !== "invite") {
    return redirectTo(requestUrl, "/sign-in?error=invalid_invitation");
  }

  let supabase;
  try {
    supabase = await createSupabaseServerClient();
    const verification = await supabase.auth.verifyOtp({
      type: "invite",
      token_hash: tokenHash,
    });

    if (verification.error) {
      return redirectTo(requestUrl, "/sign-in?error=invalid_invitation");
    }
  } catch {
    return redirectTo(requestUrl, "/sign-in?error=access_unavailable");
  }

  try {
    const account = await claimCurrentSagaInvitation();
    if (!account) {
      await supabase.auth.signOut();
      return redirectTo(requestUrl, "/sign-in?error=invalid_invitation");
    }

    if (account.status === "suspended") {
      return redirectTo(requestUrl, "/access/suspended");
    }

    const params = new URLSearchParams({ next });
    return redirectTo(requestUrl, `/set-password?${params.toString()}`);
  } catch {
    const params = new URLSearchParams({ retry: "invitation", next });
    return redirectTo(requestUrl, `/access/unavailable?${params.toString()}`);
  }
}
