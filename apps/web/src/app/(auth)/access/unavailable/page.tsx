import type { Metadata } from "next";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { completeInvitationAction } from "@/features/auth/actions";
import { AuthFrame } from "@/features/auth/auth-frame";
import { safeNextPath } from "@/lib/auth/redirects";

export const metadata: Metadata = {
  title: "Access unavailable",
};

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function UnavailablePage({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const retryInvitation = first(params.retry) === "invitation";
  const next = safeNextPath(first(params.next));

  return (
    <AuthFrame
      eyebrow="Access boundary"
      title="Access check unavailable"
      description="S.A.G.A. could not make a trustworthy product-access decision. Private routes remain closed until the server can verify identity and account state."
    >
      <div className="space-y-3">
        {retryInvitation ? (
          <form action={completeInvitationAction}>
            <input type="hidden" name="next" value={next} />
            <Button type="submit" className="w-full">
              Retry invitation completion
            </Button>
          </form>
        ) : null}
        <Link
          href="/sign-in"
          className="inline-flex min-h-11 w-full items-center justify-center rounded-xl border border-[var(--border)] px-4 py-2.5 text-sm font-semibold text-[var(--foreground)] transition hover:bg-white/5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
        >
          Return to sign in
        </Link>
      </div>
    </AuthFrame>
  );
}
