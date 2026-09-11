import Link from "next/link";
import { notFound } from "next/navigation";

import { signOutAction } from "@/server/auth/actions";

export const dynamic = "force-dynamic";

type AccessState = "not-admitted" | "suspended" | "unavailable";

type PageProps = {
  params: Promise<{ state: string }>;
};

const COPY: Record<AccessState, { title: string; body: string }> = {
  "not-admitted": {
    title: "This identity is not admitted to S.A.G.A.",
    body: "A valid Supabase identity is not enough to enter the closed demo. Access requires a matching active S.A.G.A. invitation and account record.",
  },
  suspended: {
    title: "S.A.G.A. access is suspended",
    body: "Your identity is valid, but the S.A.G.A. account is currently suspended. Private story data remains unavailable until an administrator reactivates access.",
  },
  unavailable: {
    title: "Account access is temporarily unavailable",
    body: "S.A.G.A. could not safely verify the complete identity and product-access boundary. Access fails closed rather than guessing.",
  },
};

function isAccessState(value: string): value is AccessState {
  return value in COPY;
}

export default async function AccessStatePage({ params }: PageProps) {
  const { state } = await params;
  if (!isAccessState(state)) {
    notFound();
  }

  const copy = COPY[state];
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-2xl items-center px-6 py-16">
      <section className="saga-panel w-full rounded-3xl p-7 sm:p-9">
        <p className="mb-3 text-sm font-semibold text-[var(--muted)]">Closed-demo access</p>
        <h1 className="text-3xl font-semibold tracking-tight">{copy.title}</h1>
        <p className="mt-4 max-w-prose text-sm leading-6 text-[var(--muted)]">{copy.body}</p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href="/sign-in" className="inline-flex min-h-11 items-center justify-center rounded-xl bg-[var(--foreground)] px-4 font-semibold text-[var(--background)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]">Sign in</Link>
          <form action={signOutAction}>
            <button type="submit" className="min-h-11 rounded-xl border border-[var(--border)] px-4 font-semibold outline-none hover:bg-white/5 focus-visible:ring-2 focus-visible:ring-[var(--accent)]">Sign out</button>
          </form>
        </div>
      </section>
    </main>
  );
}
