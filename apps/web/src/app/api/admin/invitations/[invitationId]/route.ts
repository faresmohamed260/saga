import { NextResponse } from "next/server";

import { revokeSagaInvitation } from "@/server/admin/admin-operations";
import { sagaAdminErrorResponse } from "@/server/admin/http";
import { isCanonicalUuid } from "@/server/admin/validation";

export const dynamic = "force-dynamic";

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ invitationId: string }> },
) {
  try {
    const { invitationId } = await params;
    if (!isCanonicalUuid(invitationId)) {
      return NextResponse.json({ error: "invalid_request" }, { status: 400 });
    }

    const status = await revokeSagaInvitation(invitationId);
    return NextResponse.json({ status });
  } catch (error) {
    return sagaAdminErrorResponse(error);
  }
}
