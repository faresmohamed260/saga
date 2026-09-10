import { NextRequest, NextResponse } from "next/server";

import type { SagaAdminAccountUpdate } from "@/lib/api/admin";
import { getCurrentSagaAccountState, isActiveSagaAdmin } from "@/server/account/current";
import { SagaAdminAccountError, updateSagaAdminAccount } from "@/server/admin/accounts";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export async function PATCH(
  request: NextRequest,
  context: { params: Promise<{ userId: string }> },
) {
  const state = await getCurrentSagaAccountState();
  if (!isActiveSagaAdmin(state)) {
    return NextResponse.json(
      { error: state.status === "signed_out" ? "Authentication required." : "Active S.A.G.A. admin access is required." },
      { status: state.status === "signed_out" ? 401 : 403 },
    );
  }

  const { userId } = await context.params;
  if (!UUID_PATTERN.test(userId)) {
    return NextResponse.json({ error: "Invalid account." }, { status: 400 });
  }

  let body: SagaAdminAccountUpdate;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid account update." }, { status: 400 });
  }

  try {
    const account = await updateSagaAdminAccount(state.identity.id, userId, body);
    return NextResponse.json({ account });
  } catch (error) {
    if (error instanceof SagaAdminAccountError) {
      const status = error.code === "invalid_request"
        ? 400
        : error.code === "account_not_found"
          ? 404
          : error.code === "admin_required"
            ? 403
            : error.code === "self_lockout" || error.code === "last_active_admin"
              ? 409
              : 503;
      return NextResponse.json({ error: error.message }, { status });
    }
    return NextResponse.json({ error: "The account could not be updated right now." }, { status: 503 });
  }
}
