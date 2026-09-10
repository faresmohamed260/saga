import { NextRequest, NextResponse } from "next/server";

import type { SagaAccessRole } from "@/lib/api/admin";
import { getCurrentSagaAccountState, isActiveSagaAdmin } from "@/server/account/current";
import {
  createSagaInvitation,
  listPendingSagaInvitations,
  SagaAdminInvitationError,
} from "@/server/admin/invitations";

function authorizationError(state: Awaited<ReturnType<typeof getCurrentSagaAccountState>>) {
  return NextResponse.json(
    { error: state.status === "signed_out" ? "Authentication required." : "Active S.A.G.A. admin access is required." },
    { status: state.status === "signed_out" ? 401 : 403 },
  );
}

export async function GET() {
  const state = await getCurrentSagaAccountState();
  if (!isActiveSagaAdmin(state)) return authorizationError(state);

  try {
    return NextResponse.json({ invitations: await listPendingSagaInvitations() });
  } catch {
    return NextResponse.json({ error: "Invitations are temporarily unavailable." }, { status: 503 });
  }
}

export async function POST(request: NextRequest) {
  const state = await getCurrentSagaAccountState();
  if (!isActiveSagaAdmin(state)) return authorizationError(state);

  let body: { email?: unknown; role?: unknown };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid invitation request." }, { status: 400 });
  }

  if (typeof body.email !== "string" || (body.role !== "member" && body.role !== "admin")) {
    return NextResponse.json({ error: "Invalid invitation request." }, { status: 400 });
  }

  const configuredOrigin = process.env.SAGA_PUBLIC_APP_URL?.trim();
  let redirectTo: string;
  try {
    redirectTo = new URL("/auth/confirm", configuredOrigin || request.nextUrl.origin).toString();
  } catch {
    return NextResponse.json({ error: "Invitation delivery is not configured." }, { status: 503 });
  }

  try {
    const result = await createSagaInvitation({
      email: body.email,
      role: body.role as SagaAccessRole,
      inviterUserId: state.identity.id,
      redirectTo,
    });
    return NextResponse.json(result, { status: 201 });
  } catch (error) {
    if (error instanceof SagaAdminInvitationError) {
      const status = error.code === "invalid_request" ? 400 : error.code === "invitation_exists" ? 409 : 503;
      return NextResponse.json({ error: error.message }, { status });
    }
    return NextResponse.json({ error: "The invitation could not be created right now." }, { status: 503 });
  }
}
