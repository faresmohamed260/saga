import Link from "next/link";
import { redirect } from "next/navigation";
import { LockKeyhole, Sparkles } from "lucide-react";

import { buttonVariants } from "@/components/ui/button";
import { LoginForm } from "@/features/account/login-form";
import { SignOutButton } from "@/features/account/sign-out-button";
import { cn } from "@/lib/utils";
import { getCurrentSagaAccountState } from "@/server/account/current";

export default async function LoginPage() {
  const state = await getCurrentSagaAccountState();
  if (state.status === "active") redirect("/app");

  const signedInWithoutAccess = state.status === "invitation_required" || state.status === "suspended" || state.status === "unavailable";

  return (
    <main className="min-h-screen px-5 py-10 sm:px-8">
      <div className="mx-auto flex w-full max-w-5xl flex-col">
        <header className="flex items-center justify-between">
          <Link href="/" className="flex items-center gap-3">
            <span className="flex size-9 items-center justify-center rounded-xl border border-violet-300/20 bg-violet-400/10 text-violet-200">
              <Sparkles size={17} strokeWidth={1.8} />
            </span>
            <span className="text-sm font-semibold tracking-[0.24em]">S.A.G.A.</span>
          </Link>
          <Link href="/" className={cn(buttonVariants({ variant: "ghost", size: "sm" }))}>Back home</Link>
        </header>

        <section className="mx-auto grid w-full max-w-4xl flex-1 items-center gap-10 py-16 lg:grid-cols-[1fr_420px]">
          <div>
            <LockKeyhole className="mb-6 text-violet-200" size={28} strokeWidth={1.6} />
            <h1 className="max-w-xl text-4xl font-semibold tracking-[-0.045em] sm:text-5xl">Invitation-only access.</h1>
            <p className="mt-5 max-w-xl text-base leading-7 text-zinc-400">
              S.A.G.A. is currently a closed demo. Accounts are admitted by invitation so the product can evolve against a bounded real-user surface.
            </p>
          </div>

          <div className="rounded-2xl border border-white/10 bg-[#0c1119]/90 p-6 shadow-2xl sm:p-7">
            {state.status === "unconfigured" ? (
              <div>
                <h2 className="text-lg font-semibold">Account service not configured</h2>
                <p className="mt-3 text-sm leading-6 text-zinc-500">The web shell is available, but the S.A.G.A. Supabase project has not been connected to this environment yet.</p>
              </div>
            ) : signedInWithoutAccess ? (
              <div>
                <h2 className="text-lg font-semibold">This account cannot enter the demo</h2>
                <p className="mt-3 text-sm leading-6 text-zinc-500">
                  {state.status === "suspended"
                    ? "This S.A.G.A. account is suspended."
                    : state.status === "unavailable"
                      ? "S.A.G.A. could not verify product access right now."
                      : "A current S.A.G.A. invitation is required for this signed-in identity."}
                </p>
                <div className="mt-6"><SignOutButton /></div>
              </div>
            ) : (
              <div>
                <h2 className="text-lg font-semibold">Sign in</h2>
                <p className="mt-2 mb-6 text-sm leading-6 text-zinc-500">Use the email and password associated with your invited S.A.G.A. account.</p>
                <LoginForm />
              </div>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
