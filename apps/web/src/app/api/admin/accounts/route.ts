import { NextResponse } from "next/server";

import { listSagaAdminAccounts } from "@/server/admin/admin-operations";
import { sagaAdminErrorResponse } from "@/server/admin/http";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const accounts = await listSagaAdminAccounts();
    return NextResponse.json({ accounts }, { headers: { "cache-control": "no-store" } });
  } catch (error) {
    return sagaAdminErrorResponse(error);
  }
}
