import { NextResponse } from "next/server";

import {
  createOrRetrySagaInvitation,
  listSagaAdminInvitations,
} from "@/server/admin/admin-operations";
import { sagaAdminErrorResponse } from "@/server/admin/http";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const invitations = await listSagaAdminInvitations();
    return NextResponse.json({ invitations }, { headers: { "cache-control": "no-store" } });
  } catch (error) {
    return sagaAdminErrorResponse(error);
  }
}

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as { email?: unknown; role?: unknown };
    const result = await createOrRetrySagaInvitation({ email: body.email, role: body.role });
    return NextResponse.json(result, { status: result.created ? 201 : 200 });
  } catch (error) {
    if (error instanceof SyntaxError) {
      return NextResponse.json({ error: "invalid_request" }, { status: 400 });
    }
    return sagaAdminErrorResponse(error);
  }
}
