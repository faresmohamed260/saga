import type { User } from "@supabase/supabase-js";
import { NextRequest, NextResponse } from "next/server";

import { claimSagaInvitation } from "@/server/account/access";
import { createSupabaseServerClient } from "@/server/supabase/server";

function redirectWithinApp(path: string) {
  return new NextResponse(null, {
    status: 307,
    headers: {
      Location: path,
      "Cache-Control": "private, no-store",
    },
  });
}

function verifiedIdentity(user: User | null) {
  if (!user || user.is_anonymous === true || typeof user.id !== "string") return null;
  return { id: user.id, email: typeof user.email === "string" ? user.email : null };
}

export async function GET(request: NextRequest) {
  const tokenHash = request.nextUrl.searchParams.get("token_hash")?.trim() || null;
  const code = request.nextUrl.searchParams.get("code")?.trim() || null;
  const type = request.nextUrl.searchParams.get("type");

  if ((!tokenHash && !code) || (tokenHash && type !== "invite")) {
    return redirectWithinApp("/login?auth=link_invalid");
  }

  const supabase = await createSupabaseServerClient();
  if (!supabase) return redirectWithinApp("/login?auth=unavailable");

  let user: User | null = null;
  if (tokenHash) {
    const { data, error } = await supabase.auth.verifyOtp({ token_hash: tokenHash, type: "invite" });
    if (error) return redirectWithinApp("/login?auth=link_invalid");
    user = data.user;
  } else if (code) {
    const { data, error } = await supabase.auth.exchangeCodeForSession(code);
    if (error) return redirectWithinApp("/login?auth=link_invalid");
    user = data.user;
  }

  const identity = verifiedIdentity(user);
  if (!identity) return redirectWithinApp("/login?auth=link_invalid");

  try {
    const access = await claimSagaInvitation(identity);
    if (!access || access.status !== "active") {
      return redirectWithinApp("/login?auth=invitation_required");
    }
  } catch {
    return redirectWithinApp("/login?auth=unavailable");
  }

  return redirectWithinApp("/app?welcome=1");
}
