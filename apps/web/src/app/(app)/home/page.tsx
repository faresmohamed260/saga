import { signOutAction } from "@/server/auth/actions";

export default function HomePage() {
  return (
    <main className="mx-auto min-h-screen w-full max-w-5xl px-6 py-16">
      <section className="max-w-2xl">
        <p className="text-sm font-semibold text-[var(--muted)]">Private S.A.G.A. workspace</p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight">Access boundary established</h1>
        <p className="mt-4 text-base leading-7 text-[var(--muted)]">
          This Phase 1C foothold proves the private route boundary. The narrative application shell and Home, Library, and Projects composition belong to Phase 1D after the dedicated S.A.G.A. visual concept pass.
        </p>
        <form action={signOutAction} className="mt-8">
          <button type="submit" className="min-h-11 rounded-xl border border-[var(--border)] px-4 font-semibold outline-none hover:bg-white/5 focus-visible:ring-2 focus-visible:ring-[var(--accent)]">
            Sign out
          </button>
        </form>
      </section>
    </main>
  );
}
