import { NextResponse } from "next/server";

import {
  createSagaSourceReadUrl,
  SagaSourceUploadError,
} from "@/server/story/source-upload";

export const dynamic = "force-dynamic";

export async function GET(
  _request: Request,
  context: { params: Promise<{ sourceId: string }> },
) {
  const { sourceId } = await context.params;

  try {
    const signed = await createSagaSourceReadUrl(sourceId);
    return NextResponse.redirect(signed.url, 307);
  } catch (error) {
    if (error instanceof SagaSourceUploadError) {
      return NextResponse.json(
        { error: error.code },
        { status: error.httpStatus },
      );
    }
    return NextResponse.json({ error: "unavailable" }, { status: 503 });
  }
}
