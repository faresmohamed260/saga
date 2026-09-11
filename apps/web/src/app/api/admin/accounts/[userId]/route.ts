import { NextResponse } from "next/server";

import { updateSagaAdminAccount } from "@/server/admin/admin-operations";
import { sagaAdminErrorResponse } from "@/server/admin/http";
import { isCanonicalUuid } from "@/server/admin/validation";

export const dynamic = "force-dynamic";

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ userId: string }> },
) {
  try {
    const { userId } = await params;
    if (!isCanonicalUuid(userId)) {
      return NextResponse.json({ error: "invalid_request" }, { status: 400 });
    }

    const body = (await request.json()) as { role?: unknown; status?: unknown };
    const account = await updateSagaAdminAccount(userId, {
      role: body.role,
      status: body.status,
    });
    return NextResponse.json({ account });
  } catch (error) {
    if (error instanceof SyntaxError) {
      return NextResponse.json({ error: "invalid_request" }, { status: 400 });
    }
    return sagaAdminErrorResponse(error);
  }
}
