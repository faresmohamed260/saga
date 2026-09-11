import type { Metadata } from "next";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AuthFrame } from "@/features/auth/auth-frame";
import { signInAction } from "@/features/auth/actions";
import { safeNextPath } from "@/lib/auth/redirects";

export const metadata: Metadata = {
  title: "Sign in",
};

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function messageFor(error: string | undefined, state: string | undefined): string | null {
  if (state === "signed_out") {
    return "You are signed out.";
  }
  if (error === "session_required") {
    return "Sign in to continue.";
  }
  if (error === "access_unavailable") {
    return "Sign-in is temporarily unavailable. Please try again.";
  }
  if (error) {
    return "We could not sign you in with those credentials.";
  }
  return null;
}

export default async function SignInPage({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const next = safeNextPath(first(params.next));
  const message = messageFor(first(params.error), first(params.state));

  return (
    <AuthFrame
      eyebrow="Closed demo"
      title="Sign in to S.A.G.A."
      description="Use the credentials established from your invitation. Product access remains controlled by S.A.G.A. after authentication."
    >
      {message ? (
        <p className="mb-5 rounded-xl border border-[var(--border)] bg-white/5 px-3.5 py-3 text-sm text-[var(--muted)]" role="status">
          {message}
        </p>
      ) : null}
      <form action={signInAction} className="space-y-5">
        <input type="hidden" name="next" value={next} />
        <div className="space-y-2">
          <label htmlFor="email" className="text-sm font-medium text-[var(--foreground)]">
            Email
          </label>
          <Input id="email" name="email" type="email" autoComplete="email" required />
        </div>
        <div className="space-y-2">
          <label htmlFor="password" className="text-sm font-medium text-[var(--foreground)]">
            Password
          </label>
          <Input id="password" name="password" type="password" autoComplete="current-password" required />
        </div>
        <Button type="submit" className="w-full">
          Sign in
        </Button>
      </form>
      <p className="mt-6 text-xs leading-5 text-[var(--muted)]">
        S.A.G.A. is invitation-only. Access is established by an administrator and cannot be self-enrolled from this page.
      </p>
    </AuthFrame>
  );
}
