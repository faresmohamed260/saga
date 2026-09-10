import { NextResponse } from "next/server";

import { getCurrentSagaAccountState, isActiveSagaAdmin } from "@/server/account/current";
import { listSagaAdminAccounts } from "@/server/admin/accounts";

export async function GET() {
  const state = await getCurrentSagaAccountState();
  if (!isActiveSagaAdmin(state)) {
    return NextResponse.json(
      { error: state.status === "signed_out" ? "Authentication required." : "Active S.A.G.A. admin access is required." },
      { status: state.status === "signed_out" ? 401 : 403 },
    );
  }

  try {
    return NextResponse.json({ accounts: await listSagaAdminAccounts() });
  } catch {
    return NextResponse.json({ error: "Accounts are temporarily unavailable." }, { status: 503 });
  }
}
