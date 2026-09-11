import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { setPasswordAction } from "@/features/auth/actions";
import { AuthFrame } from "@/features/auth/auth-frame";
import { safeNextPath } from "@/lib/auth/redirects";
import { resolveCurrentSagaAccount } from "@/server/account/account-access";

export const metadata: Metadata = {
  title: "Set password",
};

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function SetPasswordPage({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const next = safeNextPath(first(params.next));
  const access = await resolveCurrentSagaAccount();

  if (access.state === "unauthenticated") {
    const returnTo = `/set-password?${new URLSearchParams({ next }).toString()}`;
    redirect(`/sign-in?${new URLSearchParams({ error: "session_required", next: returnTo }).toString()}`);
  }
  if (access.state === "not_admitted") {
    redirect("/access/not-admitted");
  }
  if (access.state === "unavailable") {
    redirect("/access/unavailable");
  }

  const error = first(params.error);
  const message =
    error === "password_invalid"
      ? "Use at least eight characters and make sure both entries match."
      : error
        ? "We could not update your password. Please try again."
        : null;

  return (
    <AuthFrame
      eyebrow="Account security"
      title="Set your password"
      description="Choose the password you will use for later S.A.G.A. sign-ins. This updates Supabase Auth credentials only; product access remains S.A.G.A.-controlled."
    >
      {message ? (
        <p className="mb-5 rounded-xl border border-[var(--border)] bg-white/5 px-3.5 py-3 text-sm text-[var(--muted)]" role="alert">
          {message}
        </p>
      ) : null}
      <form action={setPasswordAction} className="space-y-5">
        <input type="hidden" name="next" value={next} />
        <div className="space-y-2">
          <label htmlFor="password" className="text-sm font-medium text-[var(--foreground)]">
            New password
          </label>
          <Input id="password" name="password" type="password" autoComplete="new-password" minLength={8} required />
        </div>
        <div className="space-y-2">
          <label htmlFor="password-confirmation" className="text-sm font-medium text-[var(--foreground)]">
            Confirm password
          </label>
          <Input
            id="password-confirmation"
            name="password_confirmation"
            type="password"
            autoComplete="new-password"
            minLength={8}
            required
          />
        </div>
        <Button type="submit" className="w-full">
          Save password
        </Button>
      </form>
    </AuthFrame>
  );
}
