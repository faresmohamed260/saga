import Link from "next/link";

import { safeNextPath } from "@/lib/auth/redirect";
import { signInAction } from "@/server/auth/actions";

export const dynamic = "force-dynamic";

type PageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

const ERROR_MESSAGES: Record<string, string> = {
  invalid: "Sign-in failed. Check your credentials and try again.",
  session: "Your session could not be verified. Please sign in again.",
  unavailable: "Sign-in is temporarily unavailable. Please try again later.",
};

export default async function SignInPage({ searchParams }: PageProps) {
  const params = await searchParams;
  const next = safeNextPath(first(params.next));
  const error = first(params.error);
  const message = error ? ERROR_MESSAGES[error] : undefined;
  const signedOut = first(params.signedOut) === "1";

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-xl items-center px-6 py-16">
      <section className="saga-panel w-full rounded-3xl p-7 sm:p-9" aria-labelledby="sign-in-title">
        <div className="mb-8 space-y-3">
          <Link href="/" className="text-sm font-semibold text-[var(--muted)] hover:text-[var(--foreground)]">
            S.A.G.A.
          </Link>
          <h1 id="sign-in-title" className="text-3xl font-semibold tracking-tight">
            Sign in to the closed demo
          </h1>
          <p className="text-sm leading-6 text-[var(--muted)]">
            Access is invitation-only. Use the email address and password attached to your invited account.
          </p>
        </div>

        {message ? (
          <p role="alert" className="mb-5 rounded-xl border border-red-400/25 bg-red-400/10 px-4 py-3 text-sm">
            {message}
          </p>
        ) : null}
        {signedOut ? (
          <p role="status" className="mb-5 rounded-xl border border-[var(--border)] bg-white/5 px-4 py-3 text-sm">
            You have been signed out.
          </p>
        ) : null}

        <form action={signInAction} className="space-y-5">
          <input type="hidden" name="next" value={next} />
          <div className="space-y-2">
            <label htmlFor="email" className="block text-sm font-medium">Email</label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              required
              className="min-h-11 w-full rounded-xl border border-[var(--border)] bg-black/20 px-3 text-base outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/25"
            />
          </div>
          <div className="space-y-2">
            <label htmlFor="password" className="block text-sm font-medium">Password</label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              className="min-h-11 w-full rounded-xl border border-[var(--border)] bg-black/20 px-3 text-base outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/25"
            />
          </div>
          <button
            type="submit"
            className="min-h-11 w-full rounded-xl bg-[var(--foreground)] px-4 font-semibold text-[var(--background)] outline-none hover:opacity-90 focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--background)]"
          >
            Sign in
          </button>
        </form>

        <p className="mt-6 text-xs leading-5 text-[var(--muted)]">
          There is no public account creation path. Invitations are issued by a S.A.G.A. administrator.
        </p>
      </section>
    </main>
  );
}
