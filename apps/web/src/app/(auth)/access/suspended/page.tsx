import type { Metadata } from "next";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { signOutAction } from "@/features/auth/actions";
import { AuthFrame } from "@/features/auth/auth-frame";

export const metadata: Metadata = {
  title: "Access suspended",
};

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function SuspendedPage({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const passwordUpdated = first(params.state) === "password_updated";

  return (
    <AuthFrame
      eyebrow="Access boundary"
      title="S.A.G.A. access is suspended"
      description="Authentication can remain valid while private narrative data stays unavailable. An administrator must reactivate S.A.G.A. product access."
    >
      {passwordUpdated ? (
        <p className="mb-5 rounded-xl border border-[var(--border)] bg-white/5 px-3.5 py-3 text-sm text-[var(--muted)]" role="status">
          Your password was updated.
        </p>
      ) : null}
      <div className="space-y-3">
        <Link
          href="/set-password"
          className="inline-flex min-h-11 w-full items-center justify-center rounded-xl border border-[var(--border)] px-4 py-2.5 text-sm font-semibold text-[var(--foreground)] transition hover:bg-white/5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
        >
          Change password
        </Link>
        <form action={signOutAction}>
          <Button type="submit" className="w-full">
            Sign out
          </Button>
        </form>
      </div>
    </AuthFrame>
  );
}
