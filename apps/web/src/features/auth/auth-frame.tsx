import Link from "next/link";
import type { ReactNode } from "react";

type AuthFrameProps = {
  eyebrow: string;
  title: string;
  description: string;
  children: ReactNode;
};

export function AuthFrame({ eyebrow, title, description, children }: AuthFrameProps) {
  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden px-5 py-12">
      <div className="saga-grid pointer-events-none absolute inset-0 opacity-50" aria-hidden="true" />
      <section className="saga-panel relative w-full max-w-md rounded-3xl p-6 sm:p-8" aria-labelledby="auth-title">
        <Link
          href="/"
          className="mb-8 inline-flex min-h-11 items-center text-sm font-semibold tracking-[0.28em] text-[var(--foreground)] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[var(--accent)]"
        >
          S.A.G.A.
        </Link>
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--cyan)]">{eyebrow}</p>
        <h1 id="auth-title" className="mt-3 text-3xl font-semibold tracking-tight text-[var(--foreground)]">
          {title}
        </h1>
        <p className="mt-3 text-sm leading-6 text-[var(--muted)]">{description}</p>
        <div className="mt-7">{children}</div>
      </section>
    </main>
  );
}
