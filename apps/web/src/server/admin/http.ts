import { NextResponse } from "next/server";

import { SagaAccessError } from "@/server/account/account-access";

import { SagaAdminOperationError } from "./admin-operations";

export function sagaAdminErrorResponse(error: unknown) {
  if (error instanceof SagaAccessError) {
    return NextResponse.json({ error: error.code }, { status: error.httpStatus });
  }
  if (error instanceof SagaAdminOperationError) {
    return NextResponse.json({ error: error.code }, { status: error.httpStatus });
  }
  return NextResponse.json({ error: "unavailable" }, { status: 503 });
}
