import { redirect } from "next/navigation";

import { safeNextPath } from "@/lib/auth/redirect";
import { getFreshSagaIdentity } from "@/server/account/identity";
import { setPasswordAction } from "@/server/auth/actions";

export const dynamic = "force-dynamic";

type PageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function SetPasswordPage({ searchParams }: PageProps) {
  const params = await searchParams;
  const next = safeNextPath(first(params.next));
  const error = first(params.error);

  let identity;
  try {
    identity = await getFreshSagaIdentity();
  } catch {
    redirect("/access/unavailable");
  }

  if (!identity) {
    redirect(`/sign-in?error=session&next=${encodeURIComponent("/set-password")}`);
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-xl items-center px-6 py-16">
      <section className="saga-panel w-full rounded-3xl p-7 sm:p-9" aria-labelledby="password-title">
        <div className="mb-8 space-y-3">
          <p className="text-sm font-semibold text-[var(--muted)]">S.A.G.A. account security</p>
          <h1 id="password-title" className="text-3xl font-semibold tracking-tight">Set your password</h1>
          <p className="text-sm leading-6 text-[var(--muted)]">
            Choose a password for <span className="text-[var(--foreground)]">{identity.email}</span>. Passwords are managed by Supabase Auth, not stored by S.A.G.A.
          </p>
        </div>

        {error ? (
          <p role="alert" className="mb-5 rounded-xl border border-red-400/25 bg-red-400/10 px-4 py-3 text-sm">
            {error === "invalid"
              ? "Use matching passwords with at least 10 characters."
              : error === "unavailable"
                ? "Account security is temporarily unavailable."
                : "The password could not be updated. Please try again."}
          </p>
        ) : null}

        <form action={setPasswordAction} className="space-y-5">
          <input type="hidden" name="next" value={next} />
          <div className="space-y-2">
            <label htmlFor="password" className="block text-sm font-medium">New password</label>
            <input id="password" name="password" type="password" autoComplete="new-password" minLength={10} required className="min-h-11 w-full rounded-xl border border-[var(--border)] bg-black/20 px-3 text-base outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/25" />
          </div>
          <div className="space-y-2">
            <label htmlFor="passwordConfirmation" className="block text-sm font-medium">Confirm password</label>
            <input id="passwordConfirmation" name="passwordConfirmation" type="password" autoComplete="new-password" minLength={10} required className="min-h-11 w-full rounded-xl border border-[var(--border)] bg-black/20 px-3 text-base outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/25" />
          </div>
          <button type="submit" className="min-h-11 w-full rounded-xl bg-[var(--foreground)] px-4 font-semibold text-[var(--background)] outline-none hover:opacity-90 focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--background)]">
            Save password
          </button>
        </form>
      </section>
    </main>
  );
}
