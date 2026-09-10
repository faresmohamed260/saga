import { NextResponse } from "next/server";

import { getCurrentSagaAccountState, isActiveSagaAdmin } from "@/server/account/current";
import { revokeSagaInvitation, SagaAdminInvitationError } from "@/server/admin/invitations";

export async function DELETE(
  _request: Request,
  context: { params: Promise<{ invitationId: string }> },
) {
  const state = await getCurrentSagaAccountState();
  if (!isActiveSagaAdmin(state)) {
    return NextResponse.json(
      { error: state.status === "signed_out" ? "Authentication required." : "Active S.A.G.A. admin access is required." },
      { status: state.status === "signed_out" ? 401 : 403 },
    );
  }

  const { invitationId } = await context.params;
  if (!/^[0-9a-f-]{36}$/i.test(invitationId)) {
    return NextResponse.json({ error: "Invalid invitation." }, { status: 400 });
  }

  try {
    await revokeSagaInvitation(invitationId);
    return new NextResponse(null, { status: 204 });
  } catch (error) {
    if (error instanceof SagaAdminInvitationError) {
      const status = error.code === "invitation_not_found" ? 404 : 503;
      return NextResponse.json({ error: error.message }, { status });
    }
    return NextResponse.json({ error: "The invitation could not be revoked right now." }, { status: 503 });
  }
}
