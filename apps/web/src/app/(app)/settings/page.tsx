import type { Metadata } from "next";

import { PageHeader } from "@/components/shell/page-header";
import { signOutAction } from "@/features/auth/actions";
import { requireCurrentSagaAccount } from "@/server/account/account-access";

export const metadata: Metadata = {
  title: "Settings",
};

export default async function SettingsPage() {
  const account = await requireCurrentSagaAccount();

  return (
    <div className="flex flex-col gap-10">
      <PageHeader
        eyebrow="Account"
        title="Settings"
        description="Only account information that already exists in the closed-demo access model is shown here."
      />

      <section className="max-w-3xl border-y border-[var(--app-separator)]" aria-labelledby="account-heading">
        <div className="py-6">
          <h2 id="account-heading" className="text-sm font-semibold text-[var(--app-text)]">
            Account access
          </h2>
          <dl className="mt-5 grid gap-5 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-xs font-medium uppercase tracking-[0.12em] text-[var(--app-muted)]">Email</dt>
              <dd className="mt-1.5 break-all text-[var(--app-text)]">{account.email}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-[0.12em] text-[var(--app-muted)]">Role</dt>
              <dd className="mt-1.5 capitalize text-[var(--app-text)]">{account.role}</dd>
            </div>
          </dl>
        </div>

        <div className="border-t border-[var(--app-separator)] py-6">
          <h2 className="text-sm font-semibold text-[var(--app-text)]">Session</h2>
          <p className="mt-2 max-w-xl text-sm leading-6 text-[var(--app-muted)]">
            Sign out of this browser session. Public self-signup remains disabled for the closed demo.
          </p>
          <form action={signOutAction} className="mt-4">
            <button
              type="submit"
              className="inline-flex min-h-10 items-center rounded-lg border border-[var(--app-separator)] bg-[var(--app-surface)] px-4 text-sm font-semibold text-[var(--app-text)] transition-colors hover:bg-[var(--app-surface-elevated)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
            >
              Sign out
            </button>
          </form>
        </div>
      </section>
    </div>
  );
}
