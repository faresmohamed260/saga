import type { Metadata } from "next";

import { Button } from "@/components/ui/button";
import { completeInvitationAction, signOutAction } from "@/features/auth/actions";
import { AuthFrame } from "@/features/auth/auth-frame";
import { safeNextPath } from "@/lib/auth/redirects";

export const metadata: Metadata = {
  title: "Invitation required",
};

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function NotAdmittedPage({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const next = safeNextPath(first(params.next));
  const noInvitation = first(params.error) === "no_pending_invitation";

  return (
    <AuthFrame
      eyebrow="Access boundary"
      title="Invitation required"
      description="Your authenticated identity does not currently have active S.A.G.A. product access. A matching pending invitation must be claimed before private routes can open."
    >
      {noInvitation ? (
        <p className="mb-5 rounded-xl border border-[var(--border)] bg-white/5 px-3.5 py-3 text-sm text-[var(--muted)]" role="status">
          No eligible pending invitation is available for the verified account.
        </p>
      ) : null}
      <div className="space-y-3">
        <form action={completeInvitationAction}>
          <input type="hidden" name="next" value={next} />
          <Button type="submit" className="w-full">
            Complete pending invitation
          </Button>
        </form>
        <form action={signOutAction}>
          <Button type="submit" className="w-full border-[var(--border)] bg-transparent text-[var(--foreground)] hover:bg-white/5">
            Sign out
          </Button>
        </form>
      </div>
    </AuthFrame>
  );
}
