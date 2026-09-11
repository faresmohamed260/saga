import type { Metadata } from "next";

import { Button } from "@/components/ui/button";
import { signOutAction } from "@/features/auth/actions";

export const metadata: Metadata = {
  title: "Private access",
};

export default function HomeAccessCheckpointPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-5 py-12">
      <section className="saga-panel w-full max-w-2xl rounded-3xl p-6 sm:p-9" aria-labelledby="private-title">
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--cyan)]">Phase 1C access checkpoint</p>
        <h1 id="private-title" className="mt-3 text-3xl font-semibold tracking-tight text-[var(--foreground)]">
          Private S.A.G.A. access verified
        </h1>
        <p className="mt-4 max-w-xl text-sm leading-6 text-[var(--muted)]">
          This route exists only to prove the closed-demo private boundary. The narrative application shell and real Home, Library, and Projects composition belong to Phase 1D.
        </p>
        <form action={signOutAction} className="mt-7">
          <Button type="submit">Sign out</Button>
        </form>
      </section>
    </main>
  );
}
