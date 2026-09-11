import type { Metadata } from "next";

import { PageHeader } from "@/components/shell/page-header";
import { signOutAction } from "@/features/auth/actions";

export const metadata: Metadata = {
  title: "Settings",
};

export default function SettingsPage() {
  return (
    <div className="flex flex-col gap-10">
      <PageHeader
        eyebrow="Account"
        title="Settings"
        description="Account controls are intentionally limited while the closed demo is being established."
      />

      <section className="max-w-3xl border-y border-[var(--app-separator)]" aria-labelledby="session-heading">
        <div className="py-6">
          <h2 id="session-heading" className="text-sm font-semibold text-[var(--app-text)]">
            Session
          </h2>
          <p className="mt-2 max-w-xl text-sm leading-6 text-[var(--app-muted)]">
            Sign out of this browser session. Public self-signup remains disabled for this closed demo; broader account administration is not enabled yet.
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
